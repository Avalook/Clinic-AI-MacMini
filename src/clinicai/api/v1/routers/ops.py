"""MANAGEMENT-only, read-only operations endpoints: service status and telemetry."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.core.telemetry import SLOW_REQUEST_MS, telemetry
from clinicai.schemas.ops import OpsStatusResponse
from clinicai.services.ops_status import OpsStatusService

router = APIRouter()
_MANAGEMENT_GUARD = require_role(ClinicRole.MANAGEMENT)


@router.get("/ops/status", response_model=OpsStatusResponse)
async def get_ops_status(
    response: Response,
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> OpsStatusResponse:
    response.headers["Cache-Control"] = "private, no-store"
    return await OpsStatusService(pool).collect()


@router.get("/ops/telemetry")
async def get_telemetry(
    response: Response,
    window_s: float | None = Query(default=900, ge=0, le=86400),
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
) -> dict[str, object]:
    """Response times and recent failures, from the API process's ring buffer.

    Behind the MANAGEMENT guard like the rest of /ops. It carries no patient
    data by construction (route templates only — see core/telemetry), but it
    does describe the shape of the system, and that is not something to hand to
    every logged-in staff member.

    Defaults to the last 15 minutes: the question at a front desk is "is it slow
    right now", and an average over a whole uptime hides the answer.
    """
    response.headers["Cache-Control"] = "no-store"
    snapshot = telemetry.snapshot(window_s=window_s or None)
    snapshot["slow_threshold_ms"] = SLOW_REQUEST_MS
    return snapshot
