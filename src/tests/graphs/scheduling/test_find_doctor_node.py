"""Sub-graph find_doctor_node tests (rewired to find_work_sessions tool)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import clinicai.tools.scheduling.find_work_sessions as _fws_module
from clinicai.graphs.scheduling import (
    build_scheduling_subgraph,
    make_find_doctor_node,
)
from clinicai.graphs.scheduling.state import SchedulingState
from clinicai.tools.scheduling.find_work_sessions import (
    FindWorkSessionsOutput,
    WorkSessionResult,
)


def _session_result(doctor_name: str = "BS Trần Thị A") -> WorkSessionResult:
    return WorkSessionResult(
        session_id=uuid4(),
        session_date=__import__("datetime").date(2026, 5, 25),
        session_type="EVENING",
        start_time="18:00",
        end_time="21:00",
        max_patients=20,
        available_doctors=[
            {
                "staff_id": str(uuid4()),
                "full_name": doctor_name,
                "on_call_flag": True,
            }
        ],
    )


@pytest.mark.asyncio
async def test_make_find_doctor_node_success_weekday_evening(monkeypatch) -> None:
    """Happy path: weekday evening → EVENING session → doctor surfaced."""
    monkeypatch.setattr(
        _fws_module,
        "find_work_sessions",
        AsyncMock(return_value=FindWorkSessionsOutput(sessions=[_session_result()])),
    )

    node = make_find_doctor_node(AsyncMock(), uuid4())
    state: SchedulingState = {
        "preferred_date": "2026-05-25",  # Monday
        "preferred_time": "evening",
        "turn_count": 2,
    }
    result = await node(state)

    assert result["step"] == "confirm"
    assert result["preferred_doctor"] == "BS Trần Thị A"
    assert "BS Trần Thị A" in result["response"]
    assert "ca EVENING" in result["response"]
    assert len(result["candidate_doctors"]) == 1


@pytest.mark.asyncio
async def test_no_sessions_found_loops_back_to_ask_date(monkeypatch) -> None:
    """Empty tool result → loop back to ask_date."""
    monkeypatch.setattr(
        _fws_module,
        "find_work_sessions",
        AsyncMock(return_value=FindWorkSessionsOutput(sessions=[])),
    )

    node = make_find_doctor_node(AsyncMock(), uuid4())
    state: SchedulingState = {
        "preferred_date": "2026-05-25",
        "preferred_time": "evening",
        "turn_count": 2,
    }
    result = await node(state)

    assert result["step"] == "ask_date"
    assert result["preferred_date"] is None
    assert "không có bác sĩ rảnh" in result["response"]


@pytest.mark.asyncio
async def test_invalid_time_for_weekday_redirects_to_ask_time() -> None:
    """morning on a weekday has no session_type → ask_time loop."""
    node = make_find_doctor_node(AsyncMock(), uuid4())
    state: SchedulingState = {
        "preferred_date": "2026-05-25",  # Monday
        "preferred_time": "morning",
        "turn_count": 2,
    }
    result = await node(state)

    assert result["step"] == "ask_time"
    assert result["preferred_time"] is None
    assert "chỉ có ca tối" in result["response"]


@pytest.mark.asyncio
async def test_tool_exception_fallback(monkeypatch) -> None:
    """Tool raises → graceful confirm-with-apology, no crash."""
    monkeypatch.setattr(
        _fws_module,
        "find_work_sessions",
        AsyncMock(side_effect=RuntimeError("DB down")),
    )

    node = make_find_doctor_node(AsyncMock(), uuid4())
    state: SchedulingState = {
        "preferred_date": "2026-05-25",
        "preferred_time": "evening",
        "turn_count": 2,
    }
    result = await node(state)

    assert result["step"] == "confirm"
    assert result["candidate_doctors"] == []
    assert "chưa tra cứu được" in result["response"]


@pytest.mark.asyncio
async def test_no_pool_stub_fallback() -> None:
    """build_scheduling_subgraph(pool=None) keeps backward-compat stub."""
    graph = build_scheduling_subgraph(pool=None)
    initial: SchedulingState = {
        "step": "find_doctor",
        "user_message": "",
        "turn_count": 2,
        "preferred_date": "2026-05-25",
        "preferred_time": "evening",
        "response": "",
    }
    result = await graph.ainvoke(initial)
    assert "[STUB-no-pool]" in result["response"]
