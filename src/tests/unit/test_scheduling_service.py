"""Unit tests for SchedulingService with mock asyncpg pool."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import asyncpg
import pytest

from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.schemas.scheduling import (
    AppointmentCreateDTO,
    SessionType,
    WorkSessionCreateDTO,
    WorkSessionStaffAssignDTO,
)
from clinicai.services.scheduling_service import SchedulingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_SESSION_ID = uuid4()
FAKE_STAFF_ID = uuid4()
FAKE_APPT_ID = uuid4()
FAKE_PATIENT_ID = uuid4()
FAKE_LOCATION_ID = uuid4()
FAKE_SERVICE_TYPE_ID = uuid4()
FAKE_NOW = datetime.datetime(2026, 5, 20, 10, 0, 0, tzinfo=datetime.timezone.utc)
FAKE_LATER = FAKE_NOW + datetime.timedelta(hours=1)


def _make_session_record(overrides: dict | None = None) -> dict:
    base = {
        "id": FAKE_SESSION_ID,
        "location_id": FAKE_LOCATION_ID,
        "session_date": datetime.date(2026, 6, 1),
        "session_type": "EVENING",
        "start_time": datetime.time(18, 0),
        "end_time": datetime.time(21, 0),
        "max_patients": None,
        "created_at": FAKE_NOW,
    }
    if overrides:
        base.update(overrides)
    return base


def _make_wss_record(overrides: dict | None = None) -> dict:
    base = {
        "id": uuid4(),
        "work_session_id": FAKE_SESSION_ID,
        "staff_id": FAKE_STAFF_ID,
        "role": "DOCTOR",
        "station": "Station-1",
        "on_call_flag": False,
        "is_training": False,
        "created_at": FAKE_NOW,
    }
    if overrides:
        base.update(overrides)
    return base


def _make_appt_record(overrides: dict | None = None) -> dict:
    base = {
        "id": FAKE_APPT_ID,
        "clinic_patient_id": FAKE_PATIENT_ID,
        "doctor_id": FAKE_STAFF_ID,
        "work_session_id": FAKE_SESSION_ID,
        "location_id": FAKE_LOCATION_ID,
        "service_type_id": FAKE_SERVICE_TYPE_ID,
        "booking_channel": None,
        "slot_start": FAKE_NOW,
        "slot_end": FAKE_LATER,
        "assigned_station": None,
        "queue_number": None,
        "is_priority_slot": False,
        "is_walkin": False,
        "status": "SCHEDULED",
        "confirmed_at": None,
        "cancelled_at": None,
        "cancellation_reason": None,
        "created_at": FAKE_NOW,
        "updated_at": FAKE_NOW,
    }
    if overrides:
        base.update(overrides)
    return base


def _mock_pool_and_conn() -> tuple[MagicMock, AsyncMock]:
    """Return (pool, conn) with pool.acquire() wired as async ctx mgr."""
    pool = MagicMock()
    conn = AsyncMock()

    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx

    return pool, conn


# ---------------------------------------------------------------------------
# Work Session Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_work_session_success() -> None:
    """create_work_session should INSERT and return a WorkSessionDTO."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = _make_session_record()

    svc = SchedulingService(pool)
    dto = await svc.create_work_session(
        WorkSessionCreateDTO(
            location_id=FAKE_LOCATION_ID,
            session_date=datetime.date(2026, 6, 1),
            session_type=SessionType.EVENING,
            start_time=datetime.time(18, 0),
            end_time=datetime.time(21, 0),
        )
    )

    assert dto.id == FAKE_SESSION_ID
    assert dto.session_type == "EVENING"

    sql_arg = conn.fetchrow.call_args[0][0]
    assert "INSERT INTO work_session" in sql_arg


@pytest.mark.asyncio
async def test_create_work_session_duplicate_raises() -> None:
    """create_work_session should raise ValidationError on UniqueViolation."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.side_effect = asyncpg.UniqueViolationError(
        "duplicate key value violates unique constraint"
    )

    svc = SchedulingService(pool)
    with pytest.raises(ValidationError, match="already exists"):
        await svc.create_work_session(
            WorkSessionCreateDTO(
                location_id=FAKE_LOCATION_ID,
                session_date=datetime.date(2026, 6, 1),
                session_type=SessionType.EVENING,
                start_time=datetime.time(18, 0),
                end_time=datetime.time(21, 0),
            )
        )


# ---------------------------------------------------------------------------
# Work Session Staff Assignment Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assign_staff_snapshot_training() -> None:
    """assign_staff_to_session should snapshot is_training from staff table."""
    pool, conn = _mock_pool_and_conn()

    # First fetchrow: staff row with is_training=True
    # Second fetchrow: inserted work_session_staff record
    wss_record = _make_wss_record({"is_training": True})
    conn.fetchrow.side_effect = [
        {"is_training": True},  # SELECT from staff
        wss_record,  # INSERT into work_session_staff
    ]

    svc = SchedulingService(pool)
    dto = await svc.assign_staff_to_session(
        WorkSessionStaffAssignDTO(
            work_session_id=FAKE_SESSION_ID,
            staff_id=FAKE_STAFF_ID,
            role="DOCTOR",
            station="Station-1",
        )
    )

    assert dto.is_training is True
    assert dto.staff_id == FAKE_STAFF_ID

    # Second fetchrow is the INSERT — check it passes is_training=True
    insert_call_args = conn.fetchrow.call_args_list[1][0]
    assert True in insert_call_args  # is_training=True was passed


@pytest.mark.asyncio
async def test_assign_staff_not_found_raises() -> None:
    """assign_staff_to_session raises ResourceNotFoundError for missing staff."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = None  # staff not found

    svc = SchedulingService(pool)
    with pytest.raises(ResourceNotFoundError):
        await svc.assign_staff_to_session(
            WorkSessionStaffAssignDTO(
                work_session_id=FAKE_SESSION_ID,
                staff_id=uuid4(),
                role="DOCTOR",
                station="Station-1",
            )
        )


