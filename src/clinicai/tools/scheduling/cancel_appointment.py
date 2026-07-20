"""Tool: scheduling.cancel_appointment — wrap SchedulingService.cancel_appointment."""

from __future__ import annotations

from uuid import UUID

import structlog
from pydantic import BaseModel

from clinicai.services.scheduling_service import SchedulingService

logger = structlog.get_logger()


class CancelAppointmentInput(BaseModel):
    """Input schema for cancel_appointment tool."""

    appointment_id: UUID
    cancellation_reason: str


class CancelAppointmentOutput(BaseModel):
    """Output schema after successful cancellation."""

    appointment_id: UUID
    status: str


async def cancel_appointment(
    input: CancelAppointmentInput,
    service: SchedulingService,
) -> CancelAppointmentOutput:
    """Cancel an appointment with a recorded reason."""
    logger.info(
        "tool.scheduling.cancel_appointment",
        appointment_id=str(input.appointment_id),
    )

    await service.cancel_appointment(
        input.appointment_id,
        input.cancellation_reason,
    )

    return CancelAppointmentOutput(
        appointment_id=input.appointment_id,
        status="CANCELLED",
    )
