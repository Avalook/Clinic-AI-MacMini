from datetime import date
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.cashier_scope_service import (
    CashierScopeService,
    allowed_roster,
    scope_intervals,
)


def test_roster_quay_full_head_and_rejected() -> None:
    rows = [
        dict(station="T1_THUNGAN", shift="SANG", status="APPROVED", location_id="a"),
        dict(station="T2_XEPTHUOC", shift="TOI", status="APPROVED", location_id="b"),
        dict(station="T1_THUNGAN", shift="CHIEU", status="PENDING", location_id="a"),
    ]
    assert allowed_roster(rows, "dich_vu") == {"a": {"SANG"}}
    assert allowed_roster(rows, "thuoc") == {"b": {"TOI"}}
    rows = [dict(station="DIEU_PHOI", shift="TOI", status="APPROVED", location_id="a")]
    assert allowed_roster(rows, "dich_vu") == {"a": {"SANG", "CHIEU", "TOI", "FULL"}}


def test_half_open_intervals() -> None:
    start, end = scope_intervals(date(2026, 10, 12), ["SANG", "TOI"], {})
    assert len(start) == 2 and end[0] <= start[1]
    assert start[0].hour == 8 and end[1].date() == date(2026, 10, 12)


@pytest.mark.asyncio
async def test_authorize_shift_and_location(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = AsyncMock()
    pool.fetch.return_value = [
        dict(station="T1_THUNGAN", shift="SANG", status="APPROVED", location_id="a")
    ]
    pool.fetchval.return_value = {}
    identity = cast(
        StaffIdentity,
        SimpleNamespace(
            co_vai=lambda _: False, clinic_id="c", staff_id="s", location_id="a"
        ),
    )
    svc = CashierScopeService(cast(asyncpg.Pool, pool))
    # Invalid requests denied before replacing the real immutable identity.
    for ca, location in [("TOI", "a"), ("FULL", "a"), ("SANG", "b")]:
        with pytest.raises(SafetyGateError):
            await svc.authorize(
                identity,
                tu="2026-10-12",
                den="2026-10-12",
                kind="dich_vu",
                ca=ca,
                co_so=location,
            )


@pytest.mark.asyncio
async def test_active_morning_allows_even_with_future_evening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime

    import clinicai.services.cashier_scope_service as module
    from clinicai.api.identity import ClinicRole
    from clinicai.core.clock import CLINIC_TZ

    monkeypatch.setattr(
        module, "now_vn", lambda: datetime(2026, 10, 12, 9, tzinfo=CLINIC_TZ)
    )
    pool = AsyncMock()
    pool.fetch.return_value = [
        dict(station="T1_THUNGAN", shift=shift, status="APPROVED", location_id="a")
        for shift in ["SANG", "TOI"]
    ]
    pool.fetchval.return_value = {}
    identity = StaffIdentity(
        staff_id="s",
        auth_user_id="u",
        full_name="Demo",
        department="Thu ngân",
        role=ClinicRole.CASHIER,
        clinic_id="c",
        location_id="a",
        location_name="Demo",
    )
    svc = CashierScopeService(cast(asyncpg.Pool, pool))
    assert (await svc.authorize_active(identity, kind="dich_vu")).actor_id == "s"
    monkeypatch.setattr(
        module, "now_vn", lambda: datetime(2026, 10, 12, 7, 59, tzinfo=CLINIC_TZ)
    )
    with pytest.raises(SafetyGateError):
        await svc.authorize_active(identity, kind="dich_vu")
    pool.fetchval.return_value = {
        "ca_lam_viec": {"SANG": {"bat_dau": "09:15", "ket_thuc": "12:45"}}
    }
    monkeypatch.setattr(
        module, "now_vn", lambda: datetime(2026, 10, 12, 9, tzinfo=CLINIC_TZ)
    )
    with pytest.raises(SafetyGateError):
        await svc.authorize_active(identity, kind="dich_vu")
    monkeypatch.setattr(
        module, "now_vn", lambda: datetime(2026, 10, 12, 9, 30, tzinfo=CLINIC_TZ)
    )
    assert (await svc.authorize_active(identity, kind="dich_vu")).actor_id == "s"
    with pytest.raises(SafetyGateError):
        await svc.authorize(
            identity,
            tu="2026-10-12",
            den="2026-10-12",
            kind="dich_vu",
            ca="TOI",
            co_so="a",
        )
    monkeypatch.setattr(
        module, "now_vn", lambda: datetime(2026, 10, 12, 14, tzinfo=CLINIC_TZ)
    )
    with pytest.raises(SafetyGateError):
        await svc.authorize_active(identity, kind="dich_vu")


@pytest.mark.asyncio
async def test_active_head_has_both_counter_hints_without_lego(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime

    import clinicai.services.cashier_scope_service as module
    from clinicai.api.identity import ClinicRole
    from clinicai.core.clock import CLINIC_TZ
    from clinicai.services.cashier_board_service import quyen_thu_theo_loai

    monkeypatch.setattr(
        module, "now_vn", lambda: datetime(2026, 10, 12, 14, tzinfo=CLINIC_TZ)
    )
    conn = AsyncMock()
    conn.fetch.return_value = [
        dict(station="DIEU_PHOI", shift="SANG", status="APPROVED", location_id="a")
    ]
    conn.fetchval.return_value = {}
    identity = StaffIdentity(
        staff_id="s",
        auth_user_id="u",
        full_name="Demo",
        department="Trưởng ca",
        role=ClinicRole.CSKH,
        clinic_id="c",
        location_id="a",
        location_name="Demo",
    )
    assert await quyen_thu_theo_loai(cast(asyncpg.Connection, conn), identity) == {
        "dich_vu": True,
        "thuoc": True,
    }
