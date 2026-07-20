"""Unit tests for the scheduling.find_oncall tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.api.exceptions import WorkSessionNotFoundError
from clinicai.tools._common.context import new_trace
from clinicai.tools.scheduling.find_oncall import (
    FindOncallInput,
    OncallStaffOutput,
    find_oncall_staff,
)


@pytest.fixture
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Mocked asyncpg Pool + Connection."""
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool, conn


def _staff_row(role: str = "NURSE", station: str = "ROOM-1") -> dict:
    return {
        "staff_id": uuid4(),
        "full_name": f"Staff {role}",
        "role": role,
        "station": station,
    }


@pytest.mark.asyncio
async def test_find_oncall_happy_path(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """3 on-duty staff rows should produce on_duty_staff len=3 + doctor_ids."""
    pool, conn = mock_pool
    work_session_id = uuid4()
    doctor_row = _staff_row(role="DOCTOR", station="ROOM-2")
    rows = [_staff_row(), doctor_row, _staff_row(role="TECH", station="LAB")]

    conn.fetchrow.return_value = {"id": work_session_id}
    conn.fetch.return_value = rows

    inp = FindOncallInput(work_session_id=work_session_id, ctx=new_trace())
    out = await find_oncall_staff(inp, pool)

    assert isinstance(out, OncallStaffOutput)
    assert out.work_session_id == work_session_id
    assert len(out.on_duty_staff) == 3
    assert out.doctor_ids == [doctor_row["staff_id"]]
    assert out.trace_id == inp.ctx.trace_id


@pytest.mark.asyncio
async def test_find_oncall_excludes_training(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """SQL WHERE is_training=FALSE — simulate pool already filtering trainees.

    The DB returns only non-training rows; the tool just trusts the query.
    Two normal + one trainee assigned at DB level → only 2 rows handed back.
    """
    pool, conn = mock_pool
    work_session_id = uuid4()
    conn.fetchrow.return_value = {"id": work_session_id}
    conn.fetch.return_value = [_staff_row(), _staff_row(role="DOCTOR")]

    inp = FindOncallInput(work_session_id=work_session_id, ctx=new_trace())
    out = await find_oncall_staff(inp, pool)

    assert len(out.on_duty_staff) == 2
    # Verify the SQL passed to fetch contains the is_training filter — guards
    # against accidental removal of the D023 gate.
    sql_arg = conn.fetch.call_args[0][0]
    assert "is_training = FALSE" in sql_arg


@pytest.mark.asyncio
async def test_find_oncall_not_found(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """Missing work_session row → WorkSessionNotFoundError."""
    pool, conn = mock_pool
    conn.fetchrow.return_value = None

    inp = FindOncallInput(work_session_id=uuid4(), ctx=new_trace())

    with pytest.raises(WorkSessionNotFoundError):
        await find_oncall_staff(inp, pool)
