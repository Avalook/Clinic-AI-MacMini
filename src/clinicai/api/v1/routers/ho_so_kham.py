"""HỒ SƠ KHÁM của một lượt — phần dịch vụ của lượt (07/10/2026).

Router mỏng; luật ở `services/ho_so_dich_vu.py`. Plan
docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md (T1, T5).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services import ho_so_dich_vu

router = APIRouter(tags=["ho-so-kham"])


class DoiDichVuBody(BaseModel):
    service_type_id: UUID


@router.get("/ho-so-kham/{visit_id}/dich-vu")
async def doc_dich_vu(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dịch vụ của lượt, đổi được không, lịch sử đổi, phiếu cũ, "Khách đã đặt"."""
    return await ho_so_dich_vu.doc(pool, identity=identity, visit_id=str(visit_id))


@router.post("/ho-so-kham/{visit_id}/doi-dich-vu")
async def doi_dich_vu(
    visit_id: UUID,
    body: DoiDichVuBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi dịch vụ khám ngay trong hồ sơ (quyền + luật ở service)."""
    return await ho_so_dich_vu.doi(
        pool,
        identity=identity,
        visit_id=str(visit_id),
        service_type_id=str(body.service_type_id),
    )
