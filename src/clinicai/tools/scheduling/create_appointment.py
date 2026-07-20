"""Tool: scheduling.create_appointment — wrap SchedulingService.create_appointment.

Catches the GIST exclusion constraint violation (Medical Safety Gate against
double-booking) and surfaces it as AppointmentConflictError for the orchestrator
to handle politely.
"""

from __future__ import annotations

import datetime
from uuid import UUID

import asyncpg
import structlog
from pydantic import BaseModel

from clinicai.core.exceptions import ValidationError
from clinicai.schemas.scheduling import AppointmentCreateDTO
from clinicai.services.scheduling_service import SchedulingService

logger = structlog.get_logger()


class AppointmentConflictError(Exception):
    """Raised when the GIST exclusion constraint rejects the booking.

    Acts as the Medical Safety Gate signal: another appointment already
    occupies the requested slot for this doctor.
    """


class CreateAppointmentInput(BaseModel):
    """Input schema for create_appointment tool."""

    clinic_patient_id: UUID
    work_session_id: UUID
    doctor_id: UUID | None = None
    location_id: UUID
    service_type_id: UUID
    slot_start: datetime.datetime
    slot_end: datetime.datetime
    booking_channel: str = "AI_CHAT"
    is_walkin: bool = False


class CreateAppointmentOutput(BaseModel):
    """Output schema returned after a successful booking."""

    appointment_id: UUID
    status: str
    queue_number: str | None


async def create_appointment(
    input: CreateAppointmentInput,
    service: SchedulingService,
) -> CreateAppointmentOutput:
    """Create an appointment via SchedulingService.

    Wraps SchedulingService.create_appointment so callers can pass a flat
    input model. Surfaces GIST exclusion violations as AppointmentConflictError.
    """
    logger.info(
        "tool.scheduling.create_appointment",
        clinic_patient_id=str(input.clinic_patient_id),
        work_session_id=str(input.work_session_id),
        doctor_id=str(input.doctor_id) if input.doctor_id else None,
    )

    dto = AppointmentCreateDTO(
        clinic_patient_id=input.clinic_patient_id,
        doctor_id=input.doctor_id,
        work_session_id=input.work_session_id,
        location_id=input.location_id,
        service_type_id=input.service_type_id,
        booking_channel=input.booking_channel,
        slot_start=input.slot_start,
        slot_end=input.slot_end,
        is_walkin=input.is_walkin,
    )

    try:
        result = await service.create_appointment(dto)
    except asyncpg.exceptions.ExclusionViolationError as exc:
        raise AppointmentConflictError(
            "Bác sĩ đã có lịch trong khung giờ này."
        ) from exc
    except ValidationError as exc:
        if "trùng khung giờ" in str(exc):
            raise AppointmentConflictError(str(exc)) from exc
        raise

    return CreateAppointmentOutput(
        appointment_id=result.id,
        status=result.status,
        queue_number=result.queue_number,
    )
