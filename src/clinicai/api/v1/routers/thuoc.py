"""Danh mục thuốc: xoá thuốc chưa từng dùng (lưu bản chụp trước) và khôi phục.

Router mỏng — luật ở `services/thuoc/`. Quyền khối Nhà thuốc như sửa danh mục
(`pharmacy.dispense`); xem danh sách đã xoá thì `pharmacy.view` cũng được.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.thuoc import khoi_phuc_thuoc, xoa_thuoc

router = APIRouter()
_DOC = cua_quyen("pharmacy.view", "pharmacy.dispense")
_GHI = cua_quyen("pharmacy.dispense")


class ChoDungThuoc(BaseModel):
    bang: str
    nhan: str
    so: int


class XoaDuoc(BaseModel):
    xoa_duoc: bool
    ly_do: str | None = None
    da_dung: list[ChoDungThuoc] = Field(default_factory=list)


class XoaRequest(BaseModel):
    # Không giới hạn ở đây: service trả câu tiếng Việt (luật đầu vào rác).
    ly_do: str | None = None


class DaXoa(BaseModel):
    id: str
    da_xoa: bool
    ten: str
    ban_luu_id: str


class ThuocDaXoa(BaseModel):
    id: str
    drug_catalog_id: str
    ten: str
    ly_do: str
    xoa_luc: datetime
    nguoi_xoa: str | None = None
    khoi_phuc_luc: datetime | None = None
    nguoi_khoi_phuc: str | None = None
    da_khoi_phuc: bool


class DanhSachDaXoa(BaseModel):
    items: list[ThuocDaXoa]


class DaKhoiPhuc(BaseModel):
    id: str
    ten: str
    khoi_phuc: bool


@router.get("/thuoc/{thuoc_id}/xoa-duoc", response_model=XoaDuoc)
async def cua_xoa_duoc(
    thuoc_id: UUID,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> XoaDuoc:
    kq = await xoa_thuoc.thuoc_xoa_duoc(pool, identity=identity, thuoc_id=str(thuoc_id))
    return XoaDuoc(**kq)


@router.post("/thuoc/{thuoc_id}/xoa", response_model=DaXoa)
async def cua_xoa_thuoc(
    thuoc_id: UUID,
    body: XoaRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DaXoa:
    kq = await xoa_thuoc.xoa_thuoc(
        pool, identity=identity, thuoc_id=str(thuoc_id), ly_do=body.ly_do
    )
    return DaXoa(**kq)


@router.get("/thuoc/da-xoa", response_model=DanhSachDaXoa)
async def cua_thuoc_da_xoa(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DanhSachDaXoa:
    ds = await khoi_phuc_thuoc.danh_sach_da_xoa(pool, identity=identity)
    return DanhSachDaXoa(items=[ThuocDaXoa(**d) for d in ds])


@router.post("/thuoc/da-xoa/{ban_luu_id}/khoi-phuc", response_model=DaKhoiPhuc)
async def cua_khoi_phuc_thuoc(
    ban_luu_id: UUID,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DaKhoiPhuc:
    kq = await khoi_phuc_thuoc.khoi_phuc(
        pool, identity=identity, ban_luu_id=str(ban_luu_id)
    )
    return DaKhoiPhuc(**kq)
