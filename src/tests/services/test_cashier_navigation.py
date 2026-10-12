from datetime import datetime

from clinicai.core.clock import CLINIC_TZ
from clinicai.permissions.catalogue import QUYEN
from clinicai.services.cashier_navigation_service import (
    next_navigation_boundary,
    scoped_navigation,
)


def test_navigation_refreshes_at_configured_shift_start_and_end() -> None:
    settings = {"ca_lam_viec": {"SANG": {"bat_dau": "09:15", "ket_thuc": "12:45"}}}
    rows = [{"station": "LE_TAN", "shift": "SANG"}]
    before = datetime(2026, 10, 12, 9, 0, tzinfo=CLINIC_TZ)
    start = datetime(2026, 10, 12, 9, 15, tzinfo=CLINIC_TZ)
    assert next_navigation_boundary(before, rows, settings) == start
    assert next_navigation_boundary(start, rows, settings) == datetime(
        2026, 10, 12, 12, 45, tzinfo=CLINIC_TZ
    )


def test_head_full_day_and_unassigned_refresh_at_next_midnight() -> None:
    when = datetime(2026, 10, 12, 17, 0, tzinfo=CLINIC_TZ)
    midnight = datetime(2026, 10, 13, tzinfo=CLINIC_TZ)
    assert next_navigation_boundary(when, [], {}) == midnight
    assert (
        next_navigation_boundary(when, [{"station": "DIEU_PHOI", "shift": "SANG"}], {})
        == midnight
    )


def test_unrelated_station_cannot_trigger_counter_shift_deadline() -> None:
    when = datetime(2026, 10, 12, 7, 0, tzinfo=CLINIC_TZ)
    assert next_navigation_boundary(
        when, [{"station": "BAC_SI", "shift": "SANG"}], {}
    ) == datetime(2026, 10, 13, tzinfo=CLINIC_TZ)


def test_history_flags_cannot_be_granted_as_lego_capabilities() -> None:
    assert "payment.service.history" not in QUYEN
    assert "payment.medicine.history" not in QUYEN


def test_off_shift_keeps_history_but_removes_collect_and_keeps_other_rights() -> None:
    result = scoped_navigation(
        ["payment.service.collect", "payment.medicine.collect", "clinical.order.place"],
        {
            "dich_vu": {"items": [{"ngay": "2026-10-10"}], "thao_tac": False},
            "thuoc": {"items": [], "thao_tac": False},
        },
    )
    assert result == ["clinical.order.place", "payment.service.history"]


def test_active_roster_grants_counter_without_system_admin() -> None:
    result = scoped_navigation(
        [],
        {
            "dich_vu": {"items": [{"ngay": "2026-10-10"}], "thao_tac": True},
            "thuoc": {"items": [], "thao_tac": False},
        },
    )
    assert result == ["payment.service.collect", "payment.service.history"]


def test_manager_retains_both_counters_and_gains_history() -> None:
    scopes = {
        kind: {"quan_ly": True, "items": [], "thao_tac": True}
        for kind in ["dich_vu", "thuoc"]
    }
    result = scoped_navigation(["permission.manage"], scopes)
    assert result == [
        "payment.medicine.collect",
        "payment.medicine.history",
        "payment.service.collect",
        "payment.service.history",
        "permission.manage",
    ]


def test_explicit_history_capability_does_not_bypass_missing_roster() -> None:
    assert (
        scoped_navigation(
            ["payment.service.history"],
            {"dich_vu": {"items": [], "thao_tac": False}},
        )
        == []
    )
