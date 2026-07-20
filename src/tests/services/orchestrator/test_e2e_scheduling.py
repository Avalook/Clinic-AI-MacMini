"""E2E orchestrator → scheduling sub-graph integration tests.

Cover the three integration shapes a P9.1 caller can hit:
1. First turn happy path (classify → sub-graph greeting).
2. Pool-less fallback preserves the legacy stub behaviour.
3. Sub-graph propagates business-rule errors back through the orchestrator.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import clinicai.tools.scheduling.find_work_sessions as _fws_module
from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.orchestrator.graph import build_orchestrator_graph
from clinicai.orchestrator.state import OrchestratorState
from clinicai.tools.scheduling.find_work_sessions import (
    FindWorkSessionsOutput,
    WorkSessionResult,
)


def _mock_llm_with_route(route: str) -> AnthropicClient:
    fake_resp = LLMResponse(
        text=f'{{"route": "{route}", "confidence": 0.95, "reasoning": "x"}}',
        model="claude-haiku-4-5-20251001",
        input_tokens=10,
        output_tokens=20,
        latency_ms=30,
        stop_reason="end_turn",
    )
    mock = MagicMock(spec=AnthropicClient)
    mock.chat = AsyncMock(return_value=fake_resp)
    return mock


def _session_result() -> WorkSessionResult:
    return WorkSessionResult(
        session_id=uuid4(),
        session_date=date(2026, 5, 25),
        session_type="EVENING",
        start_time="18:00",
        end_time="21:00",
        max_patients=20,
        available_doctors=[
            {
                "staff_id": str(uuid4()),
                "full_name": "BS Trần Thị A",
                "on_call_flag": True,
            },
        ],
    )


@pytest.mark.asyncio
async def test_e2e_first_turn_scheduling_greeting():
    """First turn with no date → sub-graph asks for date in Vietnamese."""
    mock_llm = _mock_llm_with_route("scheduling")
    graph = build_orchestrator_graph(
        llm_client=mock_llm,
        use_llm_respond=False,
        scheduling_pool=AsyncMock(),
        scheduling_location_id=uuid4(),
    )

    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "tôi muốn đặt lịch khám",
    }
    config = {"configurable": {"thread_id": "e2e-greeting"}}
    final = await graph.ainvoke(initial, config=config)

    assert final.get("handled_by") == "scheduling_subgraph"
    assert "ngày nào" in final.get("response", "")
    assert final.get("step") == "ask_date"


@pytest.mark.asyncio
async def test_e2e_scheduling_no_pool_falls_back_to_stub():
    """No pool wired → scheduling route uses the legacy stub node."""
    mock_llm = _mock_llm_with_route("scheduling")
    graph = build_orchestrator_graph(
        llm_client=mock_llm,
        use_llm_respond=False,
        # scheduling_pool / scheduling_location_id intentionally omitted
    )

    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "đặt lịch khám ngày mai",
    }
    config = {"configurable": {"thread_id": "e2e-no-pool"}}
    final = await graph.ainvoke(initial, config=config)

    assert final.get("handled_by") == "scheduling_stub"
    assert "[STUB-scheduling]" in final.get("response", "")


@pytest.mark.asyncio
async def test_e2e_scheduling_invalid_time_weekday_redirects(monkeypatch):
    """preferred_time=morning on weekday → sub-graph redirects to ask_time."""
    # Tool should not actually be called in this path, but keep a benign mock
    # so we get a useful error if it is reached.
    monkeypatch.setattr(
        _fws_module,
        "find_work_sessions",
        AsyncMock(return_value=FindWorkSessionsOutput(sessions=[_session_result()])),
    )

    mock_llm = _mock_llm_with_route("scheduling")
    graph = build_orchestrator_graph(
        llm_client=mock_llm,
        use_llm_respond=False,
        scheduling_pool=AsyncMock(),
        scheduling_location_id=uuid4(),
    )

    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "sáng",
        "step": "find_doctor",
        "preferred_date": "2026-05-25",  # Monday
        "preferred_time": "morning",
        "turn_count": 2,
    }
    config = {"configurable": {"thread_id": "e2e-invalid-time"}}
    final = await graph.ainvoke(initial, config=config)

    assert final.get("step") == "ask_time"
    assert "chỉ có ca tối" in final.get("response", "")
    assert final.get("preferred_time") is None
