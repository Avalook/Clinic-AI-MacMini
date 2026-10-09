"""Báo cáo CA CỦA TÔI — các hàm thuần (Tuyền 09/10/2026).

Quyền xem suy từ lịch trực: (ca, cơ sở) của dòng lịch hôm nay; FULL = ba ca;
REJECTED bỏ; nhãn lạ đóng; cơ sở trống chỉ lấp được khi phòng khám MỘT cơ sở.
Đầu vào rác (ca, cơ sở) → không được xem, không ném.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from clinicai.core.shifts import ca_xem_duoc
from clinicai.permissions.catalogue import (
    KHOI_CHI_QUAN_LY_TRUONG_CA,
    KHOI_MO_FULL,
    PRESET,
)
from clinicai.services.bao_cao_ca_cua_toi_service import (
    AN_VOI_NHAN_VIEN,
    ca_cua_luc,
    cat_cho_nhan_vien,
    chon_cap,
    ds_ca_duoc_xem,
)
from clinicai.services.cong_no_service import gom_no_trong_khung

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


def _d(shift: Any, co_so: Any = A, status: Any = "APPROVED") -> dict[str, Any]:
    return {"shift": shift, "status": status, "co_so": co_so}


# ── ca_xem_duoc ─────────────────────────────────────────────────────────────


def test_mot_ca_mot_co_so() -> None:
    assert ca_xem_duoc([_d("SANG")]) == {("SANG", A)}


def test_full_la_ca_ba_ca() -> None:
    assert ca_xem_duoc([_d("FULL", B)]) == {("SANG", B), ("CHIEU", B), ("TOI", B)}


def test_bo_dong_rejected_va_giu_dong_cho_duyet() -> None:
    assert ca_xem_duoc(
        [_d("SANG", status="REJECTED"), _d("TOI", status="PENDING")]
    ) == {("TOI", A)}


def test_nhan_ca_la_hoac_rac_thi_dong_khong_mo() -> None:
    assert ca_xem_duoc([_d("DEM"), _d(None), _d(""), _d(123), _d("full ")]) == {
        ("SANG", A),
        ("CHIEU", A),
        ("TOI", A),
    }  # chỉ "full " (chuẩn hoá được) mới mở
    assert ca_xem_duoc([_d("DEM")]) == set()


def test_co_so_trong_lay_mac_dinh_khi_mot_co_so() -> None:
    assert ca_xem_duoc([_d("CHIEU", None)]) == set()
    assert ca_xem_duoc([_d("CHIEU", None)], A) == {("CHIEU", A)}
    # Dòng có cơ sở thì không bị mặc định đè.
    assert ca_xem_duoc([_d("CHIEU", B)], A) == {("CHIEU", B)}


def test_hai_ca_hai_co_so() -> None:
    assert ca_xem_duoc([_d("SANG", A), _d("TOI", B)]) == {("SANG", A), ("TOI", B)}


# ── chon_cap ────────────────────────────────────────────────────────────────

DUOC = {("SANG", A), ("TOI", A), ("TOI", B)}


def test_khong_gui_ca_lay_ca_hien_tai_neu_duoc_xem() -> None:
    assert chon_cap(DUOC, None, None, "TOI") == ("TOI", A)
    # Ca hiện tại không được xem → ca sớm nhất được xem.
    assert chon_cap(DUOC, "", None, "CHIEU") == ("SANG", A)
    assert chon_cap(DUOC, None, None, None) == ("SANG", A)


def test_gui_dung_cap_duoc_xem() -> None:
    assert chon_cap(DUOC, "toi", B, "SANG") == ("TOI", B)
    assert chon_cap(DUOC, "SANG", f" {A} ", None) == ("SANG", A)


@pytest.mark.parametrize(
    ("ca", "co_so"),
    [
        ("CHIEU", None),  # ca không trực
        ("SANG", B),  # ca có trực nhưng cơ sở khác
        ("ĐÊM", None),  # ca rác
        ("SANG", "khong-phai-uuid"),  # cơ sở rác
        ("x" * 500, "y" * 500),
    ],
)
def test_khong_duoc_xem_tra_none_khong_nem(ca: Any, co_so: Any) -> None:
    assert chon_cap(DUOC, ca, co_so, "SANG") is None


def test_khong_co_ca_nao() -> None:
    assert chon_cap(set(), None, None, "SANG") is None


# ── ca_cua_luc / ds tab ─────────────────────────────────────────────────────


def test_ca_cua_luc_theo_khung_chot_ca_va_settings_rac() -> None:
    # Khung chốt mặc định: SANG 00:00–14:00, CHIEU 14:00–17:30, TOI 17:30–24:00.
    assert ca_cua_luc(13 * 60 + 30, None) == "SANG"  # nghỉ trưa thuộc ca sáng
    assert ca_cua_luc(14 * 60, "{rác") == "CHIEU"
    assert ca_cua_luc(17 * 60 + 30, {"ca_lam_viec": 5}) == "TOI"
    assert ca_cua_luc(0, None) == "SANG"


def test_ds_ca_duoc_xem_theo_thu_tu_ca() -> None:
    ds = ds_ca_duoc_xem({("TOI", A), ("SANG", B)}, {A: "Kim Ngưu", B: "Hào Nam"})
    assert [(x["ca"], x["ten_co_so"]) for x in ds] == [
        ("SANG", "Hào Nam"),
        ("TOI", "Kim Ngưu"),
    ]


# ── Cắt payload ─────────────────────────────────────────────────────────────


def test_cat_bo_theo_nguoi_thu_theo_co_so_va_so_ca_ngay() -> None:
    bc = {k: [1] for k in AN_VOI_NHAN_VIEN} | {
        "tong": {"thuc_thu": 1},
        "theo_hinh_thuc": [],
        "theo_loai": [],
        "hang_hoa": {},
        "hoan_huy": [],
        "no_trong_ca": {},
    }
    ra = cat_cho_nhan_vien(bc)
    assert not set(AN_VOI_NHAN_VIEN) & set(ra)
    assert {"theo_nguoi_thu", "theo_co_so"} <= set(AN_VOI_NHAN_VIEN)
    for giu in ("tong", "theo_hinh_thuc", "theo_loai", "hang_hoa", "hoan_huy"):
        assert giu in ra
    assert "no_trong_ca" in ra
    assert "theo_nguoi_thu" in bc, "không sửa bản gốc"


# ── Nợ trong ca ─────────────────────────────────────────────────────────────


def test_gom_no_trong_khung() -> None:
    luc = datetime(2026, 10, 9, 3, 0, tzinfo=UTC)
    dong = [
        {"nhom": "ghi_moi", "id": "1", "visit_id": "v1", "luc": luc, "so_tien": 200}
        | {"trang_thai": "DA_THU", "ly_do": "chưa mang tiền", "nguoi": "Lan"}
        | {"khach": "Chị A", "ma_bn": "BN1"},
        {"nhom": "thu_lai", "id": "1", "visit_id": "v1", "luc": luc, "so_tien": 200}
        | {"trang_thai": "DA_THU", "ly_do": None, "nguoi": None}
        | {"khach": "Chị A", "ma_bn": "BN1"},
        {"nhom": "huy", "id": "2", "visit_id": "v2", "luc": luc, "so_tien": None}
        | {"trang_thai": "HUY", "ly_do": "bấm nhầm", "nguoi": "Lan"}
        | {"khach": "Chị B", "ma_bn": "BN2"},
        {"nhom": "la", "id": "3", "visit_id": "v3", "luc": None, "so_tien": 9}
        | {"trang_thai": "", "ly_do": "", "nguoi": "", "khach": "", "ma_bn": ""},
    ]
    ra = gom_no_trong_khung(dong)
    assert (ra["ghi_moi"]["so"], ra["ghi_moi"]["so_tien"]) == (1, 200)
    assert (ra["thu_lai"]["so"], ra["thu_lai"]["so_tien"]) == (1, 200)
    assert (ra["huy"]["so"], ra["huy"]["so_tien"]) == (1, 0)
    assert ra["ghi_moi"]["ds"][0]["khach"] == "Chị A"
    assert ra["huy"]["ds"][0]["luc"] == luc.isoformat()


def test_gom_no_rong() -> None:
    ra = gom_no_trong_khung([])
    assert {k: v["so"] for k, v in ra.items()} == {"ghi_moi": 0, "thu_lai": 0, "huy": 0}


# ── Gói mẫu: Báo cáo chỉ Quản lý + Trưởng ca ────────────────────────────────


def test_goi_mau_bao_cao_chi_quan_ly_va_truong_ca() -> None:
    assert "bao_cao" not in KHOI_MO_FULL
    co = sorted(v for v, ks in PRESET.items() if KHOI_CHI_QUAN_LY_TRUONG_CA & set(ks))
    assert co == ["MANAGEMENT", "TRUONG_CA"]
