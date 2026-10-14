"""Hoá đơn công ty (G5c · Tuyền 14/10/2026, Q15 + Q19).

Khách lấy hoá đơn về công ty: kế toán cần tên công ty + địa chỉ + mã số thuế
(+ email nhận hoá đơn). Hai nơi lưu:

* `hoa_don_cong_ty` — BẢN CHỤP trên từng hoá đơn (phiếu thu). Đây là thứ xuất
  Excel MISA đọc. Không bao giờ tự đổi theo hồ sơ khách.
* `khach_cong_ty` — công ty trong HỒ SƠ khách (nhiều công ty/khách) để lần sau điền
  sẵn. Sửa ở đây KHÔNG đổi bản chụp đã ghi.

Sửa thẳng bản chụp thì ghi `hoa_don_cong_ty_lich_su` (ai, lúc nào, cũ → mới).
Bỏ chọn "xuất hoá đơn công ty" = đặt `bo_luc`, ghi lại là hoàn tác (không xoá dòng).

Quy tắc nhắc: MST sai dạng (không phải 10 số, hoặc 10 số + "-" + 3 số) vẫn LƯU,
chỉ trả lời nhắc trung tính — không chặn, không báo lỗi. Hàm ĐỌC nhận id rác thì
trả rỗng; hàm GHI nhận id/độ dài rác thì báo 422 (không ghi nửa chừng).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.audit import record_event

#: Ai ghi nhận được thông tin công ty: Lễ tân / CSKH (hồ sơ), Thu ngân (lúc thu),
#: Kế toán (sửa sau) — mọi người có MỘT trong các quyền này. Không gác theo vai.
QUYEN_CONG_TY: tuple[str, ...] = (
    "patient.create",
    "crm.manage",
    "reception.checkin.perform",
    "payment.service.collect",
    "payment.medicine.collect",
    "accounting.finance.full",
)

_MST_RE = re.compile(r"^[0-9]{10}(-[0-9]{3})?$")
DAI_TEN = 400
DAI_DIA_CHI = 500
DAI_MST = 20
DAI_EMAIL = 254
DAI_NGUOI_MUA = 200
_KHOANG_TRANG = re.compile(r"\s+")


def chuan_hoa_mst(raw: Any) -> str:
    """Bỏ khoảng trắng trong MST ("0123 456 789" → "0123456789"); rác → rỗng."""
    if not isinstance(raw, str):
        return ""
    return _KHOANG_TRANG.sub("", raw)


def mst_dung_dang(raw: Any) -> bool | None:
    """True/False nếu MST đúng/sai dạng; None khi chưa điền (không nhắc)."""
    mst = chuan_hoa_mst(raw)
    if not mst:
        return None
    return bool(_MST_RE.match(mst))


def nhac_mst(raw: Any) -> str | None:
    """Câu nhắc trung tính khi MST sai dạng; None khi ổn hoặc chưa điền."""
    if mst_dung_dang(raw) is False:
        return (
            "Mã số thuế thường có 10 số (hoặc 10 số-001) — kiểm lại giúp. "
            "Vẫn đã lưu như bạn nhập."
        )
    return None


def _uuid_hoac_none(raw: Any) -> UUID | None:
    """Chuỗi → UUID; rác → None (không ném)."""
    try:
        return UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return None


def _chu(raw: Any, toi_da: int, ten: str) -> str:
    """Chữ GHI vào dữ liệu: bỏ khoảng trắng thừa hai đầu; quá dài → 422."""
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValidationError(f"{ten} không hợp lệ.")
    s = raw.strip()
    if len(s) > toi_da:
        raise ValidationError(f"{ten} quá dài (tối đa {toi_da} ký tự).")
    return s


class BanGhiCongTy:
    """Bộ trường công ty đã chuẩn hoá — dùng chung cho hồ sơ khách và hoá đơn."""

    __slots__ = ("dia_chi", "email", "mst", "nguoi_mua", "ten")

    def __init__(
        self,
        *,
        ten_cong_ty: Any,
        dia_chi_cong_ty: Any = "",
        ma_so_thue: Any = "",
        email_nhan_hd: Any = "",
        nguoi_mua: Any = "",
    ) -> None:
        self.ten = _chu(ten_cong_ty, DAI_TEN, "Tên công ty")
        if not self.ten:
            raise ValidationError("Tên công ty không được để trống.")
        self.dia_chi = _chu(dia_chi_cong_ty, DAI_DIA_CHI, "Địa chỉ công ty")
        mst = chuan_hoa_mst(ma_so_thue)
        if len(mst) > DAI_MST:
            raise ValidationError(f"Mã số thuế quá dài (tối đa {DAI_MST} ký tự).")
        self.mst = mst
        self.email = _chu(email_nhan_hd, DAI_EMAIL, "Email nhận hoá đơn")
        self.nguoi_mua = _chu(nguoi_mua, DAI_NGUOI_MUA, "Người mua")

    def khac(self, cu: Any) -> bool:
        return bool(
            cu["ten_cong_ty"] != self.ten
            or cu["dia_chi_cong_ty"] != self.dia_chi
            or cu["ma_so_thue"] != self.mst
            or cu["email_nhan_hd"] != self.email
            or cu["nguoi_mua"] != self.nguoi_mua
        )


_COT_KHACH = (
    "id::text id, ten_cong_ty, dia_chi_cong_ty, ma_so_thue, email_nhan_hd,"
    " nguoi_mua, dung_luc, an_luc"
)
_COT_HOA_DON = (
    "id::text id, payment_cycle_id::text payment_cycle_id, ten_cong_ty,"
    " dia_chi_cong_ty, ma_so_thue, email_nhan_hd, nguoi_mua,"
    " khach_cong_ty_id::text khach_cong_ty_id, bo_luc, ghi_luc"
)
#: Công ty của khách: dùng gần nhất lên đầu (điền sẵn lần trước).
#: Chưa dùng lần nào thì cái mới tạo đứng trước.
_THU_TU_KHACH = "ORDER BY (an_luc IS NOT NULL), dung_luc DESC NULLS LAST, tao_luc DESC"


class HoaDonCongTyService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def _doi_quyen(
        self, conn: asyncpg.Connection, identity: StaffIdentity
    ) -> None:
        for q in QUYEN_CONG_TY:
            if await can(conn, identity, q):
                return
        await doi_quyen(conn, identity, QUYEN_CONG_TY[0])

    # ── Công ty trong hồ sơ khách ──────────────────────────────────────────

    async def doc_cong_ty_khach(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        ca_da_an: bool = False,
    ) -> list[dict[str, Any]]:
        """Công ty của khách, cái dùng gần nhất đứng đầu; id rác → rỗng."""
        pid = _uuid_hoac_none(clinic_patient_id)
        async with self.pool.acquire() as conn:
            await self._doi_quyen(conn, identity)
            if pid is None:
                return []
            rows = await conn.fetch(
                f"SELECT {_COT_KHACH} FROM public.khach_cong_ty"
                " WHERE clinic_id=$1::uuid AND clinic_patient_id=$2::uuid"
                f" AND ($3 OR an_luc IS NULL) {_THU_TU_KHACH}",
                identity.clinic_id,
                pid,
                ca_da_an,
            )
        return [dict(r) for r in rows]

    async def luu_cong_ty_khach(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        id_: str | None = None,
        ten_cong_ty: Any,
        dia_chi_cong_ty: Any = "",
        ma_so_thue: Any = "",
        email_nhan_hd: Any = "",
        nguoi_mua: Any = "",
    ) -> dict[str, Any]:
        """Thêm (id rỗng) hoặc sửa một công ty trong hồ sơ khách.

        Sửa ở đây KHÔNG đổi bản chụp trên các hoá đơn đã ghi. MST sai dạng vẫn
        lưu, trả `canh_bao_mst` (nhắc, không chặn).
        """
        pid = _uuid_hoac_none(clinic_patient_id)
        if pid is None:
            raise ValidationError("Mã khách không hợp lệ.")
        sua_id = None
        if id_:
            sua_id = _uuid_hoac_none(id_)
            if sua_id is None:
                raise ValidationError("Mã công ty không hợp lệ.")
        ban = BanGhiCongTy(
            ten_cong_ty=ten_cong_ty,
            dia_chi_cong_ty=dia_chi_cong_ty,
            ma_so_thue=ma_so_thue,
            email_nhan_hd=email_nhan_hd,
            nguoi_mua=nguoi_mua,
        )
        async with self.pool.acquire() as conn, conn.transaction():
            await self._doi_quyen(conn, identity)
            khach = await conn.fetchval(
                "SELECT 1 FROM public.patient"
                " WHERE clinic_id=$1::uuid AND clinic_patient_id=$2::uuid",
                identity.clinic_id,
                pid,
            )
            if not khach:
                raise ResourceNotFoundError("Không tìm thấy khách này.")
            if sua_id is None:
                row = await conn.fetchrow(
                    "INSERT INTO public.khach_cong_ty(clinic_id, clinic_patient_id,"
                    " ten_cong_ty, dia_chi_cong_ty, ma_so_thue, email_nhan_hd,"
                    " nguoi_mua, tao_boi, sua_boi)"
                    " VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8::uuid,$8::uuid)"
                    " RETURNING id::text id",
                    identity.clinic_id,
                    pid,
                    ban.ten,
                    ban.dia_chi,
                    ban.mst,
                    ban.email,
                    ban.nguoi_mua,
                    identity.staff_id,
                )
            else:
                row = await conn.fetchrow(
                    "UPDATE public.khach_cong_ty SET ten_cong_ty=$4,"
                    " dia_chi_cong_ty=$5, ma_so_thue=$6, email_nhan_hd=$7,"
                    " nguoi_mua=$8, sua_boi=$9::uuid, sua_luc=now()"
                    " WHERE clinic_id=$1::uuid AND clinic_patient_id=$2::uuid"
                    " AND id=$3::uuid RETURNING id::text id",
                    identity.clinic_id,
                    pid,
                    sua_id,
                    ban.ten,
                    ban.dia_chi,
                    ban.mst,
                    ban.email,
                    ban.nguoi_mua,
                    identity.staff_id,
                )
                if row is None:
                    raise ResourceNotFoundError("Không tìm thấy công ty của khách.")
            await record_event(
                conn,
                event_type="hoa_don_cong_ty.khach_luu",
                aggregate_type="khach_cong_ty",
                aggregate_id=row["id"],
                identity=identity,
                origin="api:hoa-don-cong-ty",
                payload={"clinic_patient_id": str(pid), "sua": sua_id is not None},
            )
        return {"id": row["id"], "canh_bao_mst": nhac_mst(ban.mst)}

    async def an_cong_ty_khach(
        self, *, identity: StaffIdentity, id_: str, an: bool
    ) -> dict[str, Any]:
        """Gỡ công ty khỏi hồ sơ khách (an=True) hoặc khôi phục (an=False)."""
        cid = _uuid_hoac_none(id_)
        if cid is None:
            raise ValidationError("Mã công ty không hợp lệ.")
        async with self.pool.acquire() as conn, conn.transaction():
            await self._doi_quyen(conn, identity)
            row = await conn.fetchrow(
                "UPDATE public.khach_cong_ty SET sua_boi=$3::uuid, sua_luc=now(),"
                " an_luc = CASE WHEN $4 THEN now() ELSE NULL END"
                " WHERE clinic_id=$1::uuid AND id=$2::uuid RETURNING id::text id",
                identity.clinic_id,
                cid,
                identity.staff_id,
                bool(an),
            )
            if row is None:
                raise ResourceNotFoundError("Không tìm thấy công ty của khách.")
            await record_event(
                conn,
                event_type="hoa_don_cong_ty.khach_an",
                aggregate_type="khach_cong_ty",
                aggregate_id=row["id"],
                identity=identity,
                origin="api:hoa-don-cong-ty",
                payload={"an": bool(an)},
            )
        return {"id": row["id"], "an": bool(an)}

    # ── Công ty trên một hoá đơn (bản chụp) ────────────────────────────────

    async def doc_hoa_don(
        self, *, identity: StaffIdentity, payment_cycle_id: str
    ) -> dict[str, Any]:
        """Bản chụp công ty của hoá đơn (None nếu chưa ghi / đã bỏ) + gợi ý điền
        sẵn từ hồ sơ khách (công ty dùng lần trước đứng đầu)."""
        cid = _uuid_hoac_none(payment_cycle_id)
        async with self.pool.acquire() as conn:
            await self._doi_quyen(conn, identity)
            if cid is None:
                return {"cong_ty": None, "goi_y": [], "da_bo": False}
            row = await conn.fetchrow(
                f"SELECT {_COT_HOA_DON} FROM public.hoa_don_cong_ty"
                " WHERE clinic_id=$1::uuid AND payment_cycle_id=$2::uuid",
                identity.clinic_id,
                cid,
            )
            goi_y = await conn.fetch(
                f"SELECT {_COT_KHACH} FROM public.khach_cong_ty"
                " WHERE clinic_id=$1::uuid AND an_luc IS NULL"
                " AND clinic_patient_id = (SELECT v.clinic_patient_id"
                "   FROM payment_cycle pc JOIN visit v"
                "     ON v.visit_id=pc.visit_id AND v.clinic_id=pc.clinic_id"
                "  WHERE pc.clinic_id=$1::uuid AND pc.payment_cycle_id=$2::uuid)"
                f" {_THU_TU_KHACH}",
                identity.clinic_id,
                cid,
            )
        hoat_dong = row is not None and row["bo_luc"] is None
        return {
            "cong_ty": dict(row) if hoat_dong and row else None,
            "da_bo": row is not None and row["bo_luc"] is not None,
            "goi_y": [dict(r) for r in goi_y],
        }

    async def ghi_hoa_don(
        self,
        *,
        identity: StaffIdentity,
        payment_cycle_id: str,
        ten_cong_ty: Any,
        dia_chi_cong_ty: Any = "",
        ma_so_thue: Any = "",
        email_nhan_hd: Any = "",
        nguoi_mua: Any = "",
        khach_cong_ty_id: str | None = None,
        luu_vao_ho_so: bool = True,
    ) -> dict[str, Any]:
        """Tick "xuất hoá đơn công ty" (hoặc sửa bản chụp) cho một hoá đơn.

        Ghi BẢN CHỤP; có đổi so với bản trước (hoặc ghi lại sau khi bỏ) thì thêm
        một dòng lịch sử. `luu_vao_ho_so`: công ty gõ mới ở hoá đơn cũng được ghi
        vào hồ sơ khách để lần sau điền sẵn. MST sai dạng vẫn lưu, trả nhắc.
        """
        cid = _uuid_hoac_none(payment_cycle_id)
        if cid is None:
            raise ValidationError("Mã hoá đơn không hợp lệ.")
        khach_id = None
        if khach_cong_ty_id:
            khach_id = _uuid_hoac_none(khach_cong_ty_id)
            if khach_id is None:
                raise ValidationError("Mã công ty không hợp lệ.")
        ban = BanGhiCongTy(
            ten_cong_ty=ten_cong_ty,
            dia_chi_cong_ty=dia_chi_cong_ty,
            ma_so_thue=ma_so_thue,
            email_nhan_hd=email_nhan_hd,
            nguoi_mua=nguoi_mua,
        )
        async with self.pool.acquire() as conn, conn.transaction():
            await self._doi_quyen(conn, identity)
            # Khoá theo hoá đơn: hai người cùng ghi một phiếu thì xếp hàng.
            ck = await conn.fetchrow(
                "SELECT v.clinic_patient_id FROM payment_cycle pc JOIN visit v"
                " ON v.visit_id=pc.visit_id AND v.clinic_id=pc.clinic_id"
                " WHERE pc.clinic_id=$1::uuid AND pc.payment_cycle_id=$2::uuid"
                " FOR UPDATE OF pc",
                identity.clinic_id,
                cid,
            )
            if ck is None:
                raise ResourceNotFoundError("Không tìm thấy hoá đơn này.")
            khach_id = await self._khach_cong_ty_id(
                conn,
                identity,
                ban=ban,
                khach_id=khach_id,
                clinic_patient_id=ck["clinic_patient_id"],
                luu=luu_vao_ho_so,
            )
            cu = await conn.fetchrow(
                "SELECT * FROM public.hoa_don_cong_ty"
                " WHERE clinic_id=$1::uuid AND payment_cycle_id=$2::uuid"
                " FOR UPDATE",
                identity.clinic_id,
                cid,
            )
            await conn.execute(
                "INSERT INTO public.hoa_don_cong_ty(clinic_id, payment_cycle_id,"
                " ten_cong_ty, dia_chi_cong_ty, ma_so_thue, email_nhan_hd,"
                " nguoi_mua, khach_cong_ty_id, bo_luc, ghi_boi, ghi_luc)"
                " VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,NULL,$9::uuid,now())"
                " ON CONFLICT ON CONSTRAINT uq_hoa_don_cong_ty_cycle DO UPDATE SET"
                " ten_cong_ty=EXCLUDED.ten_cong_ty,"
                " dia_chi_cong_ty=EXCLUDED.dia_chi_cong_ty,"
                " ma_so_thue=EXCLUDED.ma_so_thue,"
                " email_nhan_hd=EXCLUDED.email_nhan_hd,"
                " nguoi_mua=EXCLUDED.nguoi_mua,"
                " khach_cong_ty_id=EXCLUDED.khach_cong_ty_id, bo_luc=NULL,"
                " ghi_boi=EXCLUDED.ghi_boi, ghi_luc=now()",
                identity.clinic_id,
                cid,
                ban.ten,
                ban.dia_chi,
                ban.mst,
                ban.email,
                ban.nguoi_mua,
                khach_id,
                identity.staff_id,
            )
            if khach_id is not None:
                await conn.execute(
                    "UPDATE public.khach_cong_ty SET dung_luc=now()"
                    " WHERE clinic_id=$1::uuid AND id=$2::uuid",
                    identity.clinic_id,
                    khach_id,
                )
            hanh_dong = (
                "ghi"
                if cu is None
                else "lai"
                if cu["bo_luc"] is not None
                else "sua"
                if ban.khac(cu)
                else None
            )
            if hanh_dong is not None:
                await self._them_lich_su(conn, identity, cid, hanh_dong, cu=cu, moi=ban)
                await record_event(
                    conn,
                    event_type="hoa_don_cong_ty.ghi",
                    aggregate_type="payment_cycle",
                    aggregate_id=str(cid),
                    identity=identity,
                    origin="api:hoa-don-cong-ty",
                    payload={"hanh_dong": hanh_dong},
                )
        return {
            "ok": True,
            "payment_cycle_id": str(cid),
            "khach_cong_ty_id": str(khach_id) if khach_id else None,
            "canh_bao_mst": nhac_mst(ban.mst),
            "doi": hanh_dong is not None,
        }

    async def _khach_cong_ty_id(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        ban: BanGhiCongTy,
        khach_id: UUID | None,
        clinic_patient_id: UUID,
        luu: bool,
    ) -> UUID | None:
        """Công ty trong hồ sơ khách ứng với bản chụp: dùng cái được chọn (nếu
        thuộc về khách này), không thì tìm theo MST / tên, không có thì thêm mới.

        `luu=False` (không ghi vào hồ sơ): chỉ nhận cái được chọn, không đụng hồ sơ.
        Bản chụp mới ghi cũng cập nhật dòng hồ sơ ứng với nó — hồ sơ giữ thông tin
        của LẦN GHI GẦN NHẤT (điền sẵn lần sau); chiều ngược lại thì không (sửa hồ sơ
        không kéo bản chụp theo).
        """
        if khach_id is not None:
            co = await conn.fetchval(
                "SELECT 1 FROM public.khach_cong_ty WHERE clinic_id=$1::uuid"
                " AND id=$2::uuid AND clinic_patient_id=$3::uuid",
                identity.clinic_id,
                khach_id,
                clinic_patient_id,
            )
            if not co:
                return None
            ung = khach_id
        elif not luu:
            return None
        else:
            tim = await conn.fetchval(
                "SELECT id FROM public.khach_cong_ty WHERE clinic_id=$1::uuid"
                " AND clinic_patient_id=$2::uuid AND an_luc IS NULL AND"
                " ((ma_so_thue <> '' AND ma_so_thue=$3)"
                "  OR lower(ten_cong_ty)=lower($4))"
                " ORDER BY dung_luc DESC NULLS LAST, tao_luc DESC LIMIT 1",
                identity.clinic_id,
                clinic_patient_id,
                ban.mst,
                ban.ten,
            )
            if tim is None:
                moi = await conn.fetchval(
                    "INSERT INTO public.khach_cong_ty(clinic_id, clinic_patient_id,"
                    " ten_cong_ty, dia_chi_cong_ty, ma_so_thue, email_nhan_hd,"
                    " nguoi_mua, tao_boi, sua_boi)"
                    " VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8::uuid,$8::uuid)"
                    " RETURNING id",
                    identity.clinic_id,
                    clinic_patient_id,
                    ban.ten,
                    ban.dia_chi,
                    ban.mst,
                    ban.email,
                    ban.nguoi_mua,
                    identity.staff_id,
                )
                return UUID(str(moi))
            ung = UUID(str(tim))
        if luu:
            await conn.execute(
                "UPDATE public.khach_cong_ty SET ten_cong_ty=$3, dia_chi_cong_ty=$4,"
                " ma_so_thue=$5, email_nhan_hd=$6, nguoi_mua=$7, sua_boi=$8::uuid,"
                " sua_luc=now() WHERE clinic_id=$1::uuid AND id=$2::uuid",
                identity.clinic_id,
                ung,
                ban.ten,
                ban.dia_chi,
                ban.mst,
                ban.email,
                ban.nguoi_mua,
                identity.staff_id,
            )
        return ung

    async def bo_hoa_don(
        self, *, identity: StaffIdentity, payment_cycle_id: str
    ) -> dict[str, Any]:
        """Bỏ chọn "xuất hoá đơn công ty" (hoàn tác = ghi lại). Không xoá dòng nào."""
        cid = _uuid_hoac_none(payment_cycle_id)
        if cid is None:
            raise ValidationError("Mã hoá đơn không hợp lệ.")
        async with self.pool.acquire() as conn, conn.transaction():
            await self._doi_quyen(conn, identity)
            cu = await conn.fetchrow(
                "SELECT * FROM public.hoa_don_cong_ty WHERE clinic_id=$1::uuid"
                " AND payment_cycle_id=$2::uuid FOR UPDATE",
                identity.clinic_id,
                cid,
            )
            if cu is None:
                raise ResourceNotFoundError("Hoá đơn này chưa ghi công ty.")
            if cu["bo_luc"] is None:
                await conn.execute(
                    "UPDATE public.hoa_don_cong_ty SET bo_luc=now(),"
                    " ghi_boi=$3::uuid, ghi_luc=now()"
                    " WHERE clinic_id=$1::uuid AND payment_cycle_id=$2::uuid",
                    identity.clinic_id,
                    cid,
                    identity.staff_id,
                )
                await self._them_lich_su(conn, identity, cid, "bo", cu=cu, moi=None)
                await record_event(
                    conn,
                    event_type="hoa_don_cong_ty.bo",
                    aggregate_type="payment_cycle",
                    aggregate_id=str(cid),
                    identity=identity,
                    origin="api:hoa-don-cong-ty",
                    payload={},
                )
        return {"ok": True, "payment_cycle_id": str(cid)}

    async def _them_lich_su(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        cid: UUID,
        hanh_dong: str,
        *,
        cu: Any,
        moi: BanGhiCongTy | None,
    ) -> None:
        def cu_(k: str) -> str:
            return str(cu[k]) if cu is not None else ""

        await conn.execute(
            "INSERT INTO public.hoa_don_cong_ty_lich_su(clinic_id, payment_cycle_id,"
            " hanh_dong, cu_ten, cu_dia_chi, cu_ma_so_thue, cu_email, cu_nguoi_mua,"
            " moi_ten, moi_dia_chi, moi_ma_so_thue, moi_email, moi_nguoi_mua,"
            " sua_boi) VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,"
            "$14::uuid)",
            identity.clinic_id,
            cid,
            hanh_dong,
            cu_("ten_cong_ty"),
            cu_("dia_chi_cong_ty"),
            cu_("ma_so_thue"),
            cu_("email_nhan_hd"),
            cu_("nguoi_mua"),
            moi.ten if moi else "",
            moi.dia_chi if moi else "",
            moi.mst if moi else "",
            moi.email if moi else "",
            moi.nguoi_mua if moi else "",
            identity.staff_id,
        )

    async def doc_lich_su(
        self, *, identity: StaffIdentity, payment_cycle_id: str
    ) -> list[dict[str, Any]]:
        """Lịch sử ghi/sửa/bỏ công ty của một hoá đơn, mới nhất trước; id rác → rỗng."""
        cid = _uuid_hoac_none(payment_cycle_id)
        async with self.pool.acquire() as conn:
            await self._doi_quyen(conn, identity)
            if cid is None:
                return []
            rows = await conn.fetch(
                "SELECT ls.hanh_dong, ls.cu_ten, ls.cu_dia_chi, ls.cu_ma_so_thue,"
                " ls.cu_email, ls.cu_nguoi_mua, ls.moi_ten, ls.moi_dia_chi,"
                " ls.moi_ma_so_thue, ls.moi_email, ls.moi_nguoi_mua, ls.sua_luc,"
                " s.full_name AS sua_boi_ten"
                " FROM public.hoa_don_cong_ty_lich_su ls"
                " LEFT JOIN public.staff s ON s.id=ls.sua_boi"
                " WHERE ls.clinic_id=$1::uuid AND ls.payment_cycle_id=$2::uuid"
                " ORDER BY ls.sua_luc DESC, ls.id LIMIT 100",
                identity.clinic_id,
                cid,
            )
        return [dict(r) for r in rows]


async def doc_cong_ty_cho_phieu(
    conn: asyncpg.Connection, clinic_id: str, cycle_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """{payment_cycle_id: công ty} của các hoá đơn đang chọn "công ty" — để xuất
    hoá đơn đọc. Bỏ chọn (bo_luc) thì không có mặt. Id rác bị bỏ qua."""
    ids = [u for u in (_uuid_hoac_none(x) for x in cycle_ids) if u is not None]
    if not ids:
        return {}
    rows = await conn.fetch(
        "SELECT payment_cycle_id::text id, ten_cong_ty, dia_chi_cong_ty,"
        " ma_so_thue, email_nhan_hd, nguoi_mua"
        " FROM public.hoa_don_cong_ty"
        " WHERE clinic_id=$1::uuid AND payment_cycle_id=ANY($2::uuid[])"
        " AND bo_luc IS NULL",
        clinic_id,
        ids,
    )
    return {r["id"]: dict(r) for r in rows}
