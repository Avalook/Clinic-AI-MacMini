"""Hàm thuần `thuoc.gia_dong.tinh_gia_dong` — không DB (đơn vị mẹ/con, PR A)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from clinicai.services.don_vi_thuoc import BangDonVi, DonViBan
from clinicai.services.thuoc.gia_dong import (
    GiaDong,
    so_luong_sach,
    tinh_gia_dong,
)


def _bang(*, me: str = "", gia_goc: Decimal | None = None) -> BangDonVi:
    """Ecanix: gốc viên, hộp 60 viên 550.000đ, vỉ 10 viên chưa có giá."""
    return BangDonVi(
        goc="viên",
        gia_goc=gia_goc,
        dong={
            "hộp": DonViBan("hộp", Decimal(60), Decimal(550_000), True),
            "vỉ": DonViBan("vỉ", Decimal(10), None, False),
        },
        me=me,
    )


def _gia(bang: BangDonVi, dv: str | None, gia_goc: Decimal | None = None) -> GiaDong:
    return tinh_gia_dong(bang, dv, co_thuoc=True, gia_danh_muc=gia_goc)


def test_trong_khong_co_me_la_goc_nhu_cu() -> None:
    g = _gia(_bang(), None, Decimal(9_000))
    assert (g.don_vi, g.gia, g.he_so, g.van_de) == ("", (Decimal(9_000),), None, None)


def test_trong_co_me_la_me() -> None:
    g = _gia(_bang(me="hộp"), "  ")
    assert (g.don_vi, g.don_gia, g.he_so) == ("hộp", Decimal(550_000), Decimal(60))
    assert g.thanh_tien(1) == 550_000


@pytest.mark.parametrize(("so", "tien"), [(10, 91_667), (60, 550_000), (1, 9_167)])
def test_vien_tu_chia_tu_gia_hop(so: int, tien: int) -> None:
    g = _gia(_bang(me="hộp"), "viên")
    assert g.tu_chia and g.gia_goi_y_con == 9_200
    assert g.thanh_tien(so) == tien


def test_vien_co_gia_khai_thi_dung_gia_khai() -> None:
    g = _gia(_bang(me="hộp"), "viên", Decimal(10_000))
    assert not g.tu_chia and g.thanh_tien(10) == 100_000


def test_khong_co_me_thi_khong_tu_chia_giu_khong_gia() -> None:
    g = _gia(_bang(), "viên")
    assert g.don_gia is None and not g.tu_chia, "không giá thì không thu (chủ ý)"


def test_vi_chua_gia_nho_hon_me_tu_chia_lon_hon_thi_khong() -> None:
    g = _gia(_bang(me="hộp"), "vỉ")
    assert g.thanh_tien(1) == 91_667 and g.he_so == 10
    # Mẹ là vỉ (chưa giá) → hộp lớn hơn mẹ: dùng giá hộp đã khai, không chia.
    assert _gia(_bang(me="vỉ"), "hộp").don_gia == 550_000
    assert _gia(_bang(), "vỉ").van_de, "không mẹ có giá: vẫn chặn như cũ"


def test_don_vi_chua_khai_giu_canh_bao_va_gia_goc() -> None:
    g = _gia(_bang(me="hộp", gia_goc=Decimal(9_000)), "lọ", Decimal(9_000))
    assert g.canh_bao and "“lọ” chưa khai" in g.canh_bao
    assert g.don_gia == 9_000 and g.van_de is None


def test_khong_gan_thuoc_kho_thi_khong_gia() -> None:
    g = tinh_gia_dong(_bang(me="hộp"), None, co_thuoc=False, gia_danh_muc=Decimal(1))
    assert g.gia == () and g.don_vi == "hộp"


@pytest.mark.parametrize("rac", [None, "", "abc", "-1", -5, "NaN", "inf", True, [1]])
def test_so_luong_rac_tra_rong_khong_nem(rac: Any) -> None:
    assert so_luong_sach(rac) is None
    assert _gia(_bang(me="hộp"), "viên").thanh_tien(rac) is None


def test_so_luong_viet_phay_va_so_0() -> None:
    assert so_luong_sach("1,5") == Decimal("1.5")
    assert _gia(_bang(me="hộp"), "hộp").thanh_tien(0) == 0
