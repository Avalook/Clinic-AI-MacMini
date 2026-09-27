"""Luật thuần "BUỔI KHÁM" (27/09/2026, đợt 3) — dây H1 và sinh hiệu cùng buổi.

Góp ý phòng khám: khách đăng ký thêm dịch vụ lần 2 trong buổi bị đẩy về Đo
sinh hiệu. Luật: ``(di_thang_phong OR cung_buoi_da_kham) AND co_mang_sang →
DỊCH VỤ``; sinh hiệu của buổi dùng lại được (trừ khách có thai thiếu cân/cao).
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.services import luot_kham_rules as rules
from clinicai.services.day_noi import DAY


def _duong(**kw: Any) -> str:
    mac_dinh: dict[str, Any] = {
        "qua_tu_van": False,
        "di_thang_phong": False,
        "cung_buoi_da_kham": False,
        "co_mang_sang": False,
        "quen_vao_thang": False,
    }
    return rules.duong_sau_check_in(**{**mac_dinh, **kw})[0]


# --- duong_sau_check_in -----------------------------------------------------


@pytest.mark.parametrize(
    ("di_thang_phong", "cung_buoi", "mang_sang", "mong"),
    [
        (True, False, True, rules.SERVICES),  # lịch thủ thuật có hẹn sẵn
        (False, True, True, rules.SERVICES),  # lượt 2 cùng buổi, đã khám
        (True, True, True, rules.SERVICES),
        (False, True, False, rules.TU_VAN),  # cùng buổi nhưng không có việc sẵn
        (True, False, False, rules.PRIMARY),  # hẹn thủ thuật chưa ai chỉ định
        (False, False, True, rules.TU_VAN),  # khám thường có mang sang: như cũ
    ],
)
def test_bang_chan_ly_duong_di(
    di_thang_phong: bool, cung_buoi: bool, mang_sang: bool, mong: str
) -> None:
    kw: dict[str, Any] = {
        "qua_tu_van": not di_thang_phong,
        "di_thang_phong": di_thang_phong,
        "cung_buoi_da_kham": cung_buoi,
        "co_mang_sang": mang_sang,
    }
    assert _duong(**kw) == mong


def test_cung_buoi_san_chau_khong_mang_sang_ve_bac_si_chinh() -> None:
    """Sàn chậu / thủ thuật (đi thẳng phòng, không qua tư vấn) lượt 2 mà không
    có chỉ định mang sang → bác sĩ chính quyết, không đứng im."""
    dich, ly_do = rules.duong_sau_check_in(
        qua_tu_van=False,
        di_thang_phong=True,
        cung_buoi_da_kham=True,
        co_mang_sang=False,
        quen_vao_thang=False,
    )
    assert dich == rules.PRIMARY
    assert "bác sĩ chính quyết" in ly_do


def test_ly_do_noi_ro_cung_buoi() -> None:
    dich, ly_do = rules.duong_sau_check_in(
        qua_tu_van=True,
        di_thang_phong=False,
        cung_buoi_da_kham=True,
        co_mang_sang=True,
        quen_vao_thang=False,
    )
    assert dich == rules.SERVICES and "cùng buổi" in ly_do


def test_khach_quen_van_theo_day_rieng() -> None:
    """Dây khách quen là luật RIÊNG — bật thì vào thẳng bác sĩ chính."""
    assert _duong(qua_tu_van=True, quen_vao_thang=True) == rules.PRIMARY
    assert _duong(qua_tu_van=True) == rules.TU_VAN
    assert _duong() == rules.PRIMARY


def test_day_cung_buoi_mac_dinh_bat_day_khach_quen_van_tat() -> None:
    assert DAY["h1_cung_buoi_thang_dich_vu"].mac_dinh is True
    assert DAY["h1_cung_buoi_thang_dich_vu"].kieu == "bat_tat"
    assert DAY["h1_khach_quen_vao_thang_bs"].mac_dinh is False


# --- sinh_hieu_buoi_dung_duoc -----------------------------------------------


def test_khong_thai_dung_lai_ke_ca_thieu_can_cao() -> None:
    assert rules.sinh_hieu_buoi_dung_duoc(co_thai=False, can_nang=None, chieu_cao=None)


@pytest.mark.parametrize(
    ("can", "cao", "mong"),
    [(55, 158, True), (None, 158, False), (55, None, False), (None, None, False)],
)
def test_co_thai_phai_du_can_nang_chieu_cao(can: Any, cao: Any, mong: bool) -> None:
    assert (
        rules.sinh_hieu_buoi_dung_duoc(co_thai=True, can_nang=can, chieu_cao=cao)
        is mong
    )


# --- hien_so_do_buoi ----------------------------------------------------------


@pytest.mark.parametrize(
    ("trang_thai", "rieng", "mong"),
    [
        ("recorded", False, True),  # H1 đã nhận số của buổi
        ("recorded", True, True),
        ("pending", True, True),  # dữ liệu cũ: có số riêng, trạng thái lệch
        ("pending", False, False),  # buổi có số nhưng lượt vẫn chờ đo
        ("in_progress", False, False),
        (None, False, False),
        ("rác", False, False),
    ],
)
def test_hien_so_do_buoi(trang_thai: str | None, rieng: bool, mong: bool) -> None:
    assert (
        rules.hien_so_do_buoi(vitals_status=trang_thai, co_so_do_luot_nay=rieng) is mong
    )


# --- nhan_nguon_sinh_hieu -----------------------------------------------------


def test_nhan_nguon() -> None:
    assert rules.nhan_nguon_sinh_hieu(nguon_visit_id="a", visit_id="a") is None
    assert rules.nhan_nguon_sinh_hieu(nguon_visit_id="a", visit_id="b") == "lượt trước"


@pytest.mark.parametrize(
    ("nguon", "luot"), [(None, "a"), ("a", None), ("", ""), (None, None)]
)
def test_nhan_nguon_dau_vao_rac_tra_rong(nguon: Any, luot: Any) -> None:
    assert rules.nhan_nguon_sinh_hieu(nguon_visit_id=nguon, visit_id=luot) is None
