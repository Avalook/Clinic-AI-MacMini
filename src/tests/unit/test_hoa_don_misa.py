"""Dấu vân tay hoá đơn xuất MISA (G5c): hàm thuần."""

from typing import Any

from clinicai.services.hoa_don_misa_doc import (
    LY_DO_KHONG_CON,
    LY_DO_NGUOI_MUA,
    LY_DO_NOI_DUNG,
    dau_van_tay,
    so_sanh,
)


def _hd(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "la_hd_cong_ty": False,
        "ten_khach": "Nguyễn Thị A",
        "dia_chi": "12 Kim Ngưu",
        "email": "a@x.vn",
        "so_dien_thoai": "0901234567",
        "cccd": "001190000001",
        "ngay": "12/10/2026",
        "tong": 300_000,
        "dong": [
            {
                "ten": "Khám",
                "dvt": "Lần",
                "so_luong": 1,
                "don_gia": 300_000,
                "thanh_tien": 300_000,
                "thue_suat": None,
            }
        ],
    }
    return {**base, **kw}


def _cong_ty(**kw: Any) -> dict[str, Any]:
    base = {
        "la_hd_cong_ty": True,
        "ten_cong_ty": "Công ty Hoa Sen",
        "dia_chi": "99 Trần Duy Hưng",
        "ma_so_thue": "0123456789",
        "email": "kt@hoasen.vn",
        "nguoi_mua": "",
    }
    return _hd(**{**base, **kw})


def _luu(hd: dict[str, Any]) -> dict[str, str]:
    nm, nd = dau_van_tay(hd)
    return {"dau_nguoi_mua": nm, "dau_noi_dung": nd}


def test_giong_nhau_thi_khong_doi() -> None:
    for hd in (_hd(), _cong_ty()):
        assert so_sanh(_luu(hd), dau_van_tay(hd)) == []
        assert dau_van_tay(hd) == dau_van_tay(dict(hd))


def test_chua_xuat_thi_khong_noi_gi() -> None:
    assert so_sanh(None, dau_van_tay(_hd())) == []
    assert so_sanh(None, None) == []


def test_khong_con_trong_ky() -> None:
    assert so_sanh(_luu(_hd()), None) == [LY_DO_KHONG_CON]


def test_doi_cong_ty_chi_lech_nguoi_mua() -> None:
    cu = _luu(_cong_ty())
    for truong, moi in (
        ("ten_cong_ty", "Công ty Hoa Sen 2"),
        ("dia_chi", "Địa chỉ mới"),
        ("ma_so_thue", "9999999999"),
        ("email", "khac@hoasen.vn"),
        ("nguoi_mua", "Trần Văn B"),
    ):
        assert so_sanh(cu, dau_van_tay(_cong_ty(**{truong: moi}))) == [LY_DO_NGUOI_MUA]


def test_doi_tien_hoac_dong_chi_lech_noi_dung() -> None:
    cu = _luu(_hd())
    assert so_sanh(cu, dau_van_tay(_hd(tong=250_000))) == [LY_DO_NOI_DUNG]
    dong = [{**_hd()["dong"][0], "thanh_tien": 250_000}]
    assert so_sanh(cu, dau_van_tay(_hd(dong=dong))) == [LY_DO_NOI_DUNG]
    assert so_sanh(cu, dau_van_tay(_hd(ngay="13/10/2026"))) == [LY_DO_NOI_DUNG]
    # Cả hai cùng đổi → hai lý do.
    ca_hai = _hd(tong=1, ten_khach="Người khác")
    assert so_sanh(cu, dau_van_tay(ca_hai)) == [LY_DO_NGUOI_MUA, LY_DO_NOI_DUNG]


def test_hoa_don_ca_nhan_doi_thong_tin_khach_thi_bao() -> None:
    cu = _luu(_hd())
    for truong, moi in (
        ("ten_khach", "Tên khác"),
        ("dia_chi", "Nhà mới"),
        ("email", "moi@x.vn"),
        ("so_dien_thoai", "0911111111"),
        ("cccd", "001190000002"),
    ):
        assert so_sanh(cu, dau_van_tay(_hd(**{truong: moi}))) == [LY_DO_NGUOI_MUA]


def test_thue_suat_khong_thuoc_dau_van_tay() -> None:
    """Kế toán đặt / sửa thuế khi tải file không phải thay đổi của hoá đơn."""
    dong = [{**_hd()["dong"][0], "thue_suat": "8", "thue_nguon": "dong"}]
    assert dau_van_tay(_hd(dong=dong)) == dau_van_tay(_hd())


def test_thong_tin_ca_nhan_khong_lam_lech_hoa_don_cong_ty() -> None:
    """Hoá đơn công ty không đọc tên/SĐT/CCCD khách → khách đổi số không báo oan."""
    cu = _luu(_cong_ty())
    moi = _cong_ty(ten_khach="Tên khác", so_dien_thoai="0911111111", cccd="x")
    assert so_sanh(cu, dau_van_tay(moi)) == []
