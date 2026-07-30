"""Foetal ultrasound measurements (W5, ADR-0012).

Thin router. The gate is ULTRASOUND_DOCTOR and nothing wider — the clinic asked
for that specifically, so it is stated here rather than folded into a general
"clinical writer" role.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.ultrasound_service import UltrasoundService

router = APIRouter()

_SONOGRAPHER_GUARD = require_role(ClinicRole.ULTRASOUND_DOCTOR)


class UltrasoundMeasurements(BaseModel):
    """The seven standard foetal measurements: six in mm, EFW in grams.

    EFW is typed in by the doctor. It is NOT derived from BPD/HC/AC/FL, and
    should not be until the clinic signs off on a formula — see the service.
    """

    crl: float | str | None = None
    nt: float | str | None = None
    bpd: float | str | None = None
    hc: float | str | None = None
    ac: float | str | None = None
    fl: float | str | None = None
    efw: float | str | None = None


class UltrasoundSaveRequest(BaseModel):
    appointment_id: UUID
    clinic_patient_id: UUID
    measurements: UltrasoundMeasurements | None = None
    # Abnormality is the doctor's call, never inferred from the numbers.
    is_abnormal: bool | None = None
    status: Literal["in_progress", "completed"] | None = None
    note: str | None = Field(default=None, max_length=2000)


@router.post("/ultrasound/measurements")
async def save_ultrasound_measurements(
    body: UltrasoundSaveRequest,
    identity: StaffIdentity = Depends(_SONOGRAPHER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Attach measurements to the appointment's visit, creating it if needed."""
    findings = await UltrasoundService(pool).save_measurements(
        appointment_id=str(body.appointment_id),
        clinic_patient_id=str(body.clinic_patient_id),
        measurements=(
            body.measurements.model_dump(exclude_unset=True)
            if body.measurements is not None
            else None
        ),
        is_abnormal=body.is_abnormal,
        status=body.status,
        identity=identity,
    )
    return {"ok": True, "findings": findings}
