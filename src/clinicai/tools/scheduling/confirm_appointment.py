"""Tool: scheduling.confirm_appointment — wrap SchedulingService.confirm_appointment."""

from __future__ import annotations

from uuid import UUID

import structlog
from pydantic import BaseModel

from clinicai.services.scheduling_service import SchedulingService

logger = structlog.get_logger()


class ConfirmAppointmentInput(BaseModel):
    """Input schema for confirm_appointment tool."""

    appointment_id: UUID


class ConfirmAppointmentOutput(BaseModel):
    """Output schema after successful confirmation."""

    appointment_id: UUID
    status: str
    confirmed_at: str


async def confirm_appointment(
    input: ConfirmAppointmentInput,
    service: SchedulingService,
) -> ConfirmAppointmentOutput:
    """Confirm a SCHEDULED appointment, transitioning it to CONFIRMED."""
    logger.info(
        "tool.scheduling.confirm_appointment",
        appointment_id=str(input.appointment_id),
    )

    result = await service.confirm_appointment(input.appointment_id)

    return ConfirmAppointmentOutput(
        appointment_id=input.appointment_id,
        status="CONFIRMED",
        confirmed_at=result.confirmed_at.isoformat() if result.confirmed_at else "",
    )
