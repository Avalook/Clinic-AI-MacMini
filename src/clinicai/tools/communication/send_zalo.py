"""Tool: communication.send_zalo — STUB Phase 6, real implementation Phase 12."""

from __future__ import annotations

from uuid import UUID

import structlog
from pydantic import BaseModel

from clinicai.tools._common.context import TraceContext

logger = structlog.get_logger()

_PREVIEW_LEN = 50


class SendZaloInput(BaseModel):
    """Input schema for communication.send_zalo."""

    patient_id: UUID
    message: str
    template_key: str | None = None
    ctx: TraceContext


class SendZaloOutput(BaseModel):
    """Returned from the stub. `delivered` is always False until Phase 12."""

    patient_id: UUID
    delivered: bool
    stub: bool = True
    message_preview: str
    trace_id: UUID


async def send_zalo_message(input: SendZaloInput) -> SendZaloOutput:
    """STUB — do not call Zalo API. Logs the intent and returns delivered=False."""
    logger.info(
        "tool.communication.send_zalo_stub",
        patient_id=str(input.patient_id),
        template_key=input.template_key,
        trace_id=str(input.ctx.trace_id),
    )
    return SendZaloOutput(
        patient_id=input.patient_id,
        delivered=False,
        message_preview=input.message[:_PREVIEW_LEN],
        trace_id=input.ctx.trace_id,
    )
