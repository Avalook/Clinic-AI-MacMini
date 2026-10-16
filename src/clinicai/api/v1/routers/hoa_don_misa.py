"""Đánh dấu "đã xuất sang MISA" (G5c): đánh dấu, bỏ / khôi phục, danh sách, chi tiết.

Router mỏng — danh sách hoá đơn do máy chủ dựng lại, dấu vân tay và luật "có thay
đổi sau khi xuất" ở `HoaDonMisaService` / `hoa_don_misa_doc`. Cửa theo QUYỀN lego
`accounting.finance.full`, không theo vai.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.hoa_don_misa_service import QUYEN_MISA, HoaDonMisaService

router = APIRouter()

_CUA = cua_quyen(QUYEN_MISA)


class DanhDauRequest(BaseModel):
    """`tu` / `den` dạng YYYY-MM-DD; sai dạng thì máy chủ báo 422 (không đoán ngày)."""

    tu: str = Field(max_length=40)
    den: str = Field(max_length=40)
    loai: str | None = Field(None, max_length=20)
    co_so: str | None = Field(None, max_length=64)
    ghi_chu: str = Field("", max_length=2000)


@router.get("/hoa-don/misa-xuat")
async def danh_sach_lan_xuat(
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return {"lan_xuat": await HoaDonMisaService(pool).doc_danh_sach(identity=identity)}


@router.post("/hoa-don/misa-xuat")
async def danh_dau_da_xuat(
    body: DanhDauRequest,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await HoaDonMisaService(pool).danh_dau(
        identity=identity,
        tu=body.tu,
        den=body.den,
        loai=body.loai,
        co_so=body.co_so,
        ghi_chu=body.ghi_chu,
    )


@router.get("/hoa-don/misa-xuat/{xuat_id}")
async def chi_tiet_lan_xuat(
    xuat_id: str,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await HoaDonMisaService(pool).doc_chi_tiet(
        identity=identity, xuat_id=xuat_id
    )


@router.delete("/hoa-don/misa-xuat/{xuat_id}")
async def bo_danh_dau(
    xuat_id: str,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bỏ đánh dấu — hoàn tác bằng PUT (không xoá dòng nào)."""
    return await HoaDonMisaService(pool).huy_danh_dau(
        identity=identity, xuat_id=xuat_id
    )


@router.put("/hoa-don/misa-xuat/{xuat_id}")
async def khoi_phuc_danh_dau(
    xuat_id: str,
    identity: StaffIdentity = Depends(_CUA),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await HoaDonMisaService(pool).khoi_phuc(identity=identity, xuat_id=xuat_id)
