"""Hàm thuần của danh mục dịch vụ chuẩn 01/10/2026 (nhóm hàng, khoá chỉ định,
mã tự sinh) — đầu vào rác không ném."""

from __future__ import annotations

import unicodedata

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.config_service import (
    _nhom_hang,
    khoa_ten_dich_vu,
    ma_dich_vu_theo_ten,
)
from clinicai.services.danh_muc_dich_vu_service import (
    KHOA_CHUA_NHOM_VIEC,
    dong_danh_muc,
    ly_do_khoa_chi_dinh,
    nhom_hang_hien,
    thu_tu_nhom_hang,
)


def test_nhom_hang_hien_doi_dang_kiotviet_bo_ghi_chu_nhap_lieu() -> None:
    assert nhom_hang_hien("Siêu âm>>Siêu âm thai") == "Siêu âm › Siêu âm thai"
    assert nhom_hang_hien("  XN   thu hộ ") == "XN thu hộ"
    for rac in (None, "", "  ", 12, "KiotViet 26/09/2026", "Tiền khám · GIÁ GIẢ ĐỊNH"):
        assert nhom_hang_hien(rac) is None


def test_thu_tu_nhom_theo_file_phong_kham() -> None:
    ds = ["Thủ thuật", "Zeta", "XN thu hộ", "Siêu âm › Siêu âm thai", "Siêu âm"]
    assert sorted(ds, key=thu_tu_nhom_hang) == [
        "Siêu âm",
        "Siêu âm › Siêu âm thai",
        "XN thu hộ",
        "Thủ thuật",
        "Zeta",
    ]


def test_khoa_chi_dinh_khi_chua_nhom_viec() -> None:
    assert ly_do_khoa_chi_dinh({"node_code": None}) == KHOA_CHUA_NHOM_VIEC
    assert ly_do_khoa_chi_dinh({}) == KHOA_CHUA_NHOM_VIEC
    assert ly_do_khoa_chi_dinh({"node_code": "DICHVU-SIEUAM"}) is None


def test_nhom_hang_luu_dang_kiotviet_va_rac() -> None:
    assert _nhom_hang(" Siêu âm › Siêu âm thai ") == "Siêu âm>>Siêu âm thai"
    assert _nhom_hang("") is None and _nhom_hang(None) is None
    with pytest.raises(ValidationError):
        _nhom_hang("x" * 200)


def test_ma_tu_sinh_on_dinh_theo_ten() -> None:
    a = ma_dich_vu_theo_ten("  Liên   cầu B ")
    assert a == ma_dich_vu_theo_ten("liên cầu b")
    assert a.startswith("DV_") and len(a) == 13
    nfd = unicodedata.normalize("NFD", "Liền")
    assert khoa_ten_dich_vu(nfd) == khoa_ten_dich_vu("Liền")


def test_dong_danh_muc_doc_json_chuoi_va_gia_rac() -> None:
    d = dong_danh_muc(
        {
            "id": "x",
            "service_code": "A",
            "name": "A",
            "nhom": "Siêu âm>>Siêu âm thai",
            "unit_price": "9.0E+5",
            "phong": '[{"id": "r1", "ten": "SA 1", "doi_tac": false}]',
            "active": True,
        }
    )
    assert d["unit_price"] == 900000 and d["nhom_hien"] == "Siêu âm › Siêu âm thai"
    assert d["phong"] == [{"id": "r1", "ten": "SA 1", "doi_tac": False}]
    assert (
        dong_danh_muc({"id": 1, "service_code": "B", "name": "B", "phong": "{rac"})[
            "phong"
        ]
        == []
    )
    assert (
        dong_danh_muc({"id": 1, "service_code": "B", "name": "B", "unit_price": "abc"})[
            "unit_price"
        ]
        is None
    )
