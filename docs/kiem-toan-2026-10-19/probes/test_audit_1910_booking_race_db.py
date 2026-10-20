"""Audit: rescheduling must not undo a concurrently committed arrival."""

# ruff: noqa: F811 -- imported fixture follows the repository convention.

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.services.booking_service import BookingService
from tests.services.test_check_in_lai_sau_hoan_tac_db import CLINIC, pool  # noqa: F401
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _benh_nhan, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_reschedule_preserves_concurrently_committed_checkin(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    ca = await _dung(pool)
    start = datetime.now(UTC) + timedelta(minutes=30)
    appt = await pool.fetchval(
        "INSERT INTO appointment (clinic_id,clinic_patient_id,location_id,"
        "service_type_id,slot_start,slot_end,doctor_id,status)"
        " VALUES($1::uuid,$2::uuid,$3::uuid,$4::uuid,$5,$6,$7::uuid,'CONFIRMED')"
        " RETURNING id::text",
        CLINIC,
        await _benh_nhan(pool, ca),
        ca.loc,
        ca.loai_kham,
        start,
        start + timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    reader_ready, resume = asyncio.Event(), asyncio.Event()
    changing = BookingService(pool)
    original_update = changing._update

    async def pause_before_update(*args: Any, **kwargs: Any) -> bool:
        reader_ready.set()
        await asyncio.wait_for(resume.wait(), timeout=10)
        return await original_update(*args, **kwargs)

    async def independent_hours_guard(*args: Any, **kwargs: Any) -> None:
        # Fix the clock-dependent opening-hours precondition; preserve all writes,
        # transactions, state reads, update predicates, triggers and event emission.
        return None

    monkeypatch.setattr(changing, "_update", pause_before_update)
    monkeypatch.setattr(changing, "_chan_dat_ngoai_khung_ca", independent_hours_guard)
    task = asyncio.create_task(
        changing.apply_action(
            appointment_id=appt,
            action="reschedule",
            identity=ca.le_tan,
            slot_start=start,
            slot_end=start + timedelta(minutes=15),
            ghi_chu="Synthetic reschedule note",
            ghi_chu_provided=True,
        )
    )
    try:
        await asyncio.wait_for(reader_ready.wait(), timeout=10)
        checked = await BookingService(pool).apply_action(
            appointment_id=appt,
            action="checkin",
            identity=ca.le_tan,
        )
        assert checked["status"] == "CHECKED_IN"
        resume.set()
        await asyncio.wait_for(task, timeout=10)
        state = await pool.fetchrow(
            "SELECT a.status, v.visit_id IS NOT NULL AS has_visit,"
            " v.closed_at IS NULL AS visit_open FROM appointment a"
            " JOIN visit v ON v.appointment_id=a.id WHERE a.id=$1::uuid",
            appt,
        )
        assert state["has_visit"] and state["visit_open"]
        assert state["status"] == "CHECKED_IN", "Stale reschedule reversed arrival"
    finally:
        resume.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
