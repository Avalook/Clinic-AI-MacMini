"""FastAPI endpoints for visit payments (Phase 4, cluster #3).

Thin router: server-authoritative role via ``require_role`` (identity #1a), then
delegate to ``PaymentService``. Domain errors (ConflictError/NotFoundError/
SafetyGateError) are mapped to HTTP by the global handlers in ``main.py``.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from clinicai.api.idempotency import IdempotencyGuard, idempotency_guard
from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.payment_service import PaymentService

router = APIRouter()

# Roles allowed to touch payments at all; the finer kind↔role rule is in the service.
_CASHIER_GUARD = require_role(
    ClinicRole.CASHIER,
    ClinicRole.CASHIER_THUOC,
    ClinicRole.CASHIER_DV,
    ClinicRole.MANAGEMENT,
)

PaymentKind = Literal["thuoc", "dich_vu"]


class PaymentRecordRequest(BaseModel):
    """Body for recording a payment."""

    visit_id: UUID
    kind: PaymentKind
    amount: float | None = None
    clinic_patient_id: UUID | None = None


class PaymentVoidRequest(BaseModel):
    """Body for voiding (undoing) a payment."""

    visit_id: UUID
    kind: PaymentKind


@router.post("/payments")
async def record_payment(
    body: PaymentRecordRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, bool]:
    """Record (upsert) a PAID payment once the visit's appointment is COMPLETED."""
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    service = PaymentService(pool)
    await service.record_payment(
        visit_id=str(body.visit_id),
        kind=body.kind,
        amount=body.amount,
        clinic_patient_id=(
            str(body.clinic_patient_id) if body.clinic_patient_id else None
        ),
        identity=identity,
    )
    result = {"ok": True}
    await idem.save(pool, result, status_code=200)
    return result


@router.delete("/payments")
async def void_payment(
    body: PaymentVoidRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, bool]:
    """Void (delete) a payment. Not gated on exam status."""
    service = PaymentService(pool)
    await service.void_payment(
        visit_id=str(body.visit_id),
        kind=body.kind,
        identity=identity,
    )
    return {"ok": True}
