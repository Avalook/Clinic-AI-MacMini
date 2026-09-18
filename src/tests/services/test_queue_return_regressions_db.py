"""Actual SQL on a disposable, migrated PostgreSQL; fixtures use TEMP tables only."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.display_board_service import _SQL, _mot_dong
from clinicai.services.lab_order_service import LabOrderService
from clinicai.services.queue_rows import thu_tu_goi_theo_ngay

pytestmark = [pytest.mark.db, pytest.mark.asyncio]
CLINIC = "a0000000-0000-4000-8000-000000000001"
START = datetime(2026, 9, 15, 1, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def conn() -> Any:
    url = os.environ.get("DATABASE_URL_TEST")
    if not url:
        pytest.skip("requires explicitly disposable DATABASE_URL_TEST")
    c = await asyncpg.connect(url)
    try:
        await c.execute("""
          CREATE TEMP TABLE appointment (
            id uuid, clinic_id uuid, clinic_patient_id uuid,
            service_type_id uuid, doctor_id uuid, slot_start timestamptz,
            status text, queue_number text, booking_channel text);
          CREATE TEMP TABLE patient (
            clinic_patient_id uuid, clinic_id uuid, full_name text);
          CREATE TEMP TABLE service_type (id uuid, name text);
          CREATE TEMP TABLE visit (
            appointment_id uuid, clinic_id uuid, checked_in_at timestamptz,
            status text, current_room_id uuid, thu_tu_tay_ms bigint);
          CREATE TEMP TABLE lab_result (
            lab_result_id uuid, appointment_id uuid, clinic_id uuid,
            result_value text, external_ref text, lab_provider text,
            result_received_at timestamptz, updated_at timestamptz,
            is_finalized boolean DEFAULT false,
            clinic_patient_id uuid, visit_id uuid);
          CREATE TEMP TABLE event_log (
            clinic_id uuid, event_type text, aggregate_type text,
            aggregate_id text, payload jsonb, metadata jsonb,
            source text, event_published boolean);
        """)
        yield c
    finally:
        await c.close()


async def _appointment(c: Any, arrived: int) -> str:
    aid = str(uuid.uuid4())
    await c.execute(
        "INSERT INTO appointment (id, clinic_id, slot_start, status, queue_number, "
        "booking_channel) VALUES ($1::uuid, $2::uuid, $3, 'CHECKED_IN', $4, 'WALK_IN')",
        aid,
        CLINIC,
        START,
        str(arrived),
    )
    await c.execute(
        "INSERT INTO visit (appointment_id, clinic_id, checked_in_at, status) "
        "VALUES ($1::uuid, $2::uuid, $3, 'CHECKED_IN')",
        aid,
        CLINIC,
        START + timedelta(minutes=arrived),
    )
    return aid


async def test_tv_uses_return_eligibility_and_excludes_foreign_labs(conn: Any) -> None:
    a, b = await _appointment(conn, 0), await _appointment(conn, 10)
    await conn.execute(
        "INSERT INTO lab_result VALUES ($1::uuid, $2::uuid, $3::uuid, 'ready', "
        "NULL, NULL, $4, $4, false)",
        str(uuid.uuid4()),
        a,
        CLINIC,
        START + timedelta(minutes=20),
    )
    # A foreign-clinic pending row sharing the appointment ID must not block A.
    await conn.execute(
        "INSERT INTO lab_result (lab_result_id, appointment_id, clinic_id) "
        "VALUES ($1::uuid, $2::uuid, $3::uuid)",
        str(uuid.uuid4()),
        a,
        str(uuid.uuid4()),
    )
    rows = await conn.fetch(_SQL, CLINIC, START, START + timedelta(days=1))
    decisions = thu_tu_goi_theo_ngay(rows)
    assert decisions[b].call_order < decisions[a].call_order
    assert decisions[a].entry.b3_ready is True
    assert decisions[a].entry.b3_ready_at == START + timedelta(minutes=20)
    payload = _mot_dong(rows[0], decisions[str(rows[0]["id"])], [])
    assert "b3_ready_at" not in payload and "result_value" not in payload
    # An own-clinic whitespace-only result remains pending.
    await conn.execute(
        "INSERT INTO lab_result "
        "(lab_result_id, appointment_id, clinic_id, result_value) "
        "VALUES ($1::uuid, $2::uuid, $3::uuid, '   ')",
        str(uuid.uuid4()),
        a,
        CLINIC,
    )
    rows = await conn.fetch(_SQL, CLINIC, START, START + timedelta(days=1))
    assert thu_tu_goi_theo_ngay(rows)[a].entry.b3_ready is False


class _Pool:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @asynccontextmanager
    async def acquire(self) -> Any:
        yield self.connection


async def test_correcting_result_keeps_first_received_time(conn: Any) -> None:
    rid, aid = str(uuid.uuid4()), str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO lab_result (lab_result_id, appointment_id, clinic_id) "
        "VALUES ($1::uuid, $2::uuid, $3::uuid)",
        rid,
        aid,
        CLINIC,
    )
    identity = StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="Test",
        department="DOCTOR",
        role=ClinicRole.DOCTOR,
        clinic_id=CLINIC,
        location_id=str(uuid.uuid4()),
        location_name="Test",
    )
    service = LabOrderService(_Pool(conn))
    await service.enter_result(
        lab_result_id=rid,
        result_value="first",
        result_link=None,
        lab_provider=None,
        identity=identity,
    )
    first = await conn.fetchval("SELECT result_received_at FROM lab_result")
    assert first is not None
    await service.enter_result(
        lab_result_id=rid,
        result_value="corrected",
        result_link=None,
        lab_provider=None,
        identity=identity,
    )
    row = await conn.fetchrow("SELECT * FROM lab_result")
    assert row["result_received_at"] == first
    assert row["result_value"] == "corrected"
    assert row["updated_at"] >= first
    assert await conn.fetchval("SELECT count(*) FROM event_log") == 2
