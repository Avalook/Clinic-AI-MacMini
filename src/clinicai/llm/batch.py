"""Anthropic Message Batches API wrapper — chạy LLM offline ở 50% giá.

DÙNG CHO: workload KHÔNG nhạy độ trễ, chịu được tới 24h. Ví dụ điển hình:
sinh `pre_visit_brief` HÀNG LOẠT cho lịch hẹn ngày mai (cron đêm) — bác sĩ
không cần ngay, nên 50% giá là "tiền rơi". Batch + prompt caching cộng dồn
(tới ~95% tiết kiệm trên phần prefix lặp).

KHÔNG dùng cho:
- `lab_triage` safety path: GROUP_C có SLA 4h → phân loại an toàn phải
  real-time qua AnthropicClient.chat(), TUYỆT ĐỐI không nhét vào batch 24h.
- Bất kỳ luồng nào bệnh nhân/bác sĩ đang chờ trả lời ngay.

Đây là PRIMITIVE tái dùng. Việc nối vào cron đêm sinh brief = bước riêng
(P13), cần có traffic thật mới sinh tiết kiệm; module này chỉ cung cấp khả năng.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import structlog
from anthropic import AsyncAnthropic

from clinicai.llm.anthropic_client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    cached_system_param,
)
from clinicai.llm.models import TIER_TO_MODEL, Tier

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BatchItem:
    """Một request trong batch. `custom_id` dùng để map kết quả về đúng nguồn
    (vd clinic_patient_id của brief)."""

    custom_id: str
    messages: list[dict[str, Any]]
    tier: Tier = "main_brain"
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    system: Optional[str] = None
    cache_system: bool = True


@dataclass(frozen=True)
class BatchResultItem:
    custom_id: str
    succeeded: bool
    text: str = ""
    error: Optional[str] = None


# Trạng thái batch coi như "đã xong" để dừng polling.
TERMINAL_STATUS = "ended"


class AnthropicBatchClient:
    """Async wrapper quanh Messages Batches API (50% giá, SLA tới 24h)."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY env var bắt buộc để khởi tạo AnthropicBatchClient."
            )
        self._client = AsyncAnthropic(api_key=key)

    async def submit(self, items: list[BatchItem]) -> str:
        """Nộp batch. Trả về batch_id để poll sau. Caching bật theo từng item."""
        if not items:
            raise ValueError("Batch rỗng — cần ít nhất 1 BatchItem.")
        requests: list[Any] = []
        for it in items:
            params: dict[str, Any] = {
                "model": TIER_TO_MODEL[it.tier],
                "max_tokens": it.max_tokens,
                "temperature": it.temperature,
                "messages": it.messages,
            }
            if it.system is not None:
                params["system"] = cached_system_param(it.system, it.cache_system)
            requests.append({"custom_id": it.custom_id, "params": params})

        batch = await self._client.messages.batches.create(requests=requests)
        batch_id = getattr(batch, "id", "")
        logger.info("llm_batch_submit", batch_id=batch_id, count=len(items))
        return batch_id

    async def status(self, batch_id: str) -> str:
        """Trả processing_status: 'in_progress' | 'ended' | 'canceling' ..."""
        batch = await self._client.messages.batches.retrieve(batch_id)
        return str(getattr(batch, "processing_status", "unknown"))

    async def is_done(self, batch_id: str) -> bool:
        return await self.status(batch_id) == TERMINAL_STATUS

    async def results(self, batch_id: str) -> list[BatchResultItem]:
        """Lấy kết quả (chỉ gọi khi status == 'ended'). Map theo custom_id;
        item lỗi/expired/canceled → succeeded=False + error, KHÔNG raise (để
        1 item hỏng không làm hỏng cả mẻ)."""
        out: list[BatchResultItem] = []
        stream = await self._client.messages.batches.results(batch_id)
        async for r in stream:
            rtype = getattr(getattr(r, "result", None), "type", None)
            custom_id = str(getattr(r, "custom_id", ""))
            if rtype == "succeeded":
                msg = getattr(r.result, "message", None)
                out.append(
                    BatchResultItem(
                        custom_id=custom_id,
                        succeeded=True,
                        text=self._extract_text(msg),
                    )
                )
            else:
                err_obj = getattr(r.result, "error", None)
                err = getattr(err_obj, "type", None) or (rtype or "unknown")
                out.append(
                    BatchResultItem(
                        custom_id=custom_id, succeeded=False, error=str(err)
                    )
                )
        logger.info(
            "llm_batch_results",
            batch_id=batch_id,
            total=len(out),
            failed=sum(1 for x in out if not x.succeeded),
        )
        return out

    @staticmethod
    def _extract_text(msg: Any) -> str:
        parts: list[str] = []
        for block in getattr(msg, "content", []) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts)

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:
                logger.debug("anthropic_batch_close_noop")
