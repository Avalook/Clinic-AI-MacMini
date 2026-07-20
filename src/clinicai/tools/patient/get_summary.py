"""Tool: patient.get_summary — return a thin summary view of a patient."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from pydantic import BaseModel

from clinicai.api.exceptions import PatientNotFoundError
from clinicai.services.patient_service import PatientService
from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    import asyncpg

logger = structlog.get_logger()


class GetPatientSummaryInput(BaseModel):
    """Input schema for the patient.get_summary tool."""

    patient_id: UUID
    ctx: TraceContext


class PatientSummaryOutput(BaseModel):
    """Trimmed patient view — only fields safe for routing/agent decisions."""

    patient_id: UUID
    patient_code: str
    full_name: str
    phone: str | None
    date_of_birth: date | None
    last_visit_date: date | None
    active_pregnancy: bool
    trace_id: UUID


async def get_patient_summary(
    input: GetPatientSummaryInput,
    pool: asyncpg.Pool,
) -> PatientSummaryOutput:
    """Fetch patient + summary fields. Raises PatientNotFoundError if absent."""
    logger.info(
        "tool.patient.get_summary",
        patient_id=str(input.patient_id),
        trace_id=str(input.ctx.trace_id),
    )

    service = PatientService(pool)
    row = await service.get_summary_data(input.patient_id)

    if row is None:
        raise PatientNotFoundError(f"Patient {input.patient_id} not found")

    return PatientSummaryOutput(
        patient_id=row["clinic_patient_id"],
        patient_code=row["patient_code"],
        full_name=row["full_name"],
        phone=row["phone_primary"],
        date_of_birth=row["date_of_birth"],
        last_visit_date=row["last_visit_date"],
        active_pregnancy=bool(row["active_pregnancy"]),
        trace_id=input.ctx.trace_id,
    )
