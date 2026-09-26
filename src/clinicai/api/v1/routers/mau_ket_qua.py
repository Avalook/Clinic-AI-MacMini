"""Mẫu kết quả cận lâm sàng — danh mục và việc gắn mẫu cho dịch vụ.

Đọc thì ai đăng nhập cũng được (bác sĩ cần biết dịch vụ này điền mẫu nào). Gắn
và gỡ thì cần quyền `catalogue.result_template.manage` — service tự kiểm.
Bảng gắn + tạo mẫu mới (27/09/2026) cho màn `/settings/mau-ket-qua`.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.mau_ket_qua_service import MauKetQuaService

router = APIRouter()


class GanMauBody(BaseModel):
    service_code: str = Field(min_length=1, max_length=64)
    mau: str = Field(min_length=1, max_length=48)


class TaoMauBody(BaseModel):
    ten: str = Field(min_length=1, max_length=200)
    nhom: str = Field(default="Khác", max_length=80)
    #: Mã biểu mẫu (KQ_…) để chép khung; bỏ trống = mẫu trống có mục Kết luận.
    chep_tu: str | None = Field(default=None, max_length=64)


@router.get("/mau-ket-qua/bang-gan")
async def bang_gan(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Màn Mẫu kết quả: dịch vụ có phòng làm + mẫu đang gắn + quyền người xem."""
    return await MauKetQuaService(pool).bang_gan(identity=identity)


@router.post("/mau-ket-qua/tao", status_code=201)
async def tao_mau(
    body: TaoMauBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await MauKetQuaService(pool).tao_mau(
        ten=body.ten, nhom=body.nhom, chep_tu=body.chep_tu, identity=identity
    )


@router.get("/mau-ket-qua")
async def danh_muc(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await MauKetQuaService(pool).danh_muc(identity=identity)


@router.get("/mau-ket-qua/dich-vu/{service_code}")
async def mau_cua_dich_vu(
    service_code: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Trả kết quả cho dịch vụ này thì điền vào mẫu nào."""
    return await MauKetQuaService(pool).mau_cua_dich_vu(
        service_code=service_code, identity=identity
    )


@router.get("/mau-ket-qua/de-xuat")
async def de_xuat(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Máy đề xuất mẫu cho dịch vụ chưa gắn. Người xác nhận, máy không tự gắn."""
    return await MauKetQuaService(pool).de_xuat(identity=identity)


@router.post("/mau-ket-qua/gan")
async def gan(
    body: GanMauBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await MauKetQuaService(pool).gan(
        service_code=body.service_code, mau=body.mau, identity=identity
    )


@router.post("/mau-ket-qua/go")
async def go(
    body: GanMauBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await MauKetQuaService(pool).go(
        service_code=body.service_code, mau=body.mau, identity=identity
    )
