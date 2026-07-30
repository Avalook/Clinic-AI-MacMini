"""Work-item Command API (W4, ADR-0011, doc §4.3).

Four commands, one per URL, because the frontend states an intent and the
backend decides whether it is allowed — there is deliberately no endpoint that
takes a status. Every command requires an ``Idempotency-Key``: a retried
check-in must not become two.

Role authorisation happens twice on purpose. ``require_role`` keeps roles that
never touch the flow out of the router at all, and the service then checks the
caller against the actor list of the specific node — which is configuration, so
it cannot live in a decorator.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.idempotency import IdempotencyGuard, idempotency_guard
from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.work_item_service import WorkItemService

router = APIRouter()

# Every clinical and front-desk role works the flow; the node's own actor list
# is what narrows it per station.
_WORK_ITEM_GUARD = require_role(
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.NURSE_ULTRASOUND,
    ClinicRole.TKYK,
    ClinicRole.RECEPTION,
    ClinicRole.CSKH,
    ClinicRole.CASHIER,
    ClinicRole.CASHIER_THUOC,
    ClinicRole.CASHIER_DV,
    ClinicRole.TRUONG_CA,
    ClinicRole.MANAGEMENT,
)


class CommandRequest(BaseModel):
    """Optional body for a work-item command."""

    # The version the caller last read. Sending it turns a concurrent edit into
    # a 409 instead of a silent overwrite; omitting it accepts last-write-wins.
    expected_version: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=500)


class CommandResponse(BaseModel):
    id: UUID
    status: str
    version: int


async def _run(
    command: Literal["start", "complete", "skip", "cancel"],
    work_item_id: UUID,
    body: CommandRequest | None,
    identity: StaffIdentity,
    pool: asyncpg.Pool,
    idem: IdempotencyGuard,
) -> dict[str, object]:
    # acquire() returns a NEW guard — IdempotencyGuard is frozen, so not
    # reassigning it silently disables replay protection and then makes
    # save() raise. Matches the payment router.
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]

    payload = body or CommandRequest()
    result = await WorkItemService(pool).issue(
        work_item_id=str(work_item_id),
        command=command,
        identity=identity,
        expected_version=payload.expected_version,
        reason=payload.reason,
    )
    await idem.save(pool, result, status_code=200)
    return result


@router.post(
    "/work-items/{work_item_id}/commands/start", response_model=CommandResponse
)
async def start_work_item(
    work_item_id: UUID,
    body: CommandRequest | None = None,
    identity: StaffIdentity = Depends(_WORK_ITEM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, object]:
    """Begin work. Refused while a blocking FS/SS predecessor is unfinished."""
    return await _run("start", work_item_id, body, identity, pool, idem)


@router.post(
    "/work-items/{work_item_id}/commands/complete", response_model=CommandResponse
)
async def complete_work_item(
    work_item_id: UUID,
    body: CommandRequest | None = None,
    identity: StaffIdentity = Depends(_WORK_ITEM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, object]:
    """Finish work. Refused while a blocking FF/SF predecessor is unfinished."""
    return await _run("complete", work_item_id, body, identity, pool, idem)


@router.post("/work-items/{work_item_id}/commands/skip", response_model=CommandResponse)
async def skip_work_item(
    work_item_id: UUID,
    body: CommandRequest | None = None,
    identity: StaffIdentity = Depends(_WORK_ITEM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, object]:
    """Declare the step will not happen. Never gated — this unsticks a flow."""
    return await _run("skip", work_item_id, body, identity, pool, idem)


@router.post(
    "/work-items/{work_item_id}/commands/cancel", response_model=CommandResponse
)
async def cancel_work_item(
    work_item_id: UUID,
    body: CommandRequest | None = None,
    identity: StaffIdentity = Depends(_WORK_ITEM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, object]:
    """Call the step off. Unlike skip, successors stay blocked."""
    return await _run("cancel", work_item_id, body, identity, pool, idem)


@router.get("/work-items/{work_item_id}/blockers")
async def work_item_blockers(
    work_item_id: UUID,
    phase: Literal["start", "complete"] = Query(default="start"),
    identity: StaffIdentity = Depends(_WORK_ITEM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """What is still in the way — so the UI can say why a button is disabled."""
    blockers = await WorkItemService(pool).blockers(
        work_item_id=str(work_item_id),
        phase=phase,
        identity=identity,
    )
    return {"phase": phase, "blockers": blockers, "open": not blockers}
