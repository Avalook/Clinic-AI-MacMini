"""Care-episode lifecycle endpoints (W5, ADR-0012).

Thin router: the role gate is server-authoritative via ``require_role``, then the
rule lives in ``EpisodeService``. Domain errors map to HTTP through the global
handlers in ``main.py``.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.episode_service import EpisodeService

router = APIRouter()

# Mirrors canManageAppt in src/dashboard/lib/roles.ts.
_EPISODE_GUARD = require_role(
    ClinicRole.CSKH,
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
)


class EpisodeStatusRequest(BaseModel):
    """Body for confirming or reopening an episode parked at PENDING_CLOSE."""

    action: Literal["close", "reopen"]


@router.patch("/episodes/{episode_id}")
async def set_episode_status(
    episode_id: UUID,
    body: EpisodeStatusRequest,
    identity: StaffIdentity = Depends(_EPISODE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Close or reopen a care episode that is waiting for CSKH confirmation."""
    service = EpisodeService(pool)
    status = await service.set_status(
        episode_id=str(episode_id),
        action=body.action,
        identity=identity,
    )
    return {"ok": True, "status": status}
