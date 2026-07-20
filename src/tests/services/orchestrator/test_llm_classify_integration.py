"""Integration test gọi Haiku thật. Skip nếu no API key."""

import os
from uuid import uuid4

import pytest

from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.llm_nodes import make_classify_intent_llm_node
from clinicai.orchestrator.state import OrchestratorState


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
async def test_llm_classify_real_haiku_scheduling():
    """Real Haiku 4.5 phân loại tin nhắn tiếng Việt về scheduling."""
    client = AnthropicClient()
    try:
        node = make_classify_intent_llm_node(client)
        state: OrchestratorState = {
            "trace_id": uuid4(),
            "user_message": "Em muốn đặt lịch khám thai vào thứ Hai tuần sau",
        }
        result = await node(state)
        assert result["route"] == "scheduling"
    finally:
        await client.close()
