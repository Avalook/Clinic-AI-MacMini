"""Anthropic SDK async wrapper với retry + structured logging.

T-P8-04 sẽ inject AnthropicClient vào OrchestratorService để swap
classify_intent rule-based → LLM Haiku. Hiện tại chỉ provide gateway client.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

import structlog
from anthropic import APIConnectionError, APIError, AsyncAnthropic, RateLimitError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from clinicai.llm import chi_phi
from clinicai.llm.models import TIER_TO_MODEL, Tier

logger = structlog.get_logger(__name__)

DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.2
RETRY_ATTEMPTS = 3
RETRY_WAIT_MIN_S = 1.0
RETRY_WAIT_MAX_S = 8.0


def cached_system_param(system: str, cache: bool = True) -> Any:
    """Bọc system prompt (TĨNH) trong block cache_control (ephemeral) để bật
    Anthropic prompt-caching. Dùng chung cho chat() (real-time) lẫn batch (offline).

    Caching CHỈ kích hoạt khi prefix vượt ngưỡng tối thiểu của model
    (Sonnet 4.6 ~2048 token, Haiku 4.5 ~4096 token). Dưới ngưỡng → no-op vô
    hại: SDK không ghi cache, KHÔNG phát sinh chi phí.
    """
    if not cache:
        return system
    return [
        {
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }
    ]


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    stop_reason: Optional[str] = None
    # Prompt-caching observability (0 khi không có cache hit / SDK không trả về).
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    #: Dòng `llm_lan_goi` của lần gọi này (chỉ có khi client mang `pool`).
    lan_goi_id: Optional[str] = None


class AnthropicClient:
    """Async wrapper quanh AsyncAnthropic SDK với retry + logging."""

    def __init__(self, api_key: Optional[str] = None, *, pool: Any = None) -> None:
        """`pool` (asyncpg.Pool): có thì MỖI lần gọi ghi `llm_lan_goi` (token +
        USD) và bị chặn khi tiền hôm nay chạm trần (`llm/chi_phi.py`)."""
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY env var bắt buộc để khởi tạo AnthropicClient."
            )
        self._client = AsyncAnthropic(api_key=key)
        self._pool = pool

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tier: Tier = "gateway",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: Optional[float] = DEFAULT_TEMPERATURE,
        system: Optional[str] = None,
        cache_system: bool = True,
        trace_id: Optional[UUID] = None,
        *,
        model: Optional[str] = None,
        tinh_nang: str = "khac",
        clinic_id: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        extra_body: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        """`temperature=None` = KHÔNG gửi: Opus 5.5 / Sonnet 5.5 trả 400 khi có
        tham số lấy mẫu. `model` đè `tier`. `extra_*` chuyển nguyên cho SDK (tham
        số mới hơn bản SDK đang ghim)."""
        model = model or TIER_TO_MODEL[tier]
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if system is not None:
            kwargs["system"] = self._build_system(system, cache_system)
        if extra_headers:
            kwargs["extra_headers"] = extra_headers
        if extra_body:
            kwargs["extra_body"] = extra_body

        if self._pool is not None:
            await chi_phi.chan_neu_vuot_tran(self._pool)
        start = time.perf_counter()
        try:
            resp = await self._invoke_with_retry(kwargs)
        except Exception as e:
            if self._pool is not None:
                await chi_phi.ghi_lan_goi(
                    self._pool,
                    tinh_nang=tinh_nang,
                    model=model,
                    clinic_id=clinic_id,
                    thanh_cong=False,
                    loi=f"{type(e).__name__}: {e}",
                    thoi_gian_ms=int((time.perf_counter() - start) * 1000),
                )
            raise
        latency_ms = int((time.perf_counter() - start) * 1000)

        text = self._extract_text(resp)
        input_tokens = self._usage_int(resp.usage, "input_tokens")
        output_tokens = self._usage_int(resp.usage, "output_tokens")
        cache_read = self._usage_int(resp.usage, "cache_read_input_tokens")
        cache_creation = self._usage_int(resp.usage, "cache_creation_input_tokens")
        stop_reason = getattr(resp, "stop_reason", None)
        lan_goi_id: Optional[str] = None
        if self._pool is not None:
            lan_goi_id = await chi_phi.ghi_lan_goi(
                self._pool,
                tinh_nang=tinh_nang,
                model=str(getattr(resp, "model", None) or model),
                vao=input_tokens,
                ra=output_tokens,
                doc_cache=cache_read,
                ghi_cache=cache_creation,
                clinic_id=clinic_id,
                thanh_cong=stop_reason != "refusal",
                loi="refusal" if stop_reason == "refusal" else None,
                ma_yeu_cau=getattr(resp, "_request_id", None),
                thoi_gian_ms=latency_ms,
            )

        logger.info(
            "llm_call",
            trace_id=str(trace_id) if trace_id else None,
            model=resp.model,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_creation,
            latency_ms=latency_ms,
            stop_reason=stop_reason,
        )

        return LLMResponse(
            text=text,
            model=resp.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            stop_reason=stop_reason,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_creation,
            lan_goi_id=lan_goi_id,
        )

    async def _invoke_with_retry(self, kwargs: dict[str, Any]) -> Any:
        retryer = AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(RETRY_ATTEMPTS),
            wait=wait_exponential(
                multiplier=1, min=RETRY_WAIT_MIN_S, max=RETRY_WAIT_MAX_S
            ),
            retry=retry_if_exception_type(
                (RateLimitError, APIConnectionError, APIError)
            ),
        )
        async for attempt in retryer:
            with attempt:
                return await self._client.messages.create(**kwargs)
        raise RuntimeError("AnthropicClient retry loop exited without result")

    @staticmethod
    def _build_system(system: str, cache: bool) -> Any:
        """Delegate sang hàm module-level dùng-chung (chat + batch)."""
        return cached_system_param(system, cache)

    @staticmethod
    def _usage_int(usage: Any, name: str) -> int:
        """Đọc field token từ usage, trả 0 nếu thiếu / không phải int
        (vd response mock trong test, hoặc SDK chưa trả cache fields)."""
        val = getattr(usage, name, 0)
        return val if isinstance(val, int) else 0

    @staticmethod
    def _extract_text(resp: Any) -> str:
        parts: list[str] = []
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts)

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:
                logger.debug("anthropic_close_noop")
