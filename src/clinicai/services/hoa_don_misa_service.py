"""Đánh dấu "đã xuất sang MISA" + danh sách "có thay đổi sau khi xuất" (G5c).

Kế toán tải file Excel rồi nhập vào MISA — hệ thống không tự biết. Sau khi tải,
kế toán bấm "Đánh dấu đã xuất MISA" cho khoảng ngày đó: máy chủ tự dựng lại danh
sách hoá đơn của khoảng (không tin danh sách từ trình duyệt), lưu mỗi hoá đơn một
dòng cùng dấu vân tay (`hoa_don_misa_doc`). Từ đó:

* màn xuất hiện "Đã xuất MISA lúc …" cạnh mỗi hoá đơn;
* hoá đơn mà dữ liệu hiện tại khác dấu vân tay lúc xuất (hoàn tiền, sửa dòng, đổi
  công ty / người mua) hiện "Có thay đổi sau khi xuất" kèm lý do, và có danh sách
  riêng để vào MISA sửa.

Bỏ đánh dấu = đặt `huy_luc` (hoàn tác được, không xoá). Quyền = lego
`accounting.finance.full`; không có quyền thì không đánh dấu / không xem danh sách
lần xuất (phần trạng thái trên màn xuất đi theo quyền xem màn xuất).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.hoa_don_misa_doc import dau_van_tay, so_sanh
from clinicai.services.xuat_hoa_don_service import XuatHoaDonService

QUYEN_MISA = "accounting.finance.full"
TOI_DA_LAN_XUAT = 50
_GHI_CHU_DAI = 500


def _ngay_ghi(raw: Any, ten: str) -> date:
    """Ngày GHI vào dữ liệu: đúng "YYYY-MM-DD" hoặc 422 (không ghi ngày đoán)."""
    try:
        return date.fromisoformat(str(raw).strip())
    except (ValueError, TypeError):
        raise ValidationError(f"{ten} không hợp lệ — chọn lại khoảng ngày.") from None


def _uuid_hoac_none(raw: Any) -> UUID | None:
    try:
        return UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return None


class HoaDonMisaService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def danh_dau(
        self,
        *,
        identity: StaffIdentity,
        tu: Any,
        den: Any,
        loai: str | None = None,
        co_so: str | None = None,
        ghi_chu: Any = "",
    ) -> dict[str, Any]:
        """Đánh dấu mọi hoá đơn trong khoảng là đã xuất sang MISA.

        Danh sách do MÁY CHỦ dựng lại (cùng cổng quyền / phạm vi với màn xuất).
        Khoảng ngày rác → 422 (không đoán). Không có hoá đơn nào → 422.
        """
        d_tu, d_den = _ngay_ghi(tu, "Ngày bắt đầu"), _ngay_ghi(den, "Ngày kết thúc")
        if d_den < d_tu:
            raise ValidationError("Ngày kết thúc phải sau ngày bắt đầu.")
        if not isinstance(ghi_chu, str) or len(ghi_chu.strip()) > _GHI_CHU_DAI:
            raise ValidationError("Ghi chú không hợp lệ hoặc quá dài.")
        async with self.pool.acquire() as conn:
            await doi_quyen(conn, identity, QUYEN_MISA)
        data, goc = await XuatHoaDonService(self.pool).doc_goc(
            identity=identity,
            tu=d_tu.isoformat(),
            den=d_den.isoformat(),
            loai=loai,
            co_so=co_so,
        )
        if not goc:
            raise ValidationError("Không có hoá đơn nào trong khoảng này để đánh dấu.")
        tong = sum(int(h["tong"]) for h in goc)
        async with self.pool.acquire() as conn, conn.transaction():
            xuat_id = await conn.fetchval(
                "INSERT INTO public.hoa_don_misa_xuat(clinic_id, tu_ngay, den_ngay,"
                " co_so, loai, so_hoa_don, tong_tien, ghi_chu, xuat_boi)"
                " VALUES($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9::uuid) RETURNING id",
                identity.clinic_id,
                d_tu,
                d_den,
                data.get("co_so"),
                loai or None,
                len(goc),
                tong,
                ghi_chu.strip(),
                identity.staff_id,
            )
            for h in goc:
                nm, nd = dau_van_tay(h)
                await conn.execute(
                    "INSERT INTO public.hoa_don_misa_xuat_dong(clinic_id, xuat_id,"
                    " payment_cycle_id, ma_phieu, tong, dau_nguoi_mua, dau_noi_dung)"
                    " VALUES($1::uuid,$2,$3::uuid,$4,$5,$6,$7)",
                    identity.clinic_id,
                    xuat_id,
                    h["payment_cycle_id"],
                    str(h.get("ma_phieu") or ""),
                    int(h["tong"]),
                    nm,
                    nd,
                )
            await record_event(
                conn,
                event_type="hoa_don_misa.danh_dau",
                aggregate_type="hoa_don_misa_xuat",
                aggregate_id=str(xuat_id),
                identity=identity,
                origin="api:hoa-don-misa",
                payload={
                    "tu": d_tu.isoformat(),
                    "den": d_den.isoformat(),
                    "so_hoa_don": len(goc),
                },
            )
        return {
            "id": str(xuat_id),
            "so_hoa_don": len(goc),
            "tong_tien": tong,
            "tu": d_tu.isoformat(),
            "den": d_den.isoformat(),
        }

    async def huy_danh_dau(
        self, *, identity: StaffIdentity, xuat_id: str
    ) -> dict[str, Any]:
        """Bỏ đánh dấu một lần xuất (hoàn tác = đánh dấu lại). Bỏ lần hai: im lặng."""
        uid = _uuid_hoac_none(xuat_id)
        if uid is None:
            raise ValidationError("Mã lần xuất không hợp lệ.")
        async with self.pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_MISA)
            row = await conn.fetchrow(
                "SELECT huy_luc FROM public.hoa_don_misa_xuat"
                " WHERE clinic_id=$1::uuid AND id=$2::uuid FOR UPDATE",
                identity.clinic_id,
                uid,
            )
            if row is None:
                raise ResourceNotFoundError("Không tìm thấy lần xuất này.")
            if row["huy_luc"] is None:
                await conn.execute(
                    "UPDATE public.hoa_don_misa_xuat SET huy_luc=now(),"
                    " huy_boi=$3::uuid WHERE clinic_id=$1::uuid AND id=$2::uuid",
                    identity.clinic_id,
                    uid,
                    identity.staff_id,
                )
                await record_event(
                    conn,
                    event_type="hoa_don_misa.huy",
                    aggregate_type="hoa_don_misa_xuat",
                    aggregate_id=str(uid),
                    identity=identity,
                    origin="api:hoa-don-misa",
                    payload={},
                )
        return {"ok": True, "id": str(uid)}

    async def khoi_phuc(
        self, *, identity: StaffIdentity, xuat_id: str
    ) -> dict[str, Any]:
        """Hoàn tác "bỏ đánh dấu": đánh dấu lại đúng lần xuất đó."""
        uid = _uuid_hoac_none(xuat_id)
        if uid is None:
            raise ValidationError("Mã lần xuất không hợp lệ.")
        async with self.pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_MISA)
            row = await conn.fetchrow(
                "UPDATE public.hoa_don_misa_xuat SET huy_luc=NULL, huy_boi=NULL"
                " WHERE clinic_id=$1::uuid AND id=$2::uuid AND huy_luc IS NOT NULL"
                " RETURNING id",
                identity.clinic_id,
                uid,
            )
            if row is not None:
                await record_event(
                    conn,
                    event_type="hoa_don_misa.khoi_phuc",
                    aggregate_type="hoa_don_misa_xuat",
                    aggregate_id=str(uid),
                    identity=identity,
                    origin="api:hoa-don-misa",
                    payload={},
                )
        return {"ok": True, "id": str(uid)}

    async def doc_danh_sach(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Các lần đã xuất gần nhất (kể cả đã bỏ đánh dấu, để khôi phục)."""
        async with self.pool.acquire() as conn:
            await doi_quyen(conn, identity, QUYEN_MISA)
            rows = await conn.fetch(
                "SELECT x.id::text id, x.tu_ngay, x.den_ngay, x.co_so, x.loai,"
                " x.so_hoa_don, x.tong_tien, x.ghi_chu, x.xuat_luc, x.huy_luc,"
                " s.full_name xuat_boi_ten"
                " FROM public.hoa_don_misa_xuat x"
                " LEFT JOIN public.staff s ON s.id=x.xuat_boi"
                " WHERE x.clinic_id=$1::uuid ORDER BY x.xuat_luc DESC LIMIT $2",
                identity.clinic_id,
                TOI_DA_LAN_XUAT,
            )
        return [dict(r) for r in rows]

    async def doc_chi_tiet(
        self, *, identity: StaffIdentity, xuat_id: str
    ) -> dict[str, Any]:
        """Một lần xuất: từng hoá đơn đã xuất + cái nào CÓ THAY ĐỔI so với bây giờ."""
        uid = _uuid_hoac_none(xuat_id)
        async with self.pool.acquire() as conn:
            await doi_quyen(conn, identity, QUYEN_MISA)
            if uid is None:
                raise ResourceNotFoundError("Không tìm thấy lần xuất này.")
            lan = await conn.fetchrow(
                "SELECT id::text id, tu_ngay, den_ngay, co_so, loai, so_hoa_don,"
                " tong_tien, xuat_luc, huy_luc FROM public.hoa_don_misa_xuat"
                " WHERE clinic_id=$1::uuid AND id=$2::uuid",
                identity.clinic_id,
                uid,
            )
            if lan is None:
                raise ResourceNotFoundError("Không tìm thấy lần xuất này.")
            dong = await conn.fetch(
                "SELECT payment_cycle_id::text id, ma_phieu, tong, dau_nguoi_mua,"
                " dau_noi_dung FROM public.hoa_don_misa_xuat_dong"
                " WHERE clinic_id=$1::uuid AND xuat_id=$2::uuid ORDER BY ma_phieu",
                identity.clinic_id,
                uid,
            )
        _, goc = await XuatHoaDonService(self.pool).doc_goc(
            identity=identity,
            tu=lan["tu_ngay"].isoformat(),
            den=lan["den_ngay"].isoformat(),
            loai=lan["loai"],
            co_so=lan["co_so"],
        )
        hien = {h["payment_cycle_id"]: dau_van_tay(h) for h in goc}
        hoa_don = []
        for d in dong:
            ly_do = so_sanh(d, hien.get(d["id"]))
            hoa_don.append(
                {
                    "payment_cycle_id": d["id"],
                    "ma_phieu": d["ma_phieu"],
                    "tong": d["tong"],
                    "co_thay_doi": bool(ly_do),
                    "ly_do": ly_do,
                }
            )
        return {
            "lan_xuat": dict(lan),
            "hoa_don": hoa_don,
            "so_co_thay_doi": sum(1 for h in hoa_don if h["co_thay_doi"]),
        }

    async def gan_trang_thai(
        self, *, identity: StaffIdentity, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Gắn `misa` vào từng hoá đơn của kết quả `XuatHoaDonService.xem` và thêm
        hai số tổng. `data["dau_van_tay"]` (dấu vân tay hiện tại theo phiếu) được lấy
        ra khỏi kết quả — không trả cho trình duyệt."""
        hien: dict[str, tuple[str, str]] = data.pop("dau_van_tay", {})
        ids = [
            i
            for i in (
                _uuid_hoac_none(h.get("payment_cycle_id")) for h in data["hoa_don"]
            )
            if i
        ]
        da_xuat: dict[str, Any] = {}
        if ids:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT DISTINCT ON (d.payment_cycle_id)"
                    " d.payment_cycle_id::text id, x.id::text xuat_id, x.xuat_luc,"
                    " d.dau_nguoi_mua, d.dau_noi_dung, s.full_name xuat_boi_ten"
                    " FROM public.hoa_don_misa_xuat_dong d"
                    " JOIN public.hoa_don_misa_xuat x ON x.id=d.xuat_id"
                    " LEFT JOIN public.staff s ON s.id=x.xuat_boi"
                    " WHERE d.clinic_id=$1::uuid AND x.huy_luc IS NULL"
                    " AND d.payment_cycle_id=ANY($2::uuid[])"
                    " ORDER BY d.payment_cycle_id, x.xuat_luc DESC",
                    identity.clinic_id,
                    ids,
                )
            da_xuat = {r["id"]: dict(r) for r in rows}
        so_da, so_doi = 0, 0
        thay_doi_theo_phieu: dict[str, list[str]] = {}
        for pid, d in da_xuat.items():
            thay_doi_theo_phieu[pid] = so_sanh(d, hien.get(pid))
        for h in data["hoa_don"]:
            d = da_xuat.get(str(h.get("payment_cycle_id")))
            if d is None:
                h["misa"] = None
                continue
            ly_do = thay_doi_theo_phieu[str(h["payment_cycle_id"])]
            h["misa"] = {
                "xuat_id": d["xuat_id"],
                "xuat_luc": d["xuat_luc"].isoformat(),
                "xuat_boi": d["xuat_boi_ten"],
                "co_thay_doi": bool(ly_do),
                "ly_do": ly_do,
            }
        so_da = len(da_xuat)
        so_doi = sum(1 for v in thay_doi_theo_phieu.values() if v)
        data["so_da_xuat_misa"] = so_da
        data["so_co_thay_doi_sau_xuat"] = so_doi
        return data
