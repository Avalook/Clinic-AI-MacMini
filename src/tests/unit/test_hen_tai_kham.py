"""Hàm thuần của hẹn tái khám (29/09/2026) — đầu vào rác trả rỗng, không ném."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.events.consumers.nhac_tai_kham import noi_dung_chuong
from clinicai.services.hen_tai_kham_service import (
    cho_toi_luc_bao,
    doc_ngay_hen,
    han_goi,
    la_o_ngay_hen,
    ngay_hen_cua_luot,
    ten_can_kiem_tra,
    tinh_trang,
)


@pytest.mark.parametrize(
    "rac",
    [
        None,
        "",
        "   ",
        "hôm nào đó",
        "31/02/2026",
        "2026-13-01",
        20261010,
        [],
        {},
        True,
        {"gia_tri": None},
        {"gia_tri": 5},
        {"khong": "x"},
    ],
)
def test_ngay_hen_rac_tra_rong(rac: object) -> None:
    assert doc_ngay_hen(rac) is None


def test_ngay_hen_hai_dang() -> None:
    assert doc_ngay_hen({"gia_tri": "2026-10-20"}) == date(2026, 10, 20)
    assert doc_ngay_hen("20/10/2026") == date(2026, 10, 20)


def test_han_goi_bay_ngay_truoc_va_khong_qua_han_ngay() -> None:
    hom_nay = date(2026, 9, 29)
    assert han_goi(date(2026, 10, 29), hom_nay) == date(2026, 10, 22)
    # Hẹn gần hơn 7 ngày → gọi từ hôm nay, không đỏ "quá hạn".
    assert han_goi(date(2026, 10, 2), hom_nay) == hom_nay


def test_cho_toi_luc_bao_07h_gio_vn() -> None:
    bay_gio = datetime(2026, 9, 29, 1, 0, tzinfo=timezone.utc)  # 08:00 VN
    assert cho_toi_luc_bao(date(2026, 9, 29), bay_gio) == timedelta(0)
    moc = datetime(2026, 10, 22, 7, 0, tzinfo=CLINIC_TZ)
    assert cho_toi_luc_bao(date(2026, 10, 22), bay_gio) == moc - bay_gio


def test_ngay_hen_cua_luot_lay_ngay_hop_le_muon_nhat() -> None:
    phieu = [
        ("PK", {"pk_follow_date": {"gia_tri": "rác"}, "pk_dx": {"gia_tri": "x"}}),
        ("NT", {"nt_follow_date": {"gia_tri": "2026-11-01"}}),
        ("SK", {"sk_follow_date": {"gia_tri": "2026-10-15"}}),
    ]
    assert ngay_hen_cua_luot(phieu) == (date(2026, 11, 1), "NT")
    assert ngay_hen_cua_luot([]) == (None, None)
    assert la_o_ngay_hen("pk_follow_date") and not la_o_ngay_hen("pk_follow_note")


def test_ten_can_kiem_tra_bo_qua_ma_la() -> None:
    dl = {"pk_follow_tests": {"gia_tri": ["pk_follow_tests_4", "la", 7]}}
    assert ten_can_kiem_tra("PK", dl) == ["DXA"]
    assert ten_can_kiem_tra("KHONG_CO", dl) == []
    assert ten_can_kiem_tra(None, dl) == []
    assert ten_can_kiem_tra("PK", {"pk_follow_tests": {"gia_tri": "Hormone"}}) == []


def test_tinh_trang() -> None:
    d = date(2026, 9, 29)
    assert tinh_trang("CHO_GOI", None, d + timedelta(days=1), d) == "CHUA_TOI_HAN"
    assert tinh_trang("CHO_GOI", None, d, d) == "CHO_GOI"
    assert tinh_trang("DA_GOI", None, d, d) == "DA_GOI"
    assert tinh_trang("KHONG_CAN", "DA_CO_LICH", d, d) == "DA_CO_LICH"
    assert tinh_trang("KHONG_CAN", "BS_BO_HEN", d, d) == "DA_HUY"
    assert tinh_trang("KHONG_CAN", None, None, d) == "KHONG_CAN"


def test_noi_dung_chuong_du_truong_va_thieu_thi_bo() -> None:
    assert noi_dung_chuong(None) == "Gọi khách chốt giờ tái khám."
    cau = noi_dung_chuong(
        {
            "bac_si": "Lan",
            "loai_kham": "Nội tiết",
            "chan_doan": "PCOS",
            "can_kiem_tra": ["Hormone", "Siêu âm"],
            "ghi_chu_bac_si": "nhịn ăn",
        }
    )
    for mau in ("BS Lan", "Nội tiết", "CĐ: PCOS", "Hormone, Siêu âm", "nhịn ăn"):
        assert mau in cau
