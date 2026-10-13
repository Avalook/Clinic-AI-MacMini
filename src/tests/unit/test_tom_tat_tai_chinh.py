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
    # Báo cáo không có khối giảm giá (nguồn cũ) → "chưa có dữ liệu", không bịa 0.
    assert got["giam_gia"] is None
    assert got["chua_co_du_lieu"] == ["giam_gia"]
    assert bc["tong"]["hoan_cho"] == 100_000


def test_no_khong_co_nguon_khong_bien_thanh_zero() -> None:
    got = tom_tat_tai_chinh({}, no_trong_khoang=None)
    assert got["no_chua_thu"] is None
    assert got["doanh_thu"] == 0
    assert got["hoan_tien_mat"] == 0
    assert got["chua_co_du_lieu"] == ["giam_gia", "no_chua_thu"]


def test_giam_gia_lay_tu_so_giam_gia_cua_bao_cao_khong_tru_lai() -> None:
    bc: dict[str, Any] = {
        "hang_hoa": {
            "dich_vu": {"tong": {"doanh_thu": 450_000, "doanh_thu_thuan": 450_000}}
        },
        "giam_gia": {"so_phieu": 2, "tong_goc": 600_000, "giam": 150_000, "dong": []},
    }
    got = tom_tat_tai_chinh(bc, no_trong_khoang=0)
    assert got["giam_gia"] == 150_000
    assert got["chua_co_du_lieu"] == []
    # Doanh thu đã là số sau giảm — giảm giá không bị trừ thêm lần nữa.
    assert got["doanh_thu"] == got["doanh_thu_thuan"] == 450_000
    bc["giam_gia"] = {"so_phieu": 0, "tong_goc": 0, "giam": 0, "dong": []}
    assert tom_tat_tai_chinh(bc, no_trong_khoang=0)["giam_gia"] == 0
