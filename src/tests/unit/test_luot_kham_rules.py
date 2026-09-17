"""Luật thuần của luồng khám lát 1 — mỗi test là một câu trong contract v2 §3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from clinicai.services import luot_kham_rules as rules

T0 = datetime(2026, 9, 11, 18, 0, tzinfo=timezone.utc)


# --- D1: đích sau check-in -------------------------------------------------


def test_chua_do_sinh_hieu_thi_chua_co_dich() -> None:
    assert (
        rules.decide_route(
            vitals_recorded=False, plan_status="none", current_route=None
        )
        is None
    )


def test_luot_moi_do_xong_sinh_hieu_vao_bac_si() -> None:
    assert (
        rules.decide_route(vitals_recorded=True, plan_status="none", current_route=None)
        == rules.PRIMARY
    )


def test_ke_hoach_dang_xac_minh_thi_giu_nguyen() -> None:
    # T-P2: sinh hiệu đến trước, kế hoạch còn chờ → chưa quyết.
    assert (
        rules.decide_route(
            vitals_recorded=True, plan_status="pending", current_route=None
        )
        is None
    )


def test_ke_hoach_hop_le_di_thang_dich_vu() -> None:
    assert (
        rules.decide_route(
            vitals_recorded=True, plan_status="applied", current_route=None
        )
        == rules.SERVICES
    )


@pytest.mark.parametrize("status", ["rejected", "abandoned"])
def test_ke_hoach_bi_tu_choi_hoac_bo_qua_vao_bac_si(status: str) -> None:
    assert (
        rules.decide_route(vitals_recorded=True, plan_status=status, current_route=None)
        == rules.PRIMARY
    )


def test_dich_da_ghi_thi_khong_doi() -> None:
    # I10: kế hoạch hợp lệ đến muộn không kéo khách đã vào bác sĩ sang dịch vụ.
    assert (
        rules.decide_route(
            vitals_recorded=True, plan_status="applied", current_route=rules.PRIMARY
        )
        is None
    )


def test_trang_thai_ke_hoach_la_thi_no() -> None:
    with pytest.raises(ValueError):
        rules.decide_route(vitals_recorded=True, plan_status="???", current_route=None)


# --- D2: vòng đọc sẵn sàng -------------------------------------------------


def _req(
    need: str = "PERFORMED",
    status: str = "open",
    exec_status: str = "performed",
    result: bool = False,
) -> rules.RequirementView:
    return rules.RequirementView("o1", need, status, exec_status, result)


def test_tap_rong_khong_bao_gio_san_sang() -> None:
    # I5 / T-R7
    assert rules.round_ready([]) is False


def test_da_lam_la_du_khi_chi_can_da_lam() -> None:
    assert rules.round_ready([_req("PERFORMED")]) is True


def test_da_lam_chua_co_ket_qua_chua_du_khi_can_ket_qua() -> None:
    # T-R1: thực hiện và kết quả là hai trục.
    assert rules.round_ready([_req("VALID_RESULT", result=False)]) is False
    assert rules.round_ready([_req("VALID_RESULT", result=True)]) is True


def test_chua_lam_thi_chua_du() -> None:
    assert rules.round_ready([_req("PERFORMED", exec_status="in_progress")]) is False


def test_bac_si_mien_thi_tinh_la_du_ma_khong_doi_trang_thai_thuc_hien() -> None:
    # T-R4: miễn yêu cầu, chỉ định vẫn đang chờ kết quả.
    waived = _req(
        "VALID_RESULT", status="waived", exec_status="performed", result=False
    )
    assert rules.requirement_met(waived) is False
    assert rules.round_ready([waived]) is True


def test_mot_yeu_cau_thieu_la_ca_vong_chua_du() -> None:
    assert (
        rules.round_ready(
            [_req("PERFORMED"), _req("PERFORMED", exec_status="assigned")]
        )
        is False
    )


def test_chi_dinh_vua_bat_buoc_vua_bi_giu_toi_vong_do() -> None:
    # T-V4: SA → đọc → máu khai sai.
    assert rules.cyclic_orders(2, [("sa", None), ("mau", 2)]) == ["mau"]
    # T-V3: máu giữ tới vòng 2 nhưng là yêu cầu của vòng 3 → hợp lệ.
    assert rules.cyclic_orders(3, [("mau", 2)]) == []


# --- C7: điều phối ---------------------------------------------------------


def _block(**kw: object) -> str | None:
    base: dict[str, object] = dict(
        exec_status="authorized",
        source="VISIT_ORDER",
        authorized_by="bs",
        plan_applied=False,
        route_decision=rules.PRIMARY,
        vitals_recorded=True,
        hold_until_round=None,
        closed_rounds=set(),
    )
    base.update(kw)
    return rules.dispatch_block(**base)  # type: ignore[arg-type]


def test_chi_dinh_da_duyet_dieu_phoi_duoc() -> None:
    assert _block() is None


def test_nhap_cua_thu_ky_khong_dieu_phoi_duoc() -> None:
    # T-A3 / I1
    assert _block(exec_status="draft", authorized_by=None) == "NO_VALID_ORDER"


def test_da_lam_xong_khong_dieu_phoi_lai() -> None:
    assert _block(exec_status="performed") == "ORDER_NOT_DISPATCHABLE"


def test_ke_hoach_ap_truoc_khi_do_sinh_hieu_bi_chan_dung_ly_do() -> None:
    # T-P9: nhánh kế hoạch, chưa đo huyết áp.
    assert (
        _block(
            source="PRIOR_PLAN",
            plan_applied=True,
            route_decision=None,
            vitals_recorded=False,
        )
        == "VITALS_REQUIRED"
    )


def test_ke_hoach_khi_khach_da_vao_bac_si() -> None:
    assert (
        _block(source="PRIOR_PLAN", plan_applied=True, route_decision=rules.PRIMARY)
        == "PLAN_NOT_APPLIED"
    )


def test_bi_giu_toi_khi_vong_chua_dong() -> None:
    # T-V3
    assert _block(hold_until_round=2, closed_rounds=set()) == "HELD_UNTIL_ROUND"
    assert _block(hold_until_round=2, closed_rounds={2}) is None


# --- Hàng chờ --------------------------------------------------------------


def test_hang_cho_theo_luc_du_dieu_kien_khong_theo_gio_hen() -> None:
    # T-A14: A 18:10, B 18:12, C quay lại 18:15, D vào 18:16 → A, B, C, D.
    a = rules.QueueView("A", "waiting", T0 + timedelta(minutes=10), T0)
    b = rules.QueueView("B", "waiting", T0 + timedelta(minutes=12), T0)
    c = rules.QueueView(
        "C", "waiting", T0 + timedelta(minutes=15), T0 - timedelta(hours=1)
    )
    d = rules.QueueView(
        "D", "waiting", T0 + timedelta(minutes=16), T0 + timedelta(minutes=16)
    )
    assert [e.id for e in rules.order_queue([d, c, b, a])] == ["A", "B", "C", "D"]


def test_dang_phuc_vu_dung_dau_bi_chan_dung_cuoi_da_xong_bi_bo() -> None:
    serving = rules.QueueView("S", "serving", T0 + timedelta(minutes=20), T0)
    blocked = rules.QueueView("K", "blocked", None, T0)
    done = rules.QueueView("X", "done", T0, T0)
    waiting = rules.QueueView("W", "waiting", T0, T0)
    assert [e.id for e in rules.order_queue([blocked, done, waiting, serving])] == [
        "S",
        "W",
        "K",
    ]


def test_khach_dang_o_cho_khac_thi_vao_hang_o_trang_thai_cho_mo() -> None:
    assert rules.initial_queue_status(visit_busy=True) == "blocked"
    assert rules.initial_queue_status(visit_busy=False) == "waiting"


# --- Phiên khám ------------------------------------------------------------


def test_ket_qua_phien_theo_dung_loai() -> None:
    # T-C4
    assert rules.outcome_allowed("PRIMARY", "NO_SERVICES")
    assert rules.outcome_allowed("PRIMARY", "SERVICES")
    assert not rules.outcome_allowed("PRIMARY", "DONE")
    assert rules.outcome_allowed("REVIEW", "DONE")
    assert not rules.outcome_allowed("REVIEW", "NO_SERVICES")
    assert not rules.outcome_allowed("LA", "DONE")


# --- Sinh hiệu -------------------------------------------------------------


def test_sinh_hieu_hop_le() -> None:
    v, loi = rules.parse_vitals(
        {"systolic": "120", "diastolic": 80, "pulse": 72, "temperature": "36,8"}
    )
    assert loi is None and v is not None
    assert (v.systolic, v.diastolic, v.pulse, v.temperature) == (
        120,
        80,
        72,
        Decimal("36.8"),
    )


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "abc",
        [],
        {},
        {"systolic": 120},
        {"systolic": "", "diastolic": ""},
        {"systolic": "mười", "diastolic": 80},
        {"systolic": True, "diastolic": 80},
        {"systolic": 120, "diastolic": 80, "pulse": "nhanh"},
        {"systolic": 999, "diastolic": 80},
        {"systolic": 80, "diastolic": 120},
        {"systolic": 120.5, "diastolic": 80},
        {"systolic": "NaN", "diastolic": 80},
        {"systolic": 120, "diastolic": 80, "temperature": "Infinity"},
    ],
)
def test_sinh_hieu_rac_tra_cau_loi_khong_nem(raw: object) -> None:
    v, loi = rules.parse_vitals(raw)
    assert v is None
    assert isinstance(loi, str) and loi


def test_bmi_tu_tinh_khi_co_can_nang_va_chieu_cao() -> None:
    v, loi = rules.parse_vitals(
        {"systolic": 118, "diastolic": 76, "weight_kg": 54, "height_cm": 160}
    )
    assert loi is None and v is not None
    assert v.bmi == Decimal("21.1")


def test_bmi_do_tay_duoc_giu_nguyen() -> None:
    v, _ = rules.parse_vitals(
        {"systolic": 118, "diastolic": 76, "weight_kg": 54, "height_cm": 160, "bmi": 22}
    )
    assert v is not None and v.bmi == Decimal("22")
