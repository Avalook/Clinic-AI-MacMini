"""Tool: scheduling.find_oncall — list on-duty staff for a work session."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from pydantic import BaseModel

from clinicai.api.exceptions import WorkSessionNotFoundError
from clinicai.services.scheduling_service import SchedulingService
from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    import asyncpg

logger = structlog.get_logger()


class FindOncallInput(BaseModel):
    """Input schema for the scheduling.find_oncall tool."""

    work_session_id: UUID
    ctx: TraceContext


class OncallStaffOutput(BaseModel):
    """List of on-duty staff for the given work session."""

    work_session_id: UUID
    on_duty_staff: list[dict[str, Any]]
    doctor_ids: list[UUID]
    trace_id: UUID


async def find_oncall_staff(
    input: FindOncallInput,
    pool: asyncpg.Pool,
) -> OncallStaffOutput:
    """Return on-duty staff. Raises WorkSessionNotFoundError if session missing."""
    logger.info(
        "tool.scheduling.find_oncall",
        work_session_id=str(input.work_session_id),
        trace_id=str(input.ctx.trace_id),
    )

    service = SchedulingService(pool)
    data = await service.get_oncall_staff(input.work_session_id)

    if data is None:
        raise WorkSessionNotFoundError(
            f"Work session {input.work_session_id} not found"
        )

    staff_rows = data["staff"]
    on_duty_staff = [
        {
            "staff_id": row["staff_id"],
            "full_name": row["full_name"],
            "role": row["role"],
            "station": row["station"],
        }
        for row in staff_rows
    ]
    doctor_ids = [
        row["staff_id"] for row in staff_rows if str(row["role"]).upper() == "DOCTOR"
    ]

    return OncallStaffOutput(
        work_session_id=input.work_session_id,
        on_duty_staff=on_duty_staff,
        doctor_ids=doctor_ids,
        trace_id=input.ctx.trace_id,
    )
