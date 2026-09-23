"""Xem lại một lượt khám — chỉ đọc, cắt theo vai ở ``XemLuotService``."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from clinicai.api.identity import StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.bang_hanh_trinh_service import BangHanhTrinhService
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


@router.get("/hanh-trinh/hom-nay")
async def bang_hanh_trinh(
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bảng hành trình chung (nhóm 3, 24/09/2026): mỗi khách hôm nay — đang ở
    đâu, đã xong gì, còn chờ gì."""
    return await BangHanhTrinhService(pool).hom_nay(identity=identity)
