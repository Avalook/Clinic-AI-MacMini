"""Đọc tồn theo đơn vị MẸ + CON (Tuyền 26/11): "còn 303 hộp + 50 viên".

Mẹ = đơn vị bán nguyên (hộp, lọ) khai ở Danh mục với "1 hộp = N [gốc]"; con = đơn vị
gốc kho đếm (viên, gói). Viên lẻ là phần còn của hộp đã bóc bán lẻ.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clinicai.services.don_vi_thuoc import BangDonVi, DonViBan


def me_lon(bang: BangDonVi) -> DonViBan | None:
    """Đơn vị MẸ để đọc tồn: mẹ đã đặt (hệ số > 1), không có thì đơn vị lớn nhất."""
    if bang.me in bang.dong and bang.dong[bang.me].he_so > 1:
        return bang.dong[bang.me]
    lon = [d for d in bang.dong.values() if d.he_so > 1]
    return max(lon, key=lambda x: x.he_so) if lon else None


def chu_me_con(bang: BangDonVi, tong_goc: Decimal) -> str | None:
    """Tồn về gốc → "303 hộp + 50 viên" / "3 hộp" / "7 viên". Chưa khai mẹ: None."""
    from clinicai.services.don_vi_thuoc import so_dep

    d = me_lon(bang)
    if d is None or tong_goc <= 0:
        return None
    nguyen = (tong_goc / d.he_so).to_integral_value(rounding=ROUND_FLOOR)
    du = tong_goc - nguyen * d.he_so
    if nguyen > 0 and du > 0:
        return f"{so_dep(nguyen)} {d.don_vi} + {so_dep(du)} {bang.goc}"
    if nguyen > 0:
        return f"{so_dep(nguyen)} {d.don_vi}"
    return f"{so_dep(du)} {bang.goc}"


def phan_me_con_cua_chu_ton(
    bang: BangDonVi, tong_goc: Decimal, co_lo_khac_goc: bool
) -> str | None:
    """Phần mẹ/con nối sau "= N gốc" của `BangDonVi.chu_ton`. Chưa đủ một mẹ thì bỏ
    (dòng "= N gốc" là đủ); đủ chẵn mà lô toàn gốc thì vẫn ghi."""
    d = me_lon(bang)
    if d and tong_goc >= d.he_so and (tong_goc % d.he_so or not co_lo_khac_goc):
        return chu_me_con(bang, tong_goc)
    return None


__all__ = ["chu_me_con", "me_lon", "phan_me_con_cua_chu_ton"]
