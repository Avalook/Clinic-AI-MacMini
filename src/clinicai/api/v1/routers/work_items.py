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

from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from clinicai.api.idempotency import IdempotencyGuard, idempotency_guard
from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.service_order_service import ServiceOrderService
from clinicai.services.work_item_service import WorkItemService

router = APIRouter()

# The clinic's day, not the server's.
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

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

# A worklist is a patient-data surface.  The general work-item guard admits
# every role that can participate somewhere in the workflow, but that does not
# make an arbitrary ``workspace`` query safe.  Resolve read authority from the
# live node catalogue: a role may open a workspace when it is an actor on at
# least one node there.  Management and the shift lead retain their explicit
# cross-station coordination view.  This mirrors the server-rendered nav gate,
# so hiding a link can never be the only protection for a direct API request.
_WORKSPACE_COORDINATOR_ROLES = frozenset({ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA})


async def require_workspace_read_access(
    *,
    workspace: str,
    identity: StaffIdentity,
    pool: asyncpg.Pool,
) -> None:
    """Fail closed before a workspace query can expose another station's PII."""
    if identity.role in _WORKSPACE_COORDINATOR_ROLES:
        return

    may_read = await pool.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
             FROM node_definition n
             WHERE n.clinic_id = $1::uuid
               AND n.workspace = $2
               -- ``{}`` is deliberately "nobody yet" in the catalogue, so
               -- neither an empty nor a NULL actor list may grant a read.
               AND $3 = ANY(n.actor_roles)
        )
        """,
        identity.clinic_id,
        workspace,
        identity.role.value,
    )
    if not may_read:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vai trò của bạn không được xem khu vực công việc này",
        )


async def require_visit_work_items_read_access(
    *,
    visit_id: str,
    identity: StaffIdentity,
    pool: asyncpg.Pool,
) -> None:
    """Authorize a visit projection without turning its UUID into a PII key.

    The visit projection lets a legitimate actor identify the patient attached
    to work at their own station.  It cannot be a generic patient lookup:
    ordinary roles must own one *ready or in-progress* node on that visit, and
    the service row-scopes the projection to their nodes.  Return the same 403
    for a missing and an unauthorized visit so the endpoint does not become an
    identifier oracle.
    """
    if identity.role in _WORKSPACE_COORDINATOR_ROLES:
        return

    may_read = await pool.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
              FROM work_item w
              JOIN node_definition n
                ON n.clinic_id = w.clinic_id
               AND n.code = w.node_code
             WHERE w.visit_id = $1::uuid
               AND w.clinic_id = $2::uuid
               -- Do not let a future or terminal step make a raw visit UUID
               -- into a cross-station PII lookup.  Instantiation creates
               -- downstream work as PENDING, so PENDING alone is not current:
               -- it must also have no start gate blockers.  IN_PROGRESS is
               -- current by definition.
               AND (
                    w.status = 'IN_PROGRESS'
                    OR (
                        w.status = 'PENDING'
                        AND NOT EXISTS (
                            SELECT 1
                              FROM work_item_gate_blockers(w.id, 'start')
                        )
                    )
               )
               AND $3 = ANY(n.actor_roles)
        )
        """,
        visit_id,
        identity.clinic_id,
        identity.role.value,
    )
    if not may_read:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vai trò của bạn không được xem hành trình lượt khám này",
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


class WorklistPatient(BaseModel):
    clinic_patient_id: UUID | None = None
    patient_code: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    phone_primary: str | None = None


class VisitWorkItem(BaseModel):
    """One step of a visit, as the board needs to draw it."""

    id: UUID
    node_code: str
    node_name: str | None = None
    flow_group: str | None = None
    workspace: str | None = None
    status: str
    priority: str
    version: int
    assigned_role: str | None = None
    assigned_to: UUID | None = None
    actor_roles: list[str] = Field(default_factory=list)
    # Whether THIS caller's role is on the node's actor list, and whether the
    # gates are still shut. Together they are the difference between a button
    # that is hidden, greyed out, or live — computed here so every client draws
    # it the same way and none of them re-implements the rule.
    actionable_by_me: bool
    blocked: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Who the step is about. Every row of one visit carries the same patient,
    # which is redundant on the wire but keeps one shape for "who is this work
    # about" across both boards, so no client has to learn two of them.
    patient: WorklistPatient


class WorklistItem(BaseModel):
    """One row of a workspace's queue."""

    id: UUID
    node_code: str
    node_name: str | None = None
    status: str
    priority: str
    version: int
    visit_id: UUID | None = None
    appointment_id: UUID | None = None
    assigned_to: UUID | None = None
    assigned_role: str | None = None
    actor_roles: list[str] = Field(default_factory=list)
    actionable_by_me: bool
    blocked: bool
    due_at: datetime | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    patient: WorklistPatient
    queue_number: str | None = None
    slot_start: datetime | None = None
    booking_channel: str | None = None
    is_priority_slot: bool = False
    checked_in_at: datetime | None = None


