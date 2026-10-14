"""Kế toán: đặt thuế suất GTGT theo nhóm / mặt hàng (cửa theo QUYỀN, không theo vai)."""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.thue_suat_service import ThueSuatService

router = APIRouter()


class DatThueRequest(BaseModel):
    """`thue_suat`: số % ("8", "8,5"), "KCT", "KKKNT"; rỗng = bỏ đặt."""

    thue_suat: str | None = Field(None, max_length=20)


class DatThueMatHangRequest(DatThueRequest):
    loai: str = Field(max_length=10)
    id: str = Field(max_length=64)


@router.get("/ke-toan/thue-suat")
async def xem_thue_suat(
    tim: str | None = Query(None, max_length=80),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ThueSuatService(pool).xem(identity=identity, tim=tim)


@router.put("/ke-toan/thue-suat/nhom/{nhom}")
async def dat_thue_nhom(
    nhom: str,
    body: DatThueRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ThueSuatService(pool).dat_nhom(
        identity=identity, nhom=nhom, thue_suat=body.thue_suat
    )


@router.put("/ke-toan/thue-suat/mat-hang")
async def dat_thue_mat_hang(
    body: DatThueMatHangRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ThueSuatService(pool).dat_mat_hang(
        identity=identity, loai=body.loai, id_=body.id, thue_suat=body.thue_suat
    )
