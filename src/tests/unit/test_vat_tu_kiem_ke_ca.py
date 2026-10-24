"""Quy tắc thuần của kiểm kê vật tư đầu/cuối ca theo phòng."""

from decimal import Decimal

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services import vat_tu_kiem_ke_ca_service as kk


@pytest.mark.parametrize("raw", ["abc", "-1", "NaN", "Infinity", True, "1e20"])
def test_so_dem_khong_hop_le_duoc_tu_choi(raw: object) -> None:
    with pytest.raises(ValidationError):
        kk.so_dem(raw)


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_so_dem_rong_la_chua_dem(raw: object) -> None:
    assert kk.so_dem(raw, rong_duoc=True) is None


def test_lech_la_so_dem_thuc_te_tru_ton_so() -> None:
    assert kk.tinh_lech(Decimal("12.500"), Decimal("10")) == Decimal("-2.500")


def test_so_dem_chap_nhan_so_thap_phan_hop_le() -> None:
    assert kk.so_dem("2,375") == Decimal("2.375")
