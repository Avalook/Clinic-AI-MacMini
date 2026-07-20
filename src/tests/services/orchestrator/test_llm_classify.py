from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.orchestrator.llm_nodes import make_classify_intent_llm_node
from clinicai.orchestrator.state import OrchestratorState


def _make_mock_llm(text: str) -> AnthropicClient:
    """Helper tạo AnthropicClient mock trả text cho trước."""
    fake_resp = LLMResponse(
        text=text,
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
async def test_llm_classify_scheduling_route():
    """Haiku trả JSON đúng → route đúng."""
    mock = _make_mock_llm(
        '{"route": "scheduling", "confidence": 0.95, "reasoning": "test"}'
    )
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "đặt lịch khám",
    }
    result = await node(state)
    assert result == {"route": "scheduling"}
    mock.chat.assert_called_once()


@pytest.mark.asyncio
async def test_llm_classify_markdown_fence_stripped():
    """Haiku lỡ wrap JSON trong ```json ... ``` → vẫn parse được."""
    mock = _make_mock_llm(
        '```json\n{"route": "lab", "confidence": 0.9, "reasoning": "ok"}\n```'
    )
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {"trace_id": uuid4(), "user_message": "kết quả xn"}
    result = await node(state)
    assert result == {"route": "lab"}


@pytest.mark.asyncio
async def test_llm_classify_invalid_route_falls_back():
    """LLM trả route lạ → fallback rule-based."""
    mock = _make_mock_llm(
        '{"route": "BIZARRE_NEW_ROUTE", "confidence": 1.0, "reasoning": "x"}'
    )
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "đặt lịch hẹn ngày mai",
    }
    result = await node(state)
    assert result == {"route": "scheduling"}


@pytest.mark.asyncio
async def test_llm_classify_api_error_falls_back():
    """LLM raise exception → fallback rule-based, KHÔNG crash."""
    mock = MagicMock(spec=AnthropicClient)
    mock.chat = AsyncMock(side_effect=ConnectionError("network down"))
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "xét nghiệm máu",
    }
    result = await node(state)
    assert result == {"route": "lab"}


@pytest.mark.asyncio
async def test_llm_classify_empty_message_returns_unknown():
    """Tin nhắn rỗng → unknown, KHÔNG gọi LLM."""
    mock = MagicMock(spec=AnthropicClient)
    mock.chat = AsyncMock()
    node = make_classify_intent_llm_node(mock)
    state: OrchestratorState = {"trace_id": uuid4(), "user_message": "   "}
    result = await node(state)
    assert result == {"route": "unknown"}
    mock.chat.assert_not_called()
