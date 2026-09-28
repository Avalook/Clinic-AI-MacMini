"""Hàm thuần của gói quầy / kho đợt 3 (27/09/2026) — không cần DB."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.services.day_noi import DAY
from clinicai.services.luot_kham_rules import cau_giu_dieu_phoi
from clinicai.services.luot_treo import dieu_kien_luot_treo
from clinicai.services.service_routing_service import (
    CHO_XEP_CHUA_CHON_PHONG,
    CHO_XEP_KHONG_CO_PHONG,
    CHO_XEP_PHONG_DU_KIEN_HONG,
    cau_cho_xep_phong,
    chon_phong_h4,
)

UV: list[dict[str, Any]] = [
    {"room_id": "vang-nhat", "rank": 1},
    {"room_id": "dong-hon", "rank": 2},
]


# ── C7b: mã giữ điều phối → câu tiếng Việt ──────────────────────────────────


@pytest.mark.parametrize(
    "ma", ["ROUTE_NOT_DECIDED", "PLAN_NOT_APPLIED", "HELD_UNTIL_ROUND"]
)
def test_ma_giu_co_cau_va_viec_can_lam_khong_lo_ma_tho(ma: str) -> None:
    cau = cau_giu_dieu_phoi(ma)
    assert ma not in cau
    assert "Việc cần làm" in cau


@pytest.mark.parametrize("rac", [None, "", "KHONG_CO_MA_NAY", 123, ["x"]])
def test_ma_rac_van_co_cau_dung_duoc(rac: Any) -> None:
    cau = cau_giu_dieu_phoi(rac)
    assert cau and "Việc cần làm" in cau


# ── C7c + C9: H4 chọn phòng ──────────────────────────────────────────────────


def test_mac_dinh_phong_du_kien_thang_neu_con_nhan() -> None:
    assert chon_phong_h4(UV, "dong-hon", chi_ap_phong_du_kien=False) == (
        "dong-hon",
        None,
    )


def test_mac_dinh_phong_du_kien_hong_thi_vang_nhat() -> None:
    assert chon_phong_h4(UV, "da-tam-ngung", chi_ap_phong_du_kien=False) == (
        "vang-nhat",
        None,
    )
    assert chon_phong_h4(UV, None, chi_ap_phong_du_kien=False) == ("vang-nhat", None)


def test_mac_dinh_khong_phong_nao_thi_cho_xep() -> None:
    assert chon_phong_h4([], None, chi_ap_phong_du_kien=False) == (
        None,
        CHO_XEP_KHONG_CO_PHONG,
    )


def test_chi_ap_khong_tu_chon_phong_vang_nhat() -> None:
    assert chon_phong_h4(UV, None, chi_ap_phong_du_kien=True) == (
        None,
        CHO_XEP_CHUA_CHON_PHONG,
    )
    assert chon_phong_h4(UV, "", chi_ap_phong_du_kien=True) == (
        None,
        CHO_XEP_CHUA_CHON_PHONG,
    )


def test_chi_ap_phong_du_kien_tam_ngung_thi_cho_le_tan() -> None:
    assert chon_phong_h4(UV, "da-tam-ngung", chi_ap_phong_du_kien=True) == (
        None,
        CHO_XEP_PHONG_DU_KIEN_HONG,
    )
    assert chon_phong_h4([], "da-tam-ngung", chi_ap_phong_du_kien=True) == (
        None,
        CHO_XEP_PHONG_DU_KIEN_HONG,
    )


def test_chi_ap_phong_du_kien_con_nhan_thi_xep_dung_phong() -> None:
    assert chon_phong_h4(UV, "dong-hon", chi_ap_phong_du_kien=True) == (
        "dong-hon",
        None,
    )


@pytest.mark.parametrize(
    "ly_do",
    [CHO_XEP_KHONG_CO_PHONG, CHO_XEP_CHUA_CHON_PHONG, CHO_XEP_PHONG_DU_KIEN_HONG],
)
def test_cau_cho_xep_phong_co_viec_can_lam(ly_do: str) -> None:
    assert "Việc cần làm" in cau_cho_xep_phong(ly_do)


@pytest.mark.parametrize("rac", [None, "", "LA", 0])
def test_cau_cho_xep_phong_ly_do_rac(rac: Any) -> None:
    assert cau_cho_xep_phong(rac)


def test_day_chi_ap_mac_dinh_tat_hien_o_man_day_noi() -> None:
    d = DAY["h4_chi_ap_phong_du_kien"]
    assert d.mac_dinh is False and d.kieu == "bat_tat"


# ── C8: một câu lượt treo ─────────────────────────────────────────────────────


def test_dieu_kien_luot_treo_loai_da_check_out_va_dung_gio_vn() -> None:
    sql = dieu_kien_luot_treo("v")
    assert "v.closed_at IS NULL" in sql
    assert "v.status IN ('OPEN', 'IN_PROGRESS')" in sql
    assert "Asia/Ho_Chi_Minh" in sql
    assert dieu_kien_luot_treo("vq").count("vq.") == 4


@pytest.mark.parametrize("rac", ["", "v; DROP TABLE visit", "V", "1v", None])
def test_bi_danh_la_bi_tu_choi(rac: Any) -> None:
    with pytest.raises(ValueError):
        dieu_kien_luot_treo(rac)
