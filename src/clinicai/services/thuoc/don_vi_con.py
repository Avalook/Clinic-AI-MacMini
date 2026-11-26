"""Khối "Đơn vị con và tính số ngày dùng hết thuốc" của Danh mục & giá (Tuyền 26/11).

Màn chỉ hỏi ba câu, đúng lời Tuyền:
  · Đơn vị con của [hộp] là [viên ▼]
  · 1 [hộp] có bao nhiêu [viên]        → `so_lieu_moi_don_vi_goc` (dùng lại cột PR E)
  · Giá 1 [viên]                        → `gia_con`; trống = giá mẹ ÷ số con
Đơn vị MẸ = `don_vi_ban` (đơn vị tính, kho đếm theo nó). Cách dùng gõ chữ ở ô "Cách
dùng" phía trên; máy đọc bằng `tach_cau` — ở đây chỉ hiện "xem trước" để kho biết câu
gõ đã được hiểu đúng chưa (vd "Ngày 2 viên → 1 hộp 30 viên dùng 15 ngày").
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.don_vi_thuoc import chuan, doi_quyen_sua_gia, so_dep
from clinicai.services.thuoc.cach_dung import lieu_ngay
from clinicai.services.thuoc.don_vi_ke import kiem_ten_don_vi
from clinicai.services.thuoc.tach_cau import de_xuat_cach_dung

#: Đơn vị con hay dùng — màn cho chọn, vẫn gõ được tên khác.
DON_VI_CON_GOI_Y = ("viên", "viên đặt", "gói", "ống", "que", "miếng", "ml", "liều")


def gia_con_tu_tinh(gia_me: Any, so_con: Any) -> int | None:
    """Giá mẹ ÷ số con, làm tròn đồng. Thiếu một trong hai thì None."""
    if gia_me is None or not so_con:
        return None
    return int((Decimal(gia_me) / Decimal(so_con)).quantize(Decimal(1), ROUND_HALF_UP))


def xem_truoc(cach_dung: str, me: str, con: str, so_con: Any) -> str:
    """Một dòng cho kho đọc: máy hiểu câu cách dùng thế nào, 1 mẹ dùng được mấy ngày."""
    ct = de_xuat_cach_dung(cach_dung)
    lieu = lieu_ngay(ct)
    if lieu is None:
        return "Máy chưa đọc được liều trong câu cách dùng — không tính ngày dùng."
    lieu_chu = so_dep(Decimal(lieu.numerator) / Decimal(lieu.denominator))
    dv = ct.don_vi_lieu
    if lieu < 1:
        moi = round(1 / lieu)
        dau = (
            f"{moi} ngày dùng 1 {dv}"
            if Fraction(1, moi) == lieu
            else f"{lieu_chu} {dv}/ngày"
        )
    else:
        dau = f"Ngày dùng {lieu_chu} {dv}"
    if not so_con or not me:
        return (
            f"{dau}. Khai “1 {me or 'hộp'} có bao nhiêu {con or dv}” để tính ngày dùng."
        )
    if con and chuan(con) != chuan(dv):
        return f"{dau} — đơn vị trong câu ({dv}) khác đơn vị con ({con}), kiểm lại."
    ngay = int(Fraction(Decimal(so_con)) / lieu)
    return (
        f"{dau} → 1 {me} ({so_dep(Decimal(so_con))} {con or dv}) dùng được {ngay} ngày."
    )


async def doc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, thuoc_id: str
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT id::text, don_vi_ban, unit_price, cach_dung, don_vi_con, gia_con,"
            "       so_lieu_moi_don_vi_goc AS so_con"
            "  FROM public.drug_catalog WHERE clinic_id = $1::uuid AND id = $2::uuid",
            identity.clinic_id,
            thuoc_id,
        )
    if r is None:
        raise ValidationError("Không tìm thấy thuốc trong danh mục.")
    me = (r["don_vi_ban"] or "").strip()
    con = (r["don_vi_con"] or "").strip()
    return {
        "id": r["id"],
        "don_vi_me": me,
        "don_vi_con": con or None,
        "so_con": r["so_con"],
        "gia_me": int(r["unit_price"]) if r["unit_price"] is not None else None,
        "gia_con": int(r["gia_con"]) if r["gia_con"] is not None else None,
        "gia_con_tu_tinh": gia_con_tu_tinh(r["unit_price"], r["so_con"]),
        "xem_truoc": xem_truoc(r["cach_dung"] or "", me, con, r["so_con"]),
        "goi_y": list(DON_VI_CON_GOI_Y),
    }


async def luu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    thuoc_id: str,
    don_vi_con: str | None,
    so_con: Decimal | None,
    gia_con: Decimal | None,
) -> dict[str, Any]:
    """Ghi ba ô, có nhật ký trước/sau. Đổi giá con cần quyền sửa giá như giá mẹ."""
    from clinicai.services.pharmacy_service import ghi_nhat_ky

    con = " ".join((don_vi_con or "").split()) or None
    if con:
        kiem_ten_don_vi(con)
    if (so_con is None) != (con is None):
        raise ValidationError("Khai đủ cả đơn vị con và “1 mẹ có bao nhiêu con”.")
    async with pool.acquire() as conn, conn.transaction():
        cu = await conn.fetchrow(
            "SELECT don_vi_con, so_lieu_moi_don_vi_goc AS so_con, gia_con"
            "  FROM public.drug_catalog WHERE clinic_id = $1::uuid AND id = $2::uuid"
            "   FOR UPDATE",
            identity.clinic_id,
            thuoc_id,
        )
        if cu is None:
            raise ValidationError("Không tìm thấy thuốc trong danh mục.")
        if gia_con != cu["gia_con"]:
            await doi_quyen_sua_gia(conn, identity)
        await conn.execute(
            "UPDATE public.drug_catalog SET don_vi_con = $3,"
            " so_lieu_moi_don_vi_goc = $4, gia_con = $5"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            identity.clinic_id,
            thuoc_id,
            con,
            so_con,
            gia_con,
        )

        def _anh(con_: Any, so_: Any, gia_: Any) -> dict[str, str | None]:
            return {
                "don_vi_con": con_,
                "so_con": str(so_) if so_ is not None else None,
                "gia_con": str(gia_) if gia_ is not None else None,
            }

        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.drug_child_unit_set",
            aggregate_type="drug_catalog",
            aggregate_id=thuoc_id,
            payload={
                "truoc": _anh(cu["don_vi_con"], cu["so_con"], cu["gia_con"]),
                "sau": _anh(con, so_con, gia_con),
            },
        )
    return await doc(pool, identity=identity, thuoc_id=thuoc_id)


__all__ = ["DON_VI_CON_GOI_Y", "doc", "gia_con_tu_tinh", "luu", "xem_truoc"]
