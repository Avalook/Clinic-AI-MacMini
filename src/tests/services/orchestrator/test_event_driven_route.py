"""Event-driven routing: state['event_type'] short-circuits classification.

When an upstream caller (RabbitMQ dispatch) sets event_type, the LLM
classifier node routes straight from the event and never calls the LLM.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.orchestrator.llm_nodes import make_classify_intent_llm_node
from clinicai.orchestrator.nodes import map_event_to_route
from clinicai.orchestrator.state import OrchestratorState


def _make_mock_llm() -> AnthropicClient:
    """LLM mock that would classify as 'scheduling' if ever called."""
    fake_resp = LLMResponse(
        text='{"route": "scheduling", "confidence": 0.95, "reasoning": "test"}',
        model="claude-haiku-4-5-20251001",
        input_tokens=10,
        output_tokens=20,
        latency_ms=50,
        stop_reason="end_turn",
    )
    mock_client = MagicMock(spec=AnthropicClient)
    mock_client.chat = AsyncMock(return_value=fake_resp)
    return mock_client


@pytest.mark.asyncio
async def test_event_type_lab():
    mock = _make_mock_llm()
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "bất kỳ tin nhắn nào",
        "event_type": "lab_result_received",
    }
    result = await node(state)
    assert result == {"route": "lab"}
    mock.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_type_previsit():
    mock = _make_mock_llm()
    node = make_classify_intent_llm_node(mock)
    # Empty user_message must NOT shadow the event-driven path.
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "",
        "event_type": "previsit_trigger",
    }
    result = await node(state)
    assert result == {"route": "previsit"}
    mock.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_type_task():
    mock = _make_mock_llm()
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "x",
        "event_type": "task_overdue",
    }
    result = await node(state)
    assert result == {"route": "task"}
    mock.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_type_unknown_fallback():
    mock = _make_mock_llm()
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "x",
        "event_type": "unknown_event",
    }
    result = await node(state)
    assert result == {"route": "general"}
    mock.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_event_type_still_classifies():
    mock = _make_mock_llm()
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "Tôi muốn đặt lịch khám ngày mai",
    }
    result = await node(state)
    assert result == {"route": "scheduling"}
    mock.chat.assert_awaited_once()


def test_map_event_to_route():
    assert map_event_to_route("lab_result_received") == "lab"
    assert map_event_to_route("appointment_created") == "scheduling"
    assert map_event_to_route("previsit_trigger") == "previsit"
    assert map_event_to_route("task_overdue") == "task"
    assert map_event_to_route("nonsense") == "general"