@router.get("/work-items", response_model=list[WorklistItem])
async def worklist(
    workspace: str = Query(min_length=1, max_length=64),
    day: date | None = Query(default=None, alias="date"),
    mine_only: bool = Query(default=False),
    identity: StaffIdentity = Depends(_WORK_ITEM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[WorklistItem]:
    """A workspace's open work — the front desk's own queue.

    `workspace` comes from the node catalogue, so what appears on a board is a
    property of the clinic's configuration rather than of this function.

    With no `date`, this returns everything still open rather than only today's.
    A queue that resets at midnight loses the patient who is still sitting
    there, which is the one person it must not lose.
    """
    await require_workspace_read_access(
        workspace=workspace, identity=identity, pool=pool
    )
    rows = await WorkItemService(pool).list_worklist(
        workspace=workspace,
        day=day,
        identity=identity,
        mine_only=mine_only,
    )
    return [WorklistItem(**row) for row in rows]  # type: ignore[arg-type]


@router.get("/visits/{visit_id}/work-items", response_model=list[VisitWorkItem])
async def visit_work_items(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_WORK_ITEM_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[VisitWorkItem]:
    """The visit's steps, in flow order.

    Cancelled items are omitted: an undone arrival leaves a cancelled
    generation behind as history, and a board that showed it would be showing
    work nobody is expected to do.
    """
    await require_visit_work_items_read_access(
        visit_id=str(visit_id), identity=identity, pool=pool
    )
    rows = await WorkItemService(pool).list_for_visit(
        visit_id=str(visit_id), identity=identity
    )
    return [VisitWorkItem(**row) for row in rows]  # type: ignore[arg-type]


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


# ---------------------------------------------------------------------------
# Chỉ định dịch vụ — what LUOTKHAM-05 produces
# ---------------------------------------------------------------------------

_ORDERING_ROLES = require_role(
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK,
)


class CatalogueEntry(BaseModel):
    service_code: str
    name: str
    group: str | None = None
    category: str | None = None
    unit_price: float | None = None
    node_code: str | None = None
    node_name: str | None = None
    workspace: str | None = None
    # False when the clinic has not said which node performs it. Shown greyed
    # with a reason rather than hidden: a missing row reads as a bug, a visibly
    # unconfigured row reads as configuration.
    orderable: bool


class OrderRequest(BaseModel):
    service_codes: list[str] = Field(min_length=1, max_length=50)


class OrderedRoom(BaseModel):
    node_code: str
    work_item_id: UUID
    service_count: int
    created: bool


class DuplicateService(BaseModel):
    service_code: str
    name: str | None = None
    ordered_at: datetime


@router.get("/service-catalogue", response_model=list[CatalogueEntry])
async def service_catalogue(
    identity: StaffIdentity = Depends(_ORDERING_ROLES),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[CatalogueEntry]:
    """The clinic's orderable services, with the room each one is performed in."""
    rows = await ServiceOrderService(pool).catalogue(identity=identity)
    return [CatalogueEntry(**r) for r in rows]  # type: ignore[arg-type]


@router.post("/visits/{visit_id}/service-orders", response_model=list[OrderedRoom])
async def order_services(
    visit_id: UUID,
    body: OrderRequest,
    identity: StaffIdentity = Depends(_ORDERING_ROLES),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[OrderedRoom]:
    """Order services on a visit; work appears in the room that performs each.

    Does not complete LUOTKHAM-05 — see ServiceOrderService for why.
    """
    rows = await ServiceOrderService(pool).create(
        visit_id=str(visit_id), codes=body.service_codes, identity=identity
    )
    return [OrderedRoom(**r) for r in rows]  # type: ignore[arg-type]


@router.post(
    "/visits/{visit_id}/service-orders/duplicates",
    response_model=list[DuplicateService],
)
async def check_duplicates(
    visit_id: UUID,
    body: OrderRequest,
    identity: StaffIdentity = Depends(_ORDERING_ROLES),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[DuplicateService]:
    """Which of these the patient already had ordered in the last 30 days.

    POST because the list of codes is the question and can be long; nothing is
    written.
    """
    rows = await ServiceOrderService(pool).duplicates(
        visit_id=str(visit_id), codes=body.service_codes, identity=identity
    )
    return [DuplicateService(**r) for r in rows]  # type: ignore[arg-type]


_CASHIER_ROLES = require_role(
    ClinicRole.CASHIER,
    ClinicRole.CASHIER_THUOC,
    ClinicRole.CASHIER_DV,
    ClinicRole.TRUONG_CA,
    ClinicRole.MANAGEMENT,
    # The doctor who raised the orders may see what they cost. Reception may
    # not: closing a visit is theirs, the money is not.
    ClinicRole.DOCTOR,
)


class ChargeLine(BaseModel):
    node_code: str
    node_name: str | None = None
    node_status: str
    service_code: str | None = None
    name: str | None = None
    unit_price: float | None = None


class PaymentLine(BaseModel):
    id: UUID
    kind: str | None = None
    status: str | None = None
    amount: float
    paid_at: datetime | None = None
    voided_at: datetime | None = None
    void_reason: str | None = None


class VisitCharges(BaseModel):
    visit_id: UUID
    visit_status: str | None = None
    lines: list[ChargeLine]
    payments: list[PaymentLine]
    line_count: int
    unpriced_lines: int
    subtotal: float
    collected: float
    outstanding: float


@router.get("/visits/{visit_id}/charges", response_model=VisitCharges)
async def visit_charges(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_CASHIER_ROLES),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> VisitCharges:
    """What the visit owes for and what has been paid.

    Lines come from the work items, because the work item is the order. See
    ServiceOrderService.charges — in particular why `unpriced_lines` is part of
    the contract rather than an implementation detail.
    """
    data = await ServiceOrderService(pool).charges(
        visit_id=str(visit_id), identity=identity
    )
    return VisitCharges(**data)  # type: ignore[arg-type]
