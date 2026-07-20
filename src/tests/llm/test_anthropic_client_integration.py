"""Integration test gọi Haiku thật. Skip nếu no ANTHROPIC_API_KEY."""

import os

import pytest

from clinicai.llm.anthropic_client import AnthropicClient


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — integration skip",
)
async def test_real_haiku_call_returns_text():
    client = AnthropicClient()
    try:
        result = await client.chat(
            messages=[{"role": "user", "content": "Reply with just the word: pong"}],
            tier="gateway",
            max_tokens=20,
            temperature=0.0,
        )
        assert result.text
        assert result.input_tokens > 0
        assert result.output_tokens > 0
        assert result.model.startswith("claude-haiku-4-5")
        assert result.latency_ms > 0
    finally:
        await client.close()
