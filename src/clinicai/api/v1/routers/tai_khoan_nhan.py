"""Tài khoản ngân hàng nhận chuyển khoản (31/10/2026).

Router mỏng — luật (mặc định mỗi cơ sở, tắt chứ không xoá, ai sửa được) ở
``TaiKhoanNhanService``. Đọc: mọi nhân viên đăng nhập (khối thu cần danh sách);
Quản lý thấy cả tài khoản đã tắt. Ghi: quyền ``config.clinic.manage``.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.tai_khoan_nhan_service import (
    QUYEN_QUAN_LY,
    TaiKhoanNhanService,
)

router = APIRouter()

_CUA_SUA = cua_quyen(QUYEN_QUAN_LY)


class TaiKhoanRequest(BaseModel):
    """Kiểu lỏng: luật ô (độ dài, số tài khoản) ở ``doc_form`` của service."""

    ten_goi: str = Field(max_length=200)
    ngan_hang: str = Field(max_length=200)
    so_tai_khoan: str = Field(max_length=100)
    chu_tai_khoan: str = Field(max_length=300)
    location_id: str | None = Field(default=None, max_length=64)
    mac_dinh: bool = False
    dang_dung: bool = True


@router.get("/tai-khoan-nhan")
async def danh_sach(
    visit_id: str | None = Query(default=None, max_length=64),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Danh mục + tài khoản dùng được / mặc định ở cơ sở của lượt (``visit_id``)
    hoặc cơ sở đang đăng nhập."""
    return await TaiKhoanNhanService(pool).danh_sach(
        identity=identity, visit_id=visit_id
    )


@router.post("/tai-khoan-nhan")
async def them(
    body: TaiKhoanRequest,
    identity: StaffIdentity = Depends(_CUA_SUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await TaiKhoanNhanService(pool).luu(
        identity=identity, data=body.model_dump()
    )


@router.put("/tai-khoan-nhan/{tai_khoan_id}")
async def sua(
    tai_khoan_id: str,
    body: TaiKhoanRequest,
    identity: StaffIdentity = Depends(_CUA_SUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Sửa / bật / tắt / đặt mặc định. Tắt tài khoản mặc định = bỏ mặc định."""
    return await TaiKhoanNhanService(pool).luu(
        identity=identity, data=body.model_dump(), tai_khoan_id=tai_khoan_id
    )
