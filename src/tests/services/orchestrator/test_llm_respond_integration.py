"""Integration test gọi Sonnet 4.6 thật. Skip nếu no API key."""

import os
from uuid import uuid4

import pytest

from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.llm_nodes import make_respond_node_llm
from clinicai.orchestrator.state import OrchestratorState


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
async def test_llm_respond_real_sonnet_returns_text():
    """Real Sonnet 4.6 trả response tiếng Việt non-empty cho scheduling route."""
    client = AnthropicClient()
    try:
        node = make_respond_node_llm(client)
        state: OrchestratorState = {
            "trace_id": uuid4(),
            "user_message": "Em muốn đặt lịch khám thai vào thứ Hai tuần sau",
            "route": "scheduling",
        }
        result = await node(state)
        assert "response" in result
        assert isinstance(result["response"], str)
        assert len(result["response"].strip()) > 0
    finally:
        await client.close()
