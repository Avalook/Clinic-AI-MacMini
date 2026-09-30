"""Dọn dữ liệu khách thử — màn `/settings/don-du-lieu-thu` (30/09/2026).

Router mỏng. Cửa là capability `permission.manage` (quản trị cao nhất), service
tự kiểm — không gác bằng vai. Luật (ai bị chặn, chữ xác nhận, xoá những dòng
nào) ở `DonDuLieuThuService` và hàm SQL `don_khach_thu`.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.don_du_lieu_thu_service import DonDuLieuThuService

router = APIRouter()


class ChonKhachBody(BaseModel):
    khach: list[str] = Field(default_factory=list, max_length=500)


class XoaBody(ChonKhachBody):
    xac_nhan: str = Field(default="", max_length=20)


@router.get("/quan-tri/don-du-lieu-thu")
async def danh_sach(
    ngay: str | None = Query(default=None, max_length=20),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khách có lịch / lượt trong ngày ``ngay`` (YYYY-MM-DD; rỗng/rác = hôm qua)."""
    return await DonDuLieuThuService(pool).danh_sach(identity=identity, ngay=ngay)


@router.post("/quan-tri/don-du-lieu-thu/xem-truoc")
async def xem_truoc(
    body: ChonKhachBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Số dòng sẽ xoá theo loại + khách đang bị chặn — không đổi gì."""
    return await DonDuLieuThuService(pool).xem_truoc(
        identity=identity, khach=body.khach
    )


@router.post("/quan-tri/don-du-lieu-thu/xoa")
async def xoa(
    body: XoaBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Xoá các khách đã chọn + mọi dữ liệu của họ (phải gõ "XOA")."""
    return await DonDuLieuThuService(pool).xoa(
        identity=identity, khach=body.khach, xac_nhan=body.xac_nhan
    )
