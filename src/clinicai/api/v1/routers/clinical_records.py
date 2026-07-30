"""Clinical record writes (W5, ADR-0012).

The router admits every role that can write in *either* mode; which mode each
one is allowed is a rule about the record, so it lives in the service next to
the rest of them.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.clinical_record_service import ClinicalRecordService

router = APIRouter()

_RECORD_GUARD = require_role(
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK,
    ClinicRole.NURSE_ULTRASOUND,
    # Reception reaches this only with vitals_only=true; the service enforces it.
    ClinicRole.RECEPTION,
)


class PrescriptionItem(BaseModel):
    drug_name: str | None = None
    quantity: str | None = None
    dosage: str | None = None
    caution: str | None = None


class ClinicalRecordSaveRequest(BaseModel):
    appointment_id: UUID
    clinic_patient_id: UUID
    # Nurse/reception mode: vitals and the chief complaint only.
    vitals_only: bool = False
    chief_complaint: str | None = Field(default=None, max_length=2000)
    subjective: Any = None
    objective: Any = None
    assessment: Any = None
    plan: Any = None
    profile: dict[str, Any] | None = None
    # None means "leave the prescription alone"; [] means "clear it".
    prescriptions: list[PrescriptionItem] | None = None


@router.post("/clinical-records")
async def save_clinical_record(
    body: ClinicalRecordSaveRequest,
    identity: StaffIdentity = Depends(_RECORD_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Write the record for an appointment's visit, creating a draft if needed."""
    result = await ClinicalRecordService(pool).save(
        appointment_id=str(body.appointment_id),
        clinic_patient_id=str(body.clinic_patient_id),
        identity=identity,
        vitals_only=body.vitals_only,
        chief_complaint=body.chief_complaint,
        subjective=body.subjective,
        objective=body.objective,
        # "objective was absent" and "objective was sent as {}" mean different
        # things to the merge, and model_fields_set is the only way to tell.
        objective_sent="objective" in body.model_fields_set,
        assessment=body.assessment,
        plan=body.plan,
        profile=body.profile,
        prescriptions=(
            [item.model_dump() for item in body.prescriptions]
            if body.prescriptions is not None
            else None
        ),
    )
    return {"ok": True, **result}
