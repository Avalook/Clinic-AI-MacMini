"""Chức năng của phòng — màn Cấu trúc phòng khám (04/11/2026).

Luật nằm ở `services/phong_chuc_nang_service.py`; đây chỉ chuyển tiếp.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services import phong_chuc_nang_service as svc

router = APIRouter()
_GUARD = cua_quyen(svc.QUYEN)


class DoiChucNang(BaseModel):
    work_pack: str = Field(min_length=1, max_length=64)
    bat: bool


@router.get("/clinic-config/phong/{room_id}/chuc-nang")
async def doc_chuc_nang_phong(
    room_id: UUID,
    response: Response,
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await svc.doc_chuc_nang(pool, identity=identity, room_id=str(room_id))


@router.put("/clinic-config/phong/{room_id}/chuc-nang")
async def doi_chuc_nang_phong(
    room_id: UUID,
    body: DoiChucNang,
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await svc.doi_chuc_nang(
        pool,
        identity=identity,
        room_id=str(room_id),
        work_pack=body.work_pack,
        bat=body.bat,
    )