# ---------------------------------------------------------------------------
# Appointment Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_appointment_success() -> None:
    """create_appointment should INSERT and return an AppointmentDTO."""
    pool, conn = _mock_pool_and_conn()
    # No work_session_id → no on-duty check
    conn.fetchrow.return_value = _make_appt_record({"work_session_id": None})

    svc = SchedulingService(pool)
    dto = await svc.create_appointment(
        AppointmentCreateDTO(
            clinic_patient_id=FAKE_PATIENT_ID,
            location_id=FAKE_LOCATION_ID,
            service_type_id=FAKE_SERVICE_TYPE_ID,
            slot_start=FAKE_NOW,
            slot_end=FAKE_LATER,
        )
    )

    assert dto.id == FAKE_APPT_ID
    assert dto.status == "SCHEDULED"

    sql_arg = conn.fetchrow.call_args[0][0]
    assert "INSERT INTO appointment" in sql_arg


@pytest.mark.asyncio
async def test_create_appointment_invalid_slot_raises() -> None:
    """create_appointment raises ValidationError when slot_end <= slot_start."""
    pool, _conn = _mock_pool_and_conn()
    svc = SchedulingService(pool)

    with pytest.raises(Exception):
        await svc.create_appointment(
            AppointmentCreateDTO(
                clinic_patient_id=FAKE_PATIENT_ID,
                location_id=FAKE_LOCATION_ID,
                service_type_id=FAKE_SERVICE_TYPE_ID,
                slot_start=FAKE_NOW,
                slot_end=FAKE_NOW - datetime.timedelta(minutes=30),
            )
        )


@pytest.mark.asyncio
async def test_confirm_appointment_success() -> None:
    """confirm_appointment transitions SCHEDULED → CONFIRMED."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.side_effect = [
        {"status": "SCHEDULED"},  # SELECT existing
        _make_appt_record({"status": "CONFIRMED", "confirmed_at": FAKE_NOW}),
    ]

    svc = SchedulingService(pool)
    dto = await svc.confirm_appointment(FAKE_APPT_ID)

    assert dto.status == "CONFIRMED"
    assert dto.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_appointment_wrong_status_raises() -> None:
    """confirm_appointment raises ValidationError if current status is not SCHEDULED."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = {"status": "CONFIRMED"}

    svc = SchedulingService(pool)
    with pytest.raises(ValidationError, match="CONFIRMED"):
        await svc.confirm_appointment(FAKE_APPT_ID)


@pytest.mark.asyncio
async def test_cancel_appointment_success() -> None:
    """cancel_appointment transitions SCHEDULED → CANCELLED."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.side_effect = [
        {"status": "SCHEDULED"},  # SELECT existing
        _make_appt_record(
            {
                "status": "CANCELLED",
                "cancelled_at": FAKE_NOW,
                "cancellation_reason": "Patient request",
            }
        ),
    ]

    svc = SchedulingService(pool)
    dto = await svc.cancel_appointment(FAKE_APPT_ID, reason="Patient request")

    assert dto.status == "CANCELLED"
    assert dto.cancellation_reason == "Patient request"


@pytest.mark.asyncio
async def test_cancel_completed_appointment_raises() -> None:
    """cancel_appointment raises ValidationError if status is COMPLETED."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = {"status": "COMPLETED"}

    svc = SchedulingService(pool)
    with pytest.raises(ValidationError, match="COMPLETED"):
        await svc.cancel_appointment(FAKE_APPT_ID, reason="Late cancellation")


@pytest.mark.asyncio
async def test_cancel_already_cancelled_raises() -> None:
    """cancel_appointment raises ValidationError if status is already CANCELLED."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = {"status": "CANCELLED"}

    svc = SchedulingService(pool)
    with pytest.raises(ValidationError, match="CANCELLED"):
        await svc.cancel_appointment(FAKE_APPT_ID, reason="Duplicate cancel")
