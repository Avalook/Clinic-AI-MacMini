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
    got = tom_tat_tai_chinh(bc)
    assert got["doanh_thu"] == 700_000
    assert got["doanh_thu_thuan"] == 650_000
    assert got["thuc_thu"] == 650_000
    assert got["hoan_tien_mat"] == 20_000
    assert got["hoan_chuyen_khoan"] == 30_000
    # F3 (14/10/2026): giảm giá có thật từ 13/10 — không còn "chưa có dữ liệu".
    assert got["giam_gia"] == 0
    assert got["chua_co_du_lieu"] == []
    assert bc["tong"]["hoan_cho"] == 100_000


def _ngay(**kw: Any) -> dict[str, Any]:
    """Báo cáo một ngày dựng tay: tiền thu / huỷ / hoàn theo hình thức + sổ nợ."""
    tm, ck = kw["tm"], kw["ck"]
    return {
        "tong": {
            "thu": tm["thu"] + ck["thu"],
            "huy": tm["huy"] + ck["huy"],
            "hoan": tm["hoan"] + ck["hoan"],
        },
        "theo_hinh_thuc": [{"ma": "CASH", **tm}, {"ma": "TRANSFER", **ck}],
        "giam_gia": {"giam": kw["giam"]},
        "so_no_ky": {
            "PHAI_THU": {
                "phat_sinh": kw["no"],
                "dieu_chinh": 0,
                "thu": {
                    "tong": kw["no_thu"],
                    "tien_mat": 0,
                    "chuyen_khoan": kw["no_thu"],
                    "giam_gia": 0,
                },
                "dau_ky": 0,
            },
            "PHAI_TRA": {"phat_sinh": 0, "giam": 0, "dau_ky": 0},
        },
    }


def test_bang_vang_doi_soat_hai_ngay() -> None:
    """Bảng vàng Tuyền duyệt 14/10 (kế hoạch mục 5.1).

    Ngày 1 — A: hoá đơn 1.000k, giảm 100k, trả 500k TM, nợ 400k · B: thu 300k CK,
    huỷ (nhầm), thu lại 300k TM · C: thu 200k CK, khách đổi ý, hoàn 200k CK.
    Ngày 2 — A trả nợ 400k CK."""
    d1 = tom_tat_tai_chinh(
        _ngay(
            tm={"thu": 800_000, "huy": 0, "hoan": 0},
            ck={"thu": 500_000, "huy": 300_000, "hoan": 200_000},
            giam=100_000,
            no=400_000,
            no_thu=0,
        )
    )["dong_tien"]
    assert d1["dong_tien_vao"] == 1_800_000
    assert d1["tra_lai"] == {"tong": 500_000, "tien_mat": 0, "chuyen_khoan": 500_000}
    assert d1["no"] == 400_000
    assert (d1["giam_gia"], d1["no_thu_duoc"]["tong"]) == (100_000, 0)
    assert d1["thuc_thu"] == {"tong": 800_000, "tien_mat": 800_000, "chuyen_khoan": 0}
    assert d1["doanh_thu_thuan"] == 1_200_000
    assert d1["khop"] is True

    d2 = tom_tat_tai_chinh(
        _ngay(
            tm={"thu": 0, "huy": 0, "hoan": 0},
            ck={"thu": 400_000, "huy": 0, "hoan": 0},
            giam=0,
            no=0,
            no_thu=400_000,
        )
    )["dong_tien"]
    assert d2["dong_tien_vao"] == 0
    assert d2["no_thu_duoc"]["chuyen_khoan"] == 400_000
    assert d2["thuc_thu"] == {"tong": 400_000, "tien_mat": 0, "chuyen_khoan": 400_000}
    assert d2["khop"] is True


def test_no_dong_bang_giam_100_thuc_thu_0() -> None:
    """Nợ 400k đóng bằng "thu 0đ, giảm 400k" (#415): không có tiền đi qua."""
    bc = _ngay(
        tm={"thu": 0, "huy": 0, "hoan": 0},
        ck={"thu": 0, "huy": 0, "hoan": 0},
        giam=400_000,
        no=0,
        no_thu=400_000,
    )
    bc["so_no_ky"]["PHAI_THU"]["thu"].update(chuyen_khoan=0, giam_gia=400_000)
    d = tom_tat_tai_chinh(bc)["dong_tien"]
    assert (d["dong_tien_vao"], d["thuc_thu"]["tong"], d["khop"]) == (0, 0, True)


def test_loc_mot_loai_khong_cong_so_no() -> None:
    bc = _ngay(
        tm={"thu": 300_000, "huy": 0, "hoan": 0},
        ck={"thu": 0, "huy": 0, "hoan": 0},
        giam=0,
        no=0,
        no_thu=0,
    )
    bc["so_no_ky"] = None
    d = tom_tat_tai_chinh(bc)["dong_tien"]
    assert (d["no"], d["no_thu_duoc"]["tong"], d["dong_tien_vao"]) == (0, 0, 300_000)


def test_bao_cao_rong_ra_so_khong() -> None:
    got = tom_tat_tai_chinh({})
    assert got["doanh_thu"] == 0
    assert got["hoan_tien_mat"] == 0
    assert got["thuc_thu"] == 0


def test_khong_con_dong_no_chua_thu_trong_ky() -> None:
    """Số trôi theo lần thu sau / ghi nợ lại — không phải dòng tiền đã ghi."""
    got = tom_tat_tai_chinh({})
    assert "no_chua_thu" not in got
    assert "no_chua_thu" not in got["pham_vi"]
