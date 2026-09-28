"""Services worklist and the ultrasound queue (W5, ADR-0012).

Two screens, two role gates, one table — see the service module for why the
status vocabularies differ and why that is preserved rather than tidied here.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    StaffIdentity,
)
from clinicai.api.nghi_huu import CHI_DINH_MOI, LAM_O_PHONG, bao_da_nghi
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.permissions.y_khoa import cua_ghi_y_khoa
from clinicai.services.service_log_service import (
    Milestone,
    QueueAction,
    TaskAction,
)

router = APIRouter()

# Recording a service is clinical work — reception and management excluded
# (decided 2026-06-17, same as lab results).
_SERVICE_GUARD = cua_ghi_y_khoa
# The sono queue belongs to the ultrasound nurse.
# CHỈ LEGO (28/09/2026): cửa hỏi QUYỀN, không hỏi vai — xem permissions/cua_quyen.py.
_SONO_GUARD = cua_quyen("service.execute.start", moi_phong=True)


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
    """ĐÃ NGHỈ (Slice 1, 18/09/2026) — rail cũ, trả 410, không ghi gì."""
    bao_da_nghi(
        endpoint="POST /service-log",
        identity=identity,
        thay_bang=CHI_DINH_MOI,
    )


@router.patch("/service-log/{row_id}")
async def progress_service_item(
    row_id: UUID,
    body: ServiceProgressRequest,
    identity: StaffIdentity = Depends(_SERVICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """ĐÃ NGHỈ (Slice 1, 18/09/2026) — rail cũ, trả 410, không ghi gì."""
    bao_da_nghi(
        endpoint="PATCH /service-log/{id}",
        identity=identity,
        thay_bang=LAM_O_PHONG,
        row_id=row_id,
    )


@router.post("/sono/queue", status_code=201)
async def create_sono_row(
    body: SonoCreateRequest,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """ĐÃ NGHỈ (Slice 1, 18/09/2026) — rail cũ, trả 410, không ghi gì."""
    bao_da_nghi(
        endpoint="POST /sono/queue",
        identity=identity,
        thay_bang=CHI_DINH_MOI,
    )


@router.patch("/sono/queue/{row_id}")
async def progress_sono_row(
    row_id: UUID,
    body: SonoProgressRequest,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """ĐÃ NGHỈ (Slice 1, 18/09/2026) — rail cũ, trả 410, không ghi gì."""
    bao_da_nghi(
        endpoint="PATCH /sono/queue/{id}",
        identity=identity,
        thay_bang=LAM_O_PHONG,
        row_id=row_id,
    )


@router.delete("/sono/queue/{row_id}")
async def remove_sono_row(
    row_id: UUID,
    identity: StaffIdentity = Depends(_SONO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """ĐÃ NGHỈ (Slice 1, 18/09/2026) — rail cũ, trả 410, không ghi gì."""
    bao_da_nghi(
        endpoint="DELETE /sono/queue/{id}",
        identity=identity,
        thay_bang=CHI_DINH_MOI,
        row_id=row_id,
    )
