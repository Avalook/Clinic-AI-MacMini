"""Tổng việc tiền không bị cắt theo danh sách chi tiết."""

from clinicai.services.bao_cao_viec_tien_service import _gom


def test_tong_van_day_du_khi_chi_tiet_bi_cat() -> None:
    kq = _gom(
        [{"id": str(i), "so_tien": 1000} for i in range(101)],
        pham_vi_loai="dich_vu",
    )
    assert kq["so_phieu"] == 101
    assert kq["so_tien"] == 101000
    assert len(kq["ds"]) == 100
    assert kq["bi_cat"] is True


def test_khong_co_viec_la_so_khong_va_danh_sach_rong() -> None:
    kq = _gom([], pham_vi_loai="dich_vu_va_thuoc")
    assert kq["so_phieu"] == kq["so_tien"] == 0
    assert kq["ds"] == []
    assert kq["bi_cat"] is False
