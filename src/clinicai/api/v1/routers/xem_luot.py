"""Xem lại một lượt khám — chỉ đọc, cắt theo vai ở ``XemLuotService``."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from clinicai.api.identity import StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.xem_luot_service import GOI_DUOC, XemLuotService

router = APIRouter()
_GUARD = require_role(*GOI_DUOC)


@router.get("/xem-luot/{visit_id}")
async def xem_luot(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await XemLuotService(pool).doc(visit_id=str(visit_id), identity=identity)
