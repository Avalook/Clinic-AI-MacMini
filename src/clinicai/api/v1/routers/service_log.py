"""Services worklist and the ultrasound queue (W5, ADR-0012).

Two screens, two role gates, one table — see the service module for why the
status vocabularies differ and why that is preserved rather than tidied here.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES,
    StaffIdentity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.service_log_service import (
    MILESTONE_COLUMN,
    QUEUE_WAITING,
    SONO_ROLES,
    Milestone,
    QueueAction,
    ServiceLogService,
    TaskAction,
    queue_patch,
    task_patch,
)

router = APIRouter()

# Recording a service is clinical work — reception and management excluded
# (decided 2026-06-17, same as lab results).
_SERVICE_GUARD = require_role(*CLINICAL_WRITE_ROLES)
# The sono queue belongs to the ultrasound nurse.
_SONO_GUARD = require_role(*SONO_ROLES)


class ServiceCreateRequest(BaseModel):
    service_name: str = Field(min_length=1, max_length=300)
    patient_code: str | None = Field(default=None, max_length=64)
    performer: str | None = Field(default=None, max_length=200)


class ServiceProgressRequest(BaseModel):
    action: TaskAction
    result_text: str | None = Field(default=None, max_length=4000)


class SonoCreateRequest(BaseModel):
    # SA = ultrasound, XN = lab. The two behave differently from here on.
    kind: str = Field(pattern="^(SA|XN)$")
    service_name: str = Field(min_length=1, max_length=300)
    patient_code: str | None = Field(default=None, max_length=64)


class SonoProgressRequest(BaseModel):
    """Either a status move (SA) or a milestone toggle (XN), never both."""

    action: QueueAction | None = None
    milestone: Milestone | None = None
    value: bool | None = None


@router.post("/service-log", status_code=201)
async def create_service_item(
    body: ServiceCreateRequest,
    identity: StaffIdentity = Depends(_SERVICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Add a service or procedure to the worklist."""
    row_id = await ServiceLogService(pool).create(
        service_name=body.service_name,
        patient_code=body.patient_code,
        performer=body.performer,
        identity=identity,
    )
    return {"ok": True, "id": row_id}


@router.patch("/service-log/{row_id}")
async def progress_service_item(
    row_id: UUID,
    body: ServiceProgressRequest,
    identity: StaffIdentity = Depends(_SERVICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Start or finish a worklist item."""
    await ServiceLogService(pool).apply_patch(
        row_id=str(row_id),
        patch=task_patch(body.action, body.result_text),
        identity=identity,
        event_type=f"service_log.{'started' if body.action == 'start' else 'finished'}",
        origin=f"api:service-{body.action}",
        payload={"id": str(row_id), "action": body.action},
    )
    return {"ok": True}


@router.post("/sono/queue", status_code=201)
async def create_sono_row(
    body: SonoCreateRequest,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Add a row to the ultrasound nurse's queue."""
    row_id = await ServiceLogService(pool).create(
        service_name=body.service_name,
        patient_code=body.patient_code,
        identity=identity,
        kind=body.kind,
        status=QUEUE_WAITING,
        ref_prefix="api-sono",
        origin="api:sono-create",
    )
    return {"ok": True, "id": row_id}


@router.patch("/sono/queue/{row_id}")
async def progress_sono_row(
    row_id: UUID,
    body: SonoProgressRequest,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Move an ultrasound row along, or toggle one of a lab row's milestones."""
    if body.action is not None:
        patch = queue_patch(body.action)
        event = f"service_log.sono_{body.action}"
    elif body.milestone is not None:
        # A milestone is a timestamp that can be set and unset — a nurse who
        # ticks "sent to lab" by mistake has to be able to untick it.
        patch = {MILESTONE_COLUMN[body.milestone]: "now" if body.value else None}
        event = f"service_log.milestone_{body.milestone}"
    else:
        raise ValidationError("Cần action (SA) hoặc milestone (XN)")

    await ServiceLogService(pool).apply_patch(
        row_id=str(row_id),
        patch=patch,
        identity=identity,
        event_type=event,
        origin="api:sono-progress",
        payload={"id": str(row_id), "action": body.action, "milestone": body.milestone},
    )
    return {"ok": True}


@router.delete("/sono/queue/{row_id}")
async def remove_sono_row(
    row_id: UUID,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Drop a row from the queue. service_log is not append-only."""
    await ServiceLogService(pool).remove(row_id=str(row_id), identity=identity)
    return {"ok": True}
