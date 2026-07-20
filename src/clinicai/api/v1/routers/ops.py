"""MANAGEMENT-only, read-only operations status endpoint."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Response

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
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
