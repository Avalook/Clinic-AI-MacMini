"""Unit tests for StaffService with mock asyncpg pool."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.schemas.staff import (
    EmploymentType,
    PrimaryDepartment,
    StaffCreateDTO,
    StaffUpdateDTO,
)
from clinicai.services.staff_service import StaffService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_STAFF_ID = uuid4()
FAKE_LOCATION_ID = uuid4()
FAKE_NOW = datetime.datetime(2026, 5, 20, 10, 0, 0, tzinfo=datetime.timezone.utc)


def _make_staff_record(overrides: dict | None = None) -> dict:
    """Build a dict that looks like an asyncpg.Record for the staff table."""
    base = {
        "id": FAKE_STAFF_ID,
        "full_name": "Bác sĩ Nguyễn Văn A",
        "short_name": "BS Nguyễn",
        "primary_department": "DOCTOR",
        "primary_location_id": FAKE_LOCATION_ID,
        "employment_type": "FULL_TIME",
        "is_training": False,
        "is_active": True,
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
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_staff_success() -> None:
    """create_staff should INSERT and return a StaffDTO."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = _make_staff_record()

    svc = StaffService(pool)
    dto = await svc.create_staff(
        StaffCreateDTO(
            full_name="Bác sĩ Nguyễn Văn A",
            short_name="BS Nguyễn",
            primary_department=PrimaryDepartment.DOCTOR,
            primary_location_id=FAKE_LOCATION_ID,
        )
    )

    assert dto.id == FAKE_STAFF_ID
    assert dto.full_name == "Bác sĩ Nguyễn Văn A"
    assert dto.primary_department == "DOCTOR"
    assert dto.employment_type == "FULL_TIME"
    assert dto.is_training is False
    assert dto.is_active is True

    conn.fetchrow.assert_awaited_once()
    sql_arg = conn.fetchrow.call_args[0][0]
    assert "INSERT INTO staff" in sql_arg


@pytest.mark.asyncio
async def test_list_assignable_excludes_training() -> None:
    """list_assignable must exclude staff with is_training=TRUE (D023 gate)."""
    pool, conn = _mock_pool_and_conn()
    # DB returns only non-training staff (filter happens in DB query)
    conn.fetch.return_value = [
        _make_staff_record({"is_training": False}),
    ]

    svc = StaffService(pool)
    results = await svc.list_assignable()

    assert len(results) == 1
    assert results[0].is_training is False

    sql_arg = conn.fetch.call_args[0][0]
    assert "is_training = FALSE" in sql_arg


@pytest.mark.asyncio
async def test_list_assignable_excludes_inactive() -> None:
    """list_assignable must exclude staff with is_active=FALSE."""
    pool, conn = _mock_pool_and_conn()
    conn.fetch.return_value = []

    svc = StaffService(pool)
    results = await svc.list_assignable()

    assert results == []

    sql_arg = conn.fetch.call_args[0][0]
    assert "is_active = TRUE" in sql_arg


@pytest.mark.asyncio
async def test_get_by_id_not_found() -> None:
    """get_by_id should return None when staff does not exist."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = None

    svc = StaffService(pool)
    result = await svc.get_by_id(uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_update_staff() -> None:
    """update_staff should SET only provided fields and return updated DTO."""
    pool, conn = _mock_pool_and_conn()
    updated_record = _make_staff_record(
        {
            "full_name": "Bác sĩ Trần Thị B",
            "employment_type": "PART_TIME",
        }
    )
    conn.fetchrow.return_value = updated_record

    svc = StaffService(pool)
    dto = await svc.update_staff(
        FAKE_STAFF_ID,
        StaffUpdateDTO(
            full_name="Bác sĩ Trần Thị B",
            employment_type=EmploymentType.PART_TIME,
        ),
    )

    assert dto.full_name == "Bác sĩ Trần Thị B"
    assert dto.employment_type == "PART_TIME"

    sql_arg = conn.fetchrow.call_args[0][0]
    assert "UPDATE staff SET" in sql_arg
    assert "RETURNING" in sql_arg


@pytest.mark.asyncio
async def test_update_staff_no_fields_raises() -> None:
    """update_staff should raise ValidationError if no fields provided."""
    pool, _conn = _mock_pool_and_conn()
    svc = StaffService(pool)

    with pytest.raises(ValidationError, match="No fields to update"):
        await svc.update_staff(FAKE_STAFF_ID, StaffUpdateDTO())


@pytest.mark.asyncio
async def test_deactivate_sets_inactive() -> None:
    """deactivate should soft-delete by setting is_active=FALSE."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = {"id": FAKE_STAFF_ID}

    svc = StaffService(pool)
    await svc.deactivate(FAKE_STAFF_ID)

    conn.fetchrow.assert_awaited_once()
    sql_arg = conn.fetchrow.call_args[0][0]
    assert "is_active = FALSE" in sql_arg


@pytest.mark.asyncio
async def test_deactivate_not_found_raises() -> None:
    """deactivate should raise ResourceNotFoundError if staff does not exist."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = None

    svc = StaffService(pool)
    missing_id = uuid4()

    with pytest.raises(ResourceNotFoundError, match=str(missing_id)):
        await svc.deactivate(missing_id)
