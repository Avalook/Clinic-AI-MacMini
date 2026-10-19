"""Quyền kinh doanh độc lập với giá và trạng thái của vật tư."""

import pytest

from clinicai.services.danh_muc_dich_vu_service import dong_vat_tu
from clinicai.services.vat_tu_service import ly_do_khong_ban


@pytest.mark.parametrize("kinh_doanh", [False, None])
def test_vat_tu_van_hanh_khong_duoc_ban(kinh_doanh: bool | None) -> None:
    ly_do = ly_do_khong_ban(active=True, don_gia=300000, kinh_doanh=kinh_doanh)
    assert ly_do is not None
    assert "không được phép kinh doanh" in ly_do


def test_vat_tu_duoc_kinh_doanh_can_co_gia_va_dang_dung() -> None:
    assert ly_do_khong_ban(active=True, don_gia=300000, kinh_doanh=True) is None
    assert ly_do_khong_ban(active=True, don_gia=None, kinh_doanh=True)
    assert ly_do_khong_ban(active=False, don_gia=300000, kinh_doanh=True)


def test_danh_muc_kho_giu_vat_tu_khong_ban_nhung_danh_dau_dung() -> None:
    row = dong_vat_tu(
        {
            "id": "test",
            "service_code": "VT",
            "name": "Gạc",
            "active": True,
            "unit_price": 300000,
            "kinh_doanh_vat_tu": False,
        }
    )
    assert row["ban_duoc"] is False
    assert "không được phép kinh doanh" in row["ly_do_khong_ban"]
