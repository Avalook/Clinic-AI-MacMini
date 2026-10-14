"""Tiêu hao giữ số âm và thiếu kiểm đếm, không suy tồn sổ thành số đếm."""

from decimal import Decimal

import pytest


def test_tieu_hao_va_gia_tri() -> None:
    from clinicai.services.vat_tu_kho_service import tinh_tieu_hao

    assert tinh_tieu_hao(10, 8, 2, 5, 3000) == {
        "so_luong": Decimal(11),
        "gia_tri": Decimal(33000),
    }
    assert tinh_tieu_hao(2, 0, 0, 5, 100)["so_luong"] == -3


@pytest.mark.parametrize(
    "rac", [None, "", "rác", "NaN", "Infinity", True, "1e999999999"]
)
def test_thieu_dem_hoac_rac_tra_rong(rac: object) -> None:
    from clinicai.services.vat_tu_kho_service import tinh_tieu_hao

    assert tinh_tieu_hao(10, 8, 2, rac, 3000) is None
    assert tinh_tieu_hao(10, 8, 2, 5, rac) is None
