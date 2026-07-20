from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.orchestrator.graph import build_orchestrator_graph, route_by_intent
from clinicai.orchestrator.state import OrchestratorState
from clinicai.orchestrator.stubs import (
    communication_stub_node,
    lab_triage_stub_node,
    previsit_brief_stub_node,
    scheduling_stub_node,
    task_manager_stub_node,
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


@pytest.mark.parametrize(
    "route",
    ["scheduling", "lab", "communication", "task", "previsit", "general"],
)
def test_route_by_intent_valid_routes(route: str):
    state: OrchestratorState = {"route": route}  # type: ignore[typeddict-item]
    assert route_by_intent(state) == route


def test_route_by_intent_unknown_fallback_general():
    state: OrchestratorState = {"route": "random_garbage"}  # type: ignore[typeddict-item]
    assert route_by_intent(state) == "general"


def test_route_by_intent_missing_route_defaults_general():
    state: OrchestratorState = {}
    assert route_by_intent(state) == "general"


@pytest.mark.asyncio
async def test_graph_routes_scheduling_to_stub():
    """End-to-end: classify=scheduling → scheduling_stub sets handled_by marker."""
    mock_llm = _mock_llm_with_route("scheduling")
    graph = build_orchestrator_graph(llm_client=mock_llm, use_llm_respond=False)
    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "đặt lịch khám ngày mai",
    }
    config = {"configurable": {"thread_id": "test-scheduling"}}
    final_state = await graph.ainvoke(initial, config=config)
    assert final_state.get("handled_by") == "scheduling_stub"
    assert "[STUB-scheduling]" in final_state.get("response", "")


@pytest.mark.asyncio
async def test_graph_routes_scheduling_to_real_subgraph(monkeypatch):
    """With pool + location_id wired, scheduling routes to build_scheduling_subgraph."""
    import clinicai.tools.scheduling.find_work_sessions as _fws_module
    from clinicai.tools.scheduling.find_work_sessions import (
        FindWorkSessionsOutput,
        WorkSessionResult,
    )

    session_result = WorkSessionResult(
        session_id=uuid4(),
        session_date=__import__("datetime").date(2026, 5, 25),
        session_type="EVENING",
        start_time="18:00",
        end_time="21:00",
        max_patients=20,
        available_doctors=[
            {"staff_id": str(uuid4()), "full_name": "BS A", "on_call_flag": True},
        ],
    )
    monkeypatch.setattr(
        _fws_module,
        "find_work_sessions",
        AsyncMock(return_value=FindWorkSessionsOutput(sessions=[session_result])),
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
        "user_message": "đặt lịch khám tối mai",
        # Pre-fill so we go straight to find_doctor and exercise the real tool path.
        "step": "find_doctor",
        "preferred_date": "2026-05-25",
        "preferred_time": "evening",
        "turn_count": 2,
    }
    config = {"configurable": {"thread_id": "test-scheduling-real"}}
    final_state = await graph.ainvoke(initial, config=config)

    assert final_state.get("handled_by") == "scheduling_subgraph"
    assert final_state.get("step") in {"ask_date", "ask_time", "confirm", "done"}


@pytest.mark.asyncio
async def test_graph_routes_general_to_respond():
    """End-to-end: classify=general → respond_node template (non-empty)."""
    mock_llm = _mock_llm_with_route("general")
    graph = build_orchestrator_graph(llm_client=mock_llm, use_llm_respond=False)
    initial: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "Xin chào bác sĩ",
    }
    config = {"configurable": {"thread_id": "test-general"}}
    final_state = await graph.ainvoke(initial, config=config)
    response_text = final_state.get("response", "")
    assert response_text
    assert final_state.get("handled_by") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stub_node, expected_marker, expected_name",
    [
        (scheduling_stub_node, "scheduling_stub", "scheduling"),
        (lab_triage_stub_node, "lab_triage_stub", "lab_triage"),
        (communication_stub_node, "communication_stub", "communication"),
        (task_manager_stub_node, "task_manager_stub", "task_manager"),
        (previsit_brief_stub_node, "previsit_brief_stub", "previsit_brief"),
    ],
)
async def test_all_5_stubs_set_handled_by_marker(
    stub_node, expected_marker: str, expected_name: str
):
    state: OrchestratorState = {"trace_id": uuid4(), "user_message": "x"}
    result = await stub_node(state)
    assert result["handled_by"] == expected_marker
    assert f"[STUB-{expected_name}]" in result["response"]
