"""Integration test gọi Haiku thật.

TỰ SKIP KHI KHÔNG CÓ KEY DÙNG ĐƯỢC, KHÔNG PHẢI KHI BIẾN MÔI TRƯỜNG CÓ MẶT.

`skipif(not os.getenv("ANTHROPIC_API_KEY"))` nghe thì đúng, nhưng nó chỉ hỏi
"biến có tồn tại không". Trên máy dev, `.env` gần như luôn có một giá trị nào đó
— hết hạn, của project khác, hoặc một chỗ giữ chỗ. Test vì thế CHẠY, bắn ba
request thật lên api.anthropic.com, ăn ba lần backoff rồi đổ với 401, và
`pytest` trần trong repo này luôn kết thúc bằng "1 failed". Một bộ test lúc nào
cũng đỏ một dòng là một bộ test không ai còn đọc kết quả.

Hai thay đổi:
  * đánh dấu `integration` (marker đã khai trong pyproject) để loại được bằng
    `-m "not integration"`;
  * chỉ chạy khi CÓ CHỦ Ý bật: `RUN_LLM_INTEGRATION=1`. Gọi một API tính tiền là
    việc phải yêu cầu rõ ràng, không phải mặc định của `pytest`.
"""

import os

import pytest

from clinicai.llm.anthropic_client import AnthropicClient

_ENABLED = os.getenv("RUN_LLM_INTEGRATION") == "1"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not (_ENABLED and os.getenv("ANTHROPIC_API_KEY")),
    reason="đặt RUN_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY để gọi API thật",
)
async def test_real_haiku_call_returns_text() -> None:
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
