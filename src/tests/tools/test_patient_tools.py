"""Unit tests for the patient.get_summary tool."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from clinicai.api.exceptions import PatientNotFoundError
from clinicai.tools._common.context import new_trace
from clinicai.tools.patient.get_summary import (
    GetPatientSummaryInput,
    PatientSummaryOutput,
    get_patient_summary,
)


@pytest.fixture
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Return a mocked asyncpg Pool and its single connection."""
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool, conn


@pytest.mark.asyncio
async def test_get_summary_happy_path(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """Tool should return a populated PatientSummaryOutput from a DB row."""
    pool, conn = mock_pool
    patient_id = uuid4()
    visit = date(2026, 4, 12)
    dob = date(1990, 5, 3)
    conn.fetchrow.return_value = {
        "clinic_patient_id": patient_id,
        "patient_code": "BN-2026-000123",
        "full_name": "Nguyễn Thị A",
        "phone_primary": "0901234567",
        "date_of_birth": dob,
        "last_visit_date": visit,
        "active_pregnancy": True,
    }

    inp = GetPatientSummaryInput(patient_id=patient_id, ctx=new_trace())
    out = await get_patient_summary(inp, pool)

    assert isinstance(out, PatientSummaryOutput)
    assert out.patient_id == patient_id
    assert out.patient_code == "BN-2026-000123"
    assert out.full_name == "Nguyễn Thị A"
    assert out.phone == "0901234567"
    assert out.date_of_birth == dob
    assert out.last_visit_date == visit
    assert out.active_pregnancy is True
    assert out.trace_id == inp.ctx.trace_id


@pytest.mark.asyncio
async def test_get_summary_not_found(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """When no row exists, the tool must raise PatientNotFoundError."""
    pool, conn = mock_pool
    conn.fetchrow.return_value = None

    inp = GetPatientSummaryInput(patient_id=uuid4(), ctx=new_trace())

    with pytest.raises(PatientNotFoundError):
        await get_patient_summary(inp, pool)


@pytest.mark.asyncio
async def test_get_summary_logs_trace_id(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """structlog entries must include the trace_id from the input ctx."""
    pool, conn = mock_pool
    conn.fetchrow.return_value = {
        "clinic_patient_id": uuid4(),
        "patient_code": "BN-2026-000999",
        "full_name": "Test",
        "phone_primary": None,
        "date_of_birth": None,
        "last_visit_date": None,
        "active_pregnancy": False,
    }

    inp = GetPatientSummaryInput(patient_id=uuid4(), ctx=new_trace())

    with capture_logs() as logs:
        await get_patient_summary(inp, pool)

    assert any(log.get("trace_id") == str(inp.ctx.trace_id) for log in logs)
