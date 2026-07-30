"""Roster and price-list endpoints (W5, ADR-0012)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.config_service import (
    PRICE_ROLES,
    ROSTER_ROLES,
    PriceGroup,
    PriceListService,
    RosterDecision,
    RosterService,
    Shift,
)

router = APIRouter()

# Everyone works a shift, so everyone may sign up for one; the service decides
# who may schedule somebody else.
_ROSTER_GUARD = require_role(*ROSTER_ROLES)
_PRICE_GUARD = require_role(*PRICE_ROLES)


class ShiftRequest(BaseModel):
    work_date: date
    station: str = Field(min_length=1, max_length=64)
    shift: Shift = "FULL"
    # Ignored unless the caller is management — see the service.
    staff_id: UUID | None = None
    staff_name: str | None = Field(default=None, max_length=200)
    sort: int = 0


class RosterDecisionRequest(BaseModel):
    decision: RosterDecision
    reason: str | None = Field(default=None, max_length=500)


class PriceCreateRequest(BaseModel):
    service_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    group: PriceGroup
    unit_price: float | str | None = None


class PriceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    unit_price: float | str | None = None
    active: bool | None = None


@router.post("/roster/shifts", status_code=201)
async def add_shift(
    body: ShiftRequest,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Sign up for a shift, or — as management — schedule somebody."""
    roster_id = await RosterService(pool).add_shift(
        work_date=body.work_date,
        station=body.station,
        shift=body.shift,
        identity=identity,
        staff_id=str(body.staff_id) if body.staff_id else None,
        staff_name=body.staff_name,
        sort=body.sort,
    )
    return {"ok": True, "id": roster_id}


@router.patch("/roster/shifts/{roster_id}")
async def decide_shift(
    roster_id: UUID,
    body: RosterDecisionRequest,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Approve or reject a self-registered shift. Management only."""
    await RosterService(pool).decide(
        roster_id=str(roster_id),
        decision=body.decision,
        reason=body.reason,
        identity=identity,
    )
    return {"ok": True}


@router.delete("/roster/shifts/{roster_id}")
async def remove_shift(
    roster_id: UUID,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Remove a shift. Non-managers may only remove their own."""
    await RosterService(pool).remove(roster_id=str(roster_id), identity=identity)
    return {"ok": True}


@router.post("/service-prices", status_code=201)
async def add_price(
    body: PriceCreateRequest,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Add a line to the price list."""
    price_id = await PriceListService(pool).add(
        service_code=body.service_code,
        name=body.name,
        group=body.group,
        unit_price=body.unit_price,
        identity=identity,
    )
    return {"ok": True, "id": price_id}


@router.patch("/service-prices/{price_id}")
async def update_price(
    price_id: UUID,
    body: PriceUpdateRequest,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Change a price, rename a line, or switch it off."""
    await PriceListService(pool).update(
        price_id=str(price_id),
        identity=identity,
        name=body.name,
        unit_price=body.unit_price,
        # Absent means "leave the price"; explicit null means "clear it".
        unit_price_provided="unit_price" in body.model_fields_set,
        active=body.active,
    )
    return {"ok": True}


@router.delete("/service-prices/{price_id}")
async def remove_price(
    price_id: UUID,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Remove a price-list line."""
    await PriceListService(pool).remove(price_id=str(price_id), identity=identity)
    return {"ok": True}
