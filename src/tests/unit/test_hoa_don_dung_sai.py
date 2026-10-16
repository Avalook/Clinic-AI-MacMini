"""Phiếu ĐÚNG / KHÔNG ĐÚNG (Tuyền 14/10/2026): mọi thứ lệch đường chuẩn."""

from typing import Any

from clinicai.services.hoa_don_projection import (
    hop_hinh_thuc,
    hop_nhom,
    lech_cua_phieu,
)


def _phieu(**kw: Any) -> dict[str, Any]:
    return {
        "visit_id": "v1",
        "trang_thai": "DA_THU",
        "hoan": [],
        "su_kien": [],
        "can_doi_soat": False,
        "giam_gia": 0,
        "hinh_thuc": "CASH",
        **kw,
    }


def test_phieu_duong_chuan_la_dung() -> None:
    assert lech_cua_phieu(_phieu(), {}) == []


def test_tung_ly_do_lech() -> None:
    assert lech_cua_phieu(_phieu(trang_thai="DA_HUY"), {}) == ["HUY"]
    assert lech_cua_phieu(_phieu(hoan=[{"so_tien": 1}]), {}) == ["HOAN"]
    assert lech_cua_phieu(_phieu(su_kien=[{"loai": "DOI_HINH_THUC"}]), {}) == [
        "DOI_HINH_THUC"
    ]
    assert lech_cua_phieu(_phieu(can_doi_soat=True), {}) == ["CAN_DOI_SOAT"]
    assert lech_cua_phieu(_phieu(), {"v1": {"GHI_NO"}}) == ["NO_KHACH"]
    assert lech_cua_phieu(_phieu(), {"v1": {"CK_CHUA_VE"}}) == ["NO_KHACH"]
    assert lech_cua_phieu(_phieu(), {"v1": {"CHUA_LAM"}}) == ["NO_PHONG_KHAM"]
    # Việc tồn của LƯỢT KHÁC không làm phiếu này lệch.
    assert lech_cua_phieu(_phieu(), {"v2": {"GHI_NO"}}) == []


def test_giam_gia_khong_phai_lech_nhung_co_bo_loc_rieng() -> None:
    p = _phieu(giam_gia=50_000)
    p["lech"] = lech_cua_phieu(p, {})
    assert p["lech"] == []
    assert hop_nhom(p, "dung") and hop_nhom(p, "giam_gia")
    assert not hop_nhom(p, "khong_dung")


def test_nhom_loc() -> None:
    huy = _phieu(trang_thai="DA_HUY")
    huy["lech"] = lech_cua_phieu(huy, {})
    assert hop_nhom(huy, "khong_dung") and hop_nhom(huy, "tra_lai")
    assert not hop_nhom(huy, "dung") and not hop_nhom(huy, "no_khach")
    # Nhóm rác / rỗng = không lọc.
    assert hop_nhom(huy, None) and hop_nhom(huy, "bậy")


def test_hinh_thuc() -> None:
    assert hop_hinh_thuc(_phieu(hinh_thuc="QR"), "TRANSFER")
    assert not hop_hinh_thuc(_phieu(hinh_thuc="QR"), "CASH")
    assert hop_hinh_thuc(_phieu(), None) and hop_hinh_thuc(_phieu(), "rác")
