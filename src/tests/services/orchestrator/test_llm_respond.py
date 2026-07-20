from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.orchestrator.llm_nodes import make_respond_node_llm
from clinicai.orchestrator.state import OrchestratorState


def _make_mock_llm(text: str) -> AnthropicClient:
    fake_resp = LLMResponse(
        text=text,
        model="claude-sonnet-4-6",
        input_tokens=50,
        output_tokens=30,
        latency_ms=120,
        stop_reason="end_turn",
    )
    mock_client = MagicMock(spec=AnthropicClient)
    mock_client.chat = AsyncMock(return_value=fake_resp)
    return mock_client


@pytest.mark.asyncio
async def test_llm_respond_returns_text():
    """Sonnet trả text → response = text trimmed."""
    mock = _make_mock_llm("  Phòng khám đã nhận yêu cầu của anh/chị.  ")
    node = make_respond_node_llm(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "đặt lịch khám",
        "route": "scheduling",
    }
    result = await node(state)
    assert result == {"response": "Phòng khám đã nhận yêu cầu của anh/chị."}
    mock.chat.assert_called_once()
    call_kwargs = mock.chat.call_args.kwargs
    assert call_kwargs["tier"] == "main_brain"
    assert call_kwargs["max_tokens"] == 300
    assert call_kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_llm_respond_empty_message_uses_template():
    """Tin nhắn rỗng → fallback template, KHÔNG gọi LLM."""
    mock = MagicMock(spec=AnthropicClient)
    mock.chat = AsyncMock()
    node = make_respond_node_llm(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "   ",
        "route": "unknown",
    }
    result = await node(state)
    assert result["response"] == "Tin nhắn trống hoặc không hiểu."
    mock.chat.assert_not_called()


@pytest.mark.asyncio
async def test_llm_respond_empty_llm_text_falls_back_template():
    """LLM trả text trống → fallback template (route=scheduling template)."""
    mock = _make_mock_llm("   ")
    node = make_respond_node_llm(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "đặt lịch",
        "route": "scheduling",
    }
    result = await node(state)
    assert result["response"] == "Đã nhận yêu cầu về lịch hẹn. (Phase 9.2 xử lý thật)"


@pytest.mark.asyncio
async def test_llm_respond_api_error_falls_back_template():
    """LLM raise exception → fallback template, KHÔNG crash."""
    mock = MagicMock(spec=AnthropicClient)
    mock.chat = AsyncMock(side_effect=ConnectionError("network down"))
    node = make_respond_node_llm(mock)
    state: OrchestratorState = {
        "trace_id": uuid4(),
        "user_message": "xét nghiệm máu",
        "route": "lab",
    }
    result = await node(state)
    assert result["response"] == "Đã nhận yêu cầu về xét nghiệm. (Phase 9.4 xử lý thật)"
