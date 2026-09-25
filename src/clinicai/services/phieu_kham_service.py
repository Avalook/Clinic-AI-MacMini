"""Bảy phiếu khám — định nghĩa theo phiên bản, cổng kiểm một lần lưu, dữ liệu đọc kèm.

GÓI NÀY KHÔNG TỰ QUYẾT BA THỨ, và cả ba được CẮM TỪ NGOÀI VÀO:

1. **Phiếu gắn vào đâu.** Bảy phiếu khám (5 chuyên khoa + Thủ thuật + Sàn chậu)
   gắn vào consultation/visit. Chỉ phiếu KẾT QUẢ DỊCH VỤ mới gắn
   `service_order`. `form_instance` hiện chỉ có `service_order_id`, nên chỗ
   lưu một lần điền phiếu khám CHƯA CÓ — INTEGRATION_BLOCKER, không vá bằng
   cách giả khám thành một chỉ định. Gói này vì thế không mở/ghi
   `form_instance` nào; nó cung cấp cổng `kiem_luu` mà chỗ lưu tương lai gọi.
2. **Hồ sơ đã chốt chưa.** Clinical shell truyền `editable` /
   `finalized_locked` / `amendment_mode` (`phieu_kham.che_do`). Gói này không
   đọc trạng thái lượt, không biết mốc chốt ở đâu.
3. **Ai được làm.** `KiemQuyen` do hệ phân quyền của CORE cung cấp. Gói này
   không thêm capability, không mượn capability của module khác.

Còn lại là việc của gói: khung theo ĐÚNG phiên bản, kiểm dữ liệu theo khoá ổn
định (không so tên), phần mang sang, kết quả CLS theo `service_order_id`.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import asyncpg

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.events.catalogue import DonThuocDaLuu
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.phieu_kham import anh_xa_danh_muc as ax
from clinicai.phieu_kham.che_do import doi_ghi_duoc
from clinicai.phieu_kham.ket_qua_chi_dinh import (
    doc_ket_qua_theo_chi_dinh,
    doc_mau_du_phong,
)
from clinicai.phieu_kham.khung import (
    FORM_IDS,
    dinh_nghia,
    kiem_du_lieu,
    la_phieu_kham,
    tham_chieu_nguon,
)
from clinicai.phieu_kham.mang_sang import doc_dau_phieu

#: Việc cần hỏi quyền. Đây là NHÃN của lời hỏi gửi sang hệ phân quyền, không
#: phải capability — ánh xạ sang capability nào là việc của CORE.
HanhDong = Literal["doc_phieu", "ghi_phieu", "doc_ket_qua_cls"]

#: Hệ phân quyền của CORE: không có quyền thì RAISE (SafetyGateError).
KiemQuyen = Callable[[asyncpg.Connection, StaffIdentity, HanhDong], Awaitable[None]]


async def chua_noi_quyen(
    conn: asyncpg.Connection, identity: StaffIdentity, hanh_dong: HanhDong
) -> None:
    """Mặc định khi CHƯA nối hệ phân quyền: chặn tất. Đóng khi nghi ngờ."""
    raise SafetyGateError(f"Phiếu khám chưa được nối với hệ phân quyền ({hanh_dong}).")


#: Ghi phiếu khám = ghi bệnh án (bác sĩ, thư ký y khoa, BS siêu âm).
QUYEN_GHI = "clinical.record.write"
#: Bác sĩ tư vấn ghi vào CHÍNH phiếu khám của lượt (Tuyền chốt 24/09: "tư vấn
#: ghi vào chính bệnh án") — người chỉ có khối Tư vấn cũng ghi được.
QUYEN_GHI_THEM: frozenset[str] = frozenset({"clinical.intake.perform"})
#: Đọc: ai đang khám / ghi bệnh án / điền kết quả của lượt.
QUYEN_DOC = (
    "clinical.record.write",
    "clinical.consult.perform",
    "clinical.intake.perform",
    "result.form.fill",
)

#: Không khoá (Tuyền chốt 23/09/2026): Hoàn tất chỉ là mốc giờ, phiếu sửa tiếp
#: được. Chế độ duy nhất shell dùng cho phiếu mới.
CHE_DO_MO = "editable"


async def kiem_quyen_core(
    conn: asyncpg.Connection, identity: StaffIdentity, hanh_dong: HanhDong
) -> None:
    """Hệ phân quyền của CORE cắm vào gói (IP-2) — hỏi capability, không hỏi vai."""
    if hanh_dong == "ghi_phieu":
        for quyen in QUYEN_GHI_THEM:
            if await can(conn, identity, quyen):
                return
        await doi_quyen(
            conn, identity, QUYEN_GHI, cau="Bạn chưa được cấp quyền ghi phiếu khám."
        )
        return
    for quyen in QUYEN_DOC:
        if await can(conn, identity, quyen):
            return
    raise SafetyGateError("Bạn chưa được cấp quyền xem phiếu khám.")


def _khoa_ten(t: str) -> str:
    """Khoá so tên thuốc: bỏ hoa/thường và MỌI dấu cách ("Dunium/ Fetogard" =
    "Dunium/Fetogard")."""
    return "".join(t.split()).lower()


class PhieuKhamService:
    def __init__(self, pool: asyncpg.Pool, *, kiem_quyen: KiemQuyen) -> None:
        self._pool = pool
        self._kiem_quyen = kiem_quyen

    # ------------------------------------------------------------------
    async def khung_theo_ban(
        self, *, form_id: str, version: int | None, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Khung của MỘT phiên bản (hoặc bản đang dùng nếu `version` None).

        Phiếu đã bắt đầu điền thì ghim phiên bản của nó: xuất bản v2 thêm một
        ô thì phiếu v1 vẫn không có ô ấy.
        """
        if not la_phieu_kham(form_id):
            raise ValidationError(f"“{form_id}” không phải phiếu khám.")
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            dong = await conn.fetchrow(
                "SELECT form_id, version, ten, khung FROM form_definition"
                " WHERE clinic_id = $1::uuid AND form_id = $2"
                "   AND (($3::int IS NULL AND trang_thai = 'PUBLISHED')"
                "        OR version = $3::int)",
                identity.clinic_id,
                form_id,
                version,
            )
        if dong is None:
            ban = f" v{version}." if version is not None else " nào đang dùng."
            raise ValidationError(f"Phiếu “{form_id}” chưa có bản{ban}")
        return {
            "form_id": dong["form_id"],
            "version": dong["version"],
            "ten": dong["ten"],
            "khung": json.loads(dong["khung"]),
        }

    async def kiem_luu(
        self,
        *,
        form_id: str,
        version: int,
        du_lieu: dict[str, Any],
        che_do: object,
        identity: StaffIdentity,
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
        """Cổng một lần lưu — chỗ lưu phiếu khám (khi có) gọi TRƯỚC khi ghi.

        Thứ tự có chủ ý: chế độ trước (hồ sơ đã chốt thì không cần biết dữ liệu
        đúng hay sai), rồi quyền, rồi khung đúng phiên bản, rồi từng ô.
        """
        doi_ghi_duoc(che_do)
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "ghi_phieu")
        ban = await self.khung_theo_ban(
            form_id=form_id, version=version, identity=identity
        )
        return kiem_du_lieu(ban["khung"], du_lieu)

    # ------------------------------------------------------------------
    # CHỖ LƯU: phiếu của một LƯỢT (bảng `phieu_kham_luot`, migration
    # 20260924000008). Gỡ INTEGRATION_BLOCKER mà không giả khám thành chỉ định.
    async def doc_luot(
        self, *, visit_id: str, form_id: str | None, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Phiếu của lượt. Chưa có bản ghi thì dựng từ loại khám của lượt;
        loại khám không gắn phiếu nào thì trả danh sách để bác sĩ chọn."""
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            luot = await conn.fetchrow(
                "SELECT st.form_code FROM visit v"
                " LEFT JOIN service_type st ON st.id = v.service_type_id"
                " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
                cid,
                visit_id,
            )
            if luot is None:
                raise ValidationError("Không tìm thấy lượt khám.")
            dong = await conn.fetchrow(
                "SELECT form_id, version, du_lieu, revision, sua_luc"
                "  FROM phieu_kham_luot"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND ($3::text IS NULL OR form_id = $3)"
                " ORDER BY sua_luc DESC LIMIT 1",
                cid,
                visit_id,
                form_id,
            )
        chon = form_id or (dong["form_id"] if dong else None)
        if chon is None and luot["form_code"] in FORM_IDS:
            chon = luot["form_code"]
        if chon is None:
            return {
                "form_id": None,
                "chon_duoc": [
                    {"form_id": f, "ten": dinh_nghia(f)["ten"]} for f in FORM_IDS
                ],
            }
        ban = await self.khung_theo_ban(
            form_id=chon,
            version=int(dong["version"]) if dong else None,
            identity=identity,
        )
        du_lieu: Any = dong["du_lieu"] if dong else {}
        if isinstance(du_lieu, str):
            du_lieu = json.loads(du_lieu)
        return {
            **ban,
            "du_lieu": du_lieu,
            "revision": int(dong["revision"]) if dong else 0,
            "sua_luc": dong["sua_luc"].isoformat() if dong else None,
            "che_do": CHE_DO_MO,
            "mac_dinh_theo_loai_kham": luot["form_code"] in FORM_IDS,
        }

    async def luu_luot(
        self,
        *,
        visit_id: str,
        form_id: str,
        du_lieu: dict[str, Any],
        expected_revision: int,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Tự lưu một lần: qua cổng `kiem_luu` rồi ghi, có chống đè.

        Hai người cùng gõ (bác sĩ + thư ký) mà người kia vừa lưu → 409, màn tải
        lại chứ không đè im lặng.
        """
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            ban = await conn.fetchval(
                "SELECT version FROM phieu_kham_luot WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND form_id = $3",
                cid,
                visit_id,
                form_id,
            )
        if ban is None:
            ban = (
                await self.khung_theo_ban(
                    form_id=form_id, version=None, identity=identity
                )
            )["version"]
        sach, canh_bao = await self.kiem_luu(
            form_id=form_id,
            version=int(ban),
            du_lieu=du_lieu,
            che_do=CHE_DO_MO,
            identity=identity,
        )
        async with self._pool.acquire() as conn, conn.transaction():
            if not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM visit WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid)",
                cid,
                visit_id,
            ):
                raise ValidationError("Không tìm thấy lượt khám.")
            dong = await conn.fetchrow(
                "SELECT id, revision FROM phieu_kham_luot WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND form_id = $3 FOR UPDATE",
                cid,
                visit_id,
                form_id,
            )
            goi = json.dumps(sach, ensure_ascii=False)
            if dong is None:
                if expected_revision != 0:
                    raise ConflictError("Phiếu này không còn — tải lại trang.")
                moi = await conn.fetchval(
                    "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id,"
                    " version, du_lieu, revision, tao_boi, sua_boi)"
                    " VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, 1, $6::uuid,"
                    " $6::uuid)"
                    " ON CONFLICT (clinic_id, visit_id, form_id) DO NOTHING"
                    " RETURNING revision",
                    cid,
                    visit_id,
                    form_id,
                    int(ban),
                    goi,
                    identity.staff_id,
                )
                if moi is None:
                    raise ConflictError(
                        "Có người vừa mở phiếu này cùng lúc — tải lại để không đè."
                    )
            else:
                if int(dong["revision"]) != expected_revision:
                    raise ConflictError(
                        "Có người vừa lưu phiếu này — tải lại để không đè."
                    )
                moi = await conn.fetchval(
                    "UPDATE phieu_kham_luot SET du_lieu = $2::jsonb,"
                    " revision = revision + 1, sua_boi = $3::uuid, sua_luc = now()"
                    " WHERE id = $1::uuid RETURNING revision",
                    dong["id"],
                    goi,
                    identity.staff_id,
                )
        return {"ok": True, "revision": int(moi), "canh_bao": canh_bao}

    # ------------------------------------------------------------------
    async def tham_chieu_that(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Danh mục C / F / thuốc của nguồn, GẮN mã thật của phòng khám này.

        Mã lấy từ bảng ghép viết tay (`anh_xa_danh_muc`) rồi hỏi DB xem phòng
        khám có dịch vụ / thuốc ấy đang bật không. Không có → `service_code`
        null (màn khoá ô), không đoán.
        """
        tc = tham_chieu_nguon()
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            dv = {
                r["service_code"]: r["unit_price"]
                for r in await conn.fetch(
                    "SELECT service_code, unit_price FROM service_price"
                    " WHERE clinic_id = $1::uuid AND active AND \"group\" = 'dich_vu'",
                    cid,
                )
            }
            dong_kho = await conn.fetch(
                "SELECT DISTINCT ON (name_raw) id, name_raw, name_base, unit_price,"
                "       don_vi_ban, duong_dung, cach_dung, luu_y, biet_duoc"
                "  FROM drug_catalog WHERE clinic_id = $1::uuid AND is_active"
                " ORDER BY name_raw, created_at",
                cid,
            )
            kho = {r["name_raw"]: r for r in dong_kho}
            # Gắn theo TÊN (bỏ qua hoa/thường, dấu cách) khi bảng ghép viết tay
            # thiếu (24/09/2026: "thuốc quy chuẩn về, đừng đẻ cái kiểu chưa gắn kho").
            theo_ten: dict[str, asyncpg.Record] = {}
            for r in dong_kho:
                for t in (r["name_raw"], r["name_base"]):
                    if t:
                        theo_ten.setdefault(_khoa_ten(t), r)

        def gan(d: ax.DichVuPhieu | None) -> dict[str, Any]:
            if d is None or d.ma not in dv:
                return {"service_code": None, "gia": None}
            gia = dv[d.ma]
            return {"service_code": d.ma, "gia": int(gia) if gia is not None else None}

        for nhom in tc["chi_dinh_cls"]:
            nhom["muc"] = [{**m, **gan(ax.CLS.get(m["nhan"]))} for m in nhom["muc"]]
        tc["thu_thuat"] = [
            {**t, **gan(ax.THU_THUAT.get(t["ma"]))} for t in tc["thu_thuat"]
        ]

        # KHO LÀ NGUỒN (Tuyền 25/09/2026): tên, giá, đơn vị, cách dùng, lưu ý đọc
        # từ danh mục kho — dược sĩ sửa ở Kho thuốc là màn kê đơn đổi theo. Nhãn
        # phiếu chỉ còn là chỗ bác sĩ quen tìm. Mặt hàng kho không có trên phiếu
        # (Ozempic, King Seal…) cũng chọn được, kèm hướng dẫn.
        def tu_kho(m: dict[str, Any], r: asyncpg.Record | None) -> dict[str, Any]:
            if r is None:
                return {**m, "drug_catalog_id": None, "gia": None}
            return {
                **m,
                "brand": r["biet_duoc"] or m.get("brand") or "",
                "type": r["duong_dung"] or m.get("type") or "",
                "dosage": r["cach_dung"] or m.get("dosage") or "",
                "note": r["luu_y"] or m.get("note") or "",
                "unit": r["don_vi_ban"] or m.get("unit") or "",
                "drug_catalog_id": str(r["id"]),
                "gia": int(r["unit_price"]) if r["unit_price"] is not None else None,
            }

        mau = []
        da_gan: set[str] = set()
        for m in tc["mau_thuoc"]:
            ten_kho = ax.THUOC.get(m["ma"])
            r = kho.get(ten_kho) if ten_kho else None
            if r is None and m.get("nhan_nguon"):
                r = theo_ten.get(_khoa_ten(str(m["nhan_nguon"])))
            if r is not None:
                da_gan.add(str(r["id"]))
            mau.append(tu_kho(m, r))
        for r in dong_kho:
            if str(r["id"]) in da_gan:
                continue
            mau.append(
                tu_kho(
                    {"ma": f"kho:{r['id']}", "nhan_nguon": r["name_raw"]},
                    r,
                )
            )
        tc["mau_thuoc"] = mau
        return tc

    # Đơn thuốc (mục E) — ghi qua ĐÚNG đường bệnh án đang dùng
    # (`luu_don_chua_ky`), nên nhà thuốc nhận đơn y như trước.
    async def doc_don_thuoc(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            rows = await conn.fetch(
                "SELECT id::text, drug_catalog_id::text, drug_name_raw, quantity,"
                "       dosage_instructions, caution"
                "  FROM prescription"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND removed_at IS NULL AND nguon = 'BAC_SI'"
                " ORDER BY created_at, id",
                identity.clinic_id,
                visit_id,
            )
        return [dict(r) for r in rows]

    async def luu_don_thuoc(
        self,
        *,
        visit_id: str,
        dong: list[dict[str, Any]],
        ly_do: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        from clinicai.services.dinh_chinh_don import luu_don_chua_ky

        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await self._kiem_quyen(conn, identity, "ghi_phieu")
            # Thứ tự khoá của đơn thuốc: visit → prescription → allocation.
            luot = await conn.fetchrow(
                "SELECT clinic_patient_id::text AS pid FROM visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid FOR UPDATE",
                cid,
                visit_id,
            )
            if luot is None:
                raise ValidationError("Không tìm thấy lượt khám.")
            tom_tat = await luu_don_chua_ky(
                conn,
                visit_id=visit_id,
                clinic_id=cid,
                clinic_patient_id=luot["pid"],
                prescriptions=dong,
                created_by=identity.staff_id,
                identity=identity,
                ly_do=ly_do,
            )
            thay = int((tom_tat or {}).get("so_dong_thay") or 0)
            bo = int((tom_tat or {}).get("so_dong_bo") or 0)
            them = int((tom_tat or {}).get("so_dong_them") or 0)
            doi_tai_cho = int((tom_tat or {}).get("so_dong_sua") or 0) + int(
                (tom_tat or {}).get("so_dong_xoa") or 0
            )
            if thay or bo or them or doi_tai_cho:
                so_dong = await conn.fetchval(
                    "SELECT count(*) FROM prescription WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND removed_at IS NULL",
                    cid,
                    visit_id,
                )
                await emit_event(
                    conn,
                    ten="prescription.saved",
                    clinic_id=cid,
                    aggregate_id=visit_id,
                    payload=DonThuocDaLuu(
                        visit_id=visit_id,
                        so_dong=int(so_dong or 0),
                        so_dong_them=them,
                        so_dong_thay=thay,
                        so_dong_bo=bo,
                    ),
                    boi=nguoi(identity),
                    correlation_id=visit_id,
                )
        return {"ok": True, "tom_tat": tom_tat}

    # ------------------------------------------------------------------
    async def dau_phieu(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            return await doc_dau_phieu(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id
            )

    async def mau_du_phong(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_ket_qua_cls")
            return await doc_mau_du_phong(conn, clinic_id=identity.clinic_id)

    async def ket_qua_chi_dinh(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_ket_qua_cls")
            return await doc_ket_qua_theo_chi_dinh(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id
            )


__all__ = [
    "HanhDong",
    "KiemQuyen",
    "PhieuKhamService",
    "chua_noi_quyen",
    "kiem_quyen_core",
]
