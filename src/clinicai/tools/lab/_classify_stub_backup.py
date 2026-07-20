"""Tool: lab.classify — STUB Phase 6, real implementation Phase 9.4."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import structlog
from pydantic import BaseModel

from clinicai.tools._common.context import TraceContext

logger = structlog.get_logger()

LabClass = Literal["GROUP_A", "GROUP_B", "GROUP_C", "PENDING"]


class ClassifyLabInput(BaseModel):
    """Input schema for lab.classify."""

    lab_result_id: UUID
    ctx: TraceContext


class LabClassificationOutput(BaseModel):
    """Stub classification — always PENDING until the triage graph is live."""

    lab_result_id: UUID
    classification: LabClass
    requires_doctor_review: bool
    stub: bool = True
    trace_id: UUID


async def classify_lab_result(
    input: ClassifyLabInput,
) -> LabClassificationOutput:
    """STUB — Phase 9.4 will replace with the real lab-triage graph."""
    logger.info(
        "tool.lab.classify_stub",
        lab_result_id=str(input.lab_result_id),
        trace_id=str(input.ctx.trace_id),
    )
    return LabClassificationOutput(
        lab_result_id=input.lab_result_id,
        classification="PENDING",
        requires_doctor_review=False,
        trace_id=input.ctx.trace_id,
    )
