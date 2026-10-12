from typing import Any

from clinicai.services.tom_tat_tai_chinh_service import tom_tat_tai_chinh


def test_tach_doanh_thu_va_tien_thu_khong_gia_lap_giam_gia() -> None:
    bc: dict[str, Any] = {
        "tong": {"so_phieu_thu": 3, "thuc_thu": 650_000, "hoan_cho": 100_000},
        "hang_hoa": {
            "dich_vu": {"tong": {"doanh_thu": 500_000, "doanh_thu_thuan": 450_000}},
            "thuoc": {"tong": {"doanh_thu": 200_000, "doanh_thu_thuan": 200_000}},
        },
        "theo_hinh_thuc": [
            {"ma": "CASH", "hoan": 20_000},
            {"ma": "TRANSFER", "hoan": 25_000},
            {"ma": "QR", "hoan": 5_000},
        ],
    }
    got = tom_tat_tai_chinh(bc, no_trong_khoang=75_000)
    assert got["doanh_thu"] == 700_000
    assert got["doanh_thu_thuan"] == 650_000
    assert got["thuc_thu"] == 650_000
    assert got["hoan_tien_mat"] == 20_000
    assert got["hoan_chuyen_khoan"] == 30_000
    assert got["no_chua_thu"] == 75_000
    assert got["giam_gia"] is None
    assert got["chua_co_du_lieu"] == ["giam_gia"]
    assert bc["tong"]["hoan_cho"] == 100_000


def test_no_khong_co_nguon_khong_bien_thanh_zero() -> None:
    got = tom_tat_tai_chinh({}, no_trong_khoang=None)
    assert got["no_chua_thu"] is None
    assert got["doanh_thu"] == 0
    assert got["hoan_tien_mat"] == 0
    assert got["chua_co_du_lieu"] == ["giam_gia", "no_chua_thu"]
