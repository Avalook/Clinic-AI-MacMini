"""Progress flags for the day board (ROLE-02, ADR-0012)."""

from __future__ import annotations

from datetime import date

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.visit_progress_service import VisitProgressService

router = APIRouter()


class VisitProgressRead(BaseModel):
    appointment_id: str
    visit_id: str | None
    vitals_recorded: bool
    has_clinical_record: bool
    has_prescription: bool
    paid_kinds: list[str]


@router.get("/visits/progress", response_model=list[VisitProgressRead])
async def read_visit_progress(
    date_from: date = Query(..., alias="from", description="Từ ngày (giờ VN)"),
    date_to: date = Query(
        ..., alias="to", description="Đến ngày (giờ VN), gồm cả ngày này"
    ),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[VisitProgressRead]:
    """How far each of today's patients has got: vitals, exam, prescription, fees.

    Open to any signed-in staff member on purpose — it is the progress bar the
    front desk has always seen. What changed is that it returns flags instead of
    the doctor's note, which is what let the note's read policy be closed to
    non-clinical roles.
    """
    rows = await VisitProgressService(pool).for_range(
        date_from=date_from, date_to=date_to, clinic_id=identity.clinic_id
    )
    return [VisitProgressRead(**vars(r)) for r in rows]
