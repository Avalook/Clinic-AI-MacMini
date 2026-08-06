"""Customer-care endpoints (W5, ADR-0012)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.cskh_service import (
    INTAKE_ROLES,
    CskhService,
    clinic_today,
)
from clinicai.services.recall_service import RecallService

router = APIRouter()

_INTAKE_GUARD = require_role(*INTAKE_ROLES)
_RECALL_GUARD = require_role(
    ClinicRole.CSKH,
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
)


class CskhActionRequest(BaseModel):
    """One manually entered piece of care work."""

    category: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    status: str | None = Field(default=None, max_length=120)
    # Optional, but a code that matches nothing is an error rather than a
    # record filed against no patient.
    patient_code: str | None = Field(default=None, max_length=64)


class CskhFollowupRequest(BaseModel):
    """A recall reminder call that was actually made."""

    clinic_patient_id: UUID
    note: str | None = Field(default=None, max_length=2000)


class RecallFollowupRead(BaseModel):
    clinic_patient_id: str
    full_name: str
    phone_primary: str | None
    due_date: date
    repeat_tests: list[str]
    instruction: str
    # Ngày gọi nhắc gần nhất (từ cskh_log), None nếu chưa gọi lần nào.
    last_called_date: date | None = None


@router.get("/cskh/recalls", response_model=list[RecallFollowupRead])
async def read_due_recalls(
    identity: StaffIdentity = Depends(_RECALL_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[RecallFollowupRead]:
    """Return the minimum recall projection, never the underlying SOAP note."""
    rows = await RecallService(pool).due_followups(
        clinic_id=identity.clinic_id,
        today=date.fromisoformat(clinic_today()),
    )
    return [RecallFollowupRead(**vars(row)) for row in rows]


@router.post("/cskh/actions", status_code=201)
async def record_cskh_action(
    body: CskhActionRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Log care work that was done by hand rather than captured automatically."""
    action_id = await CskhService(pool).record_action(
        category=body.category,
        description=body.description,
        status=body.status,
        patient_code=body.patient_code,
        identity=identity,
    )
    return {"ok": True, "id": action_id}


@router.post("/cskh/followup-calls", status_code=201)
async def record_followup_call(
    body: CskhFollowupRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Record that an overdue patient was called about coming back."""
    log_id = await CskhService(pool).record_followup_call(
        clinic_patient_id=str(body.clinic_patient_id),
        note=body.note,
        identity=identity,
    )
    return {"ok": True, "id": log_id}
