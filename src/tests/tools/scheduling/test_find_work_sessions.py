"""Unit tests for the scheduling.find_work_sessions tool."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from clinicai.tools.scheduling.find_work_sessions import (
    FindWorkSessionsInput,
    FindWorkSessionsOutput,
    find_work_sessions,
)


def _row(
    *,
    session_id=None,
    session_date=None,
    session_type="EVENING",
    start_time="18:00",
    end_time="21:00",
    max_patients=20,
    doctors=None,
):
    return {
        "session_id": session_id or uuid4(),
        "session_date": session_date or date(2026, 5, 25),
        "session_type": session_type,
        "start_time": start_time,
        "end_time": end_time,
        "max_patients": max_patients,
        "available_doctors": doctors
        if doctors is not None
        else [
            {"staff_id": str(uuid4()), "full_name": "BS A", "on_call_flag": True},
        ],
    }


@pytest.mark.asyncio
async def test_find_work_sessions_returns_sessions_with_doctors() -> None:
    """Single row with one doctor → output.sessions[0].available_doctors non-empty."""
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[_row()])

    inp = FindWorkSessionsInput(
        location_id=uuid4(),
        session_date=date(2026, 5, 25),
        session_type="EVENING",
    )
    out = await find_work_sessions(inp, pool)

    assert isinstance(out, FindWorkSessionsOutput)
    assert len(out.sessions) == 1
    s = out.sessions[0]
    assert s.session_type == "EVENING"
    assert s.start_time == "18:00"
    assert s.end_time == "21:00"
    assert len(s.available_doctors) == 1
    assert s.available_doctors[0]["full_name"] == "BS A"


@pytest.mark.asyncio
async def test_find_work_sessions_empty_result() -> None:
    """No matching sessions → sessions == []."""
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])

    inp = FindWorkSessionsInput(
        location_id=uuid4(),
        session_date=date(2026, 5, 30),
        session_type="WEEKEND_MORNING",
    )
    out = await find_work_sessions(inp, pool)

    assert out.sessions == []


@pytest.mark.asyncio
async def test_find_work_sessions_filters_by_session_type() -> None:
    """SQL must be invoked with (location_id, session_date, session_type) params."""
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])

    loc_id = uuid4()
    session_date = date(2026, 5, 30)
    inp = FindWorkSessionsInput(
        location_id=loc_id,
        session_date=session_date,
        session_type="WEEKEND_AFTERNOON",
    )
    await find_work_sessions(inp, pool)

    assert pool.fetch.await_count == 1
    args = pool.fetch.call_args.args
    assert args[1] == loc_id
    assert args[2] == session_date
    assert args[3] == "WEEKEND_AFTERNOON"
    sql = args[0]
    assert "$1" in sql and "$2" in sql and "$3" in sql
    assert "is_training  = FALSE" in sql or "is_training = FALSE" in sql
    assert "role         = 'DOCTOR'" in sql or "role = 'DOCTOR'" in sql


def test_find_work_sessions_input_validation() -> None:
    """Invalid session_type string fails Pydantic validation."""
    with pytest.raises(ValidationError):
        FindWorkSessionsInput(
            location_id=uuid4(),
            session_date=date(2026, 5, 25),
            session_type="MORNING",  # not in the Literal allowlist
        )


@pytest.mark.asyncio
async def test_find_work_sessions_parses_jsonb_string() -> None:
    """Some asyncpg setups return jsonb columns as JSON strings."""
    pool = MagicMock()
    json_str = (
        '[{"staff_id": "11111111-1111-1111-1111-111111111111",'
        ' "full_name": "BS B", "on_call_flag": false}]'
    )
    pool.fetch = AsyncMock(return_value=[_row(doctors=json_str)])

    inp = FindWorkSessionsInput(
        location_id=uuid4(),
        session_date=date(2026, 5, 25),
        session_type="EVENING",
    )
    out = await find_work_sessions(inp, pool)

    assert out.sessions[0].available_doctors[0]["full_name"] == "BS B"
