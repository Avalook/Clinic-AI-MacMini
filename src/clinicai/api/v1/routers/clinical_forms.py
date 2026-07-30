"""Specialty exam forms (W5, ADR-0012)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.clinical_form_service import ClinicalFormService

router = APIRouter()

# Filling in an exam form is clinical work.
_FORM_WRITE_GUARD = require_role(*CLINICAL_WRITE_ROLES)


class ClinicalFormSaveRequest(BaseModel):
    visit_id: UUID
    service_code: str = Field(min_length=1, max_length=64)
    form_data: dict[str, Any] = Field(default_factory=dict)


@router.get("/clinical-forms")
async def read_clinical_form(
    visit_id: UUID,
    service_code: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Read one form. Any authenticated staff member may look at it."""
    return await ClinicalFormService(pool).get_form(
        visit_id=str(visit_id), service_code=service_code, identity=identity
    )


@router.put("/clinical-forms")
async def save_clinical_form(
    body: ClinicalFormSaveRequest,
    identity: StaffIdentity = Depends(_FORM_WRITE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Upsert one form. Refused once the visit is FINALIZED (ADR-0008)."""
    await ClinicalFormService(pool).save_form(
        visit_id=str(body.visit_id),
        service_code=body.service_code,
        form_data=body.form_data,
        identity=identity,
    )
    return {"ok": True}
