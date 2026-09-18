"""Theo dõi sau thủ thuật — bác sĩ quyết, CSKH chỉ nhìn (Tuyền chốt 16/09/2026)."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.theo_doi_thu_thuat_service import TheoDoiThuThuatService

router = APIRouter()


@router.get("/visits/{visit_id}/theo-doi-thu-thuat")
async def doc_theo_doi(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lượt có thủ thuật không, làm xong lúc nào, bác sĩ quyết theo dõi ra sao."""
    return await TheoDoiThuThuatService(pool).doc(
        identity=identity, visit_id=str(visit_id)
    )


class TheoDoiRequest(BaseModel):
    theo_doi: Literal["CAN", "KHONG_CAN"]
    sau_ngay: int | None = Field(default=None, ge=1, le=365)


@router.put("/visits/{visit_id}/theo-doi-thu-thuat")
async def dat_theo_doi(
    visit_id: UUID,
    body: TheoDoiRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bác sĩ phụ trách / làm thủ thuật chọn: theo dõi sau N ngày, hoặc không."""
    return await TheoDoiThuThuatService(pool).dat(
        identity=identity,
        visit_id=str(visit_id),
        theo_doi=body.theo_doi,
        sau_ngay=body.sau_ngay,
    )
