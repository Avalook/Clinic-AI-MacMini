"""Thuốc: gợi ý tên gần giống, "Nhờ kho thêm thuốc", xoá thuốc chưa từng dùng.

Router mỏng — luật ở `services/thuoc/`. Gợi ý và nhờ kho mở cho MỌI nhân viên đã
đăng nhập (ai kê đơn cũng gõ được tên lạ); xem / xử lý yêu cầu và xoá thuốc cần
quyền khối Nhà thuốc như sửa danh mục (`pharmacy.dispense`).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.thuoc import nho_kho, xoa_thuoc
from clinicai.services.thuoc.goi_y import goi_y_thuoc

router = APIRouter()
_DOC = cua_quyen("pharmacy.view", "pharmacy.dispense")
_GHI = cua_quyen("pharmacy.dispense")


class GoiYThuoc(BaseModel):
    drug_catalog_id: str
    ten: str
    biet_duoc: str | None = None
    diem: float


class DanhSachGoiY(BaseModel):
    items: list[GoiYThuoc]


class NhoKhoRequest(BaseModel):
    # Không giới hạn độ dài ở đây: service trả câu tiếng Việt (luật đầu vào rác).
    ten: str
    ghi_chu: str | None = None
    visit_id: UUID | None = None


class NhoKhoKetQua(BaseModel):
    id: str | None
    ten_go: str
    moi: bool


class YeuCauNhoKho(BaseModel):
    id: str
    ten_go: str
    ghi_chu: str | None = None
    tao_luc: datetime
    xong_luc: datetime | None = None
    nguoi_nho: str | None = None
    nguoi_xong: str | None = None
    xong: bool


class DanhSachNhoKho(BaseModel):
    items: list[YeuCauNhoKho]


class DanhDauRequest(BaseModel):
    xong: bool


class DanhDauKetQua(BaseModel):
    id: str
    xong: bool


class ChoDungThuoc(BaseModel):
    bang: str
    nhan: str
    so: int


class XoaDuoc(BaseModel):
    xoa_duoc: bool
    ly_do: str | None = None
    da_dung: list[ChoDungThuoc] = Field(default_factory=list)


class DaXoa(BaseModel):
    id: str
    da_xoa: bool
    ten: str


@router.get("/thuoc/goi-y", response_model=DanhSachGoiY)
async def cua_goi_y_thuoc(
    ten: str = Query(default=""),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DanhSachGoiY:
    """Thuốc chọn được (đang dùng, có giá) gần giống tên gõ — tên và biệt dược."""
    async with pool.acquire() as conn:
        ds = await goi_y_thuoc(conn, identity.clinic_id, ten)
    return DanhSachGoiY(items=[GoiYThuoc(**d) for d in ds])


@router.post("/thuoc/nho-kho", response_model=NhoKhoKetQua, status_code=201)
async def cua_nho_kho_them(
    body: NhoKhoRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> NhoKhoKetQua:
    kq = await nho_kho.nho_kho_them(
        pool,
        identity=identity,
        ten=body.ten,
        ghi_chu=body.ghi_chu,
        visit_id=str(body.visit_id) if body.visit_id else None,
    )
    return NhoKhoKetQua(**kq)


@router.get("/thuoc/nho-kho", response_model=DanhSachNhoKho)
async def cua_nho_kho_danh_sach(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DanhSachNhoKho:
    ds = await nho_kho.danh_sach_nho_kho(pool, identity=identity)
    return DanhSachNhoKho(items=[YeuCauNhoKho(**d) for d in ds])


@router.post("/thuoc/nho-kho/{yeu_cau_id}/danh-dau", response_model=DanhDauKetQua)
async def cua_nho_kho_danh_dau(
    yeu_cau_id: UUID,
    body: DanhDauRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DanhDauKetQua:
    kq = await nho_kho.danh_dau_nho_kho(
        pool, identity=identity, yeu_cau_id=str(yeu_cau_id), xong=body.xong
    )
    return DanhDauKetQua(**kq)


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
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> DaXoa:
    kq = await xoa_thuoc.xoa_thuoc(pool, identity=identity, thuoc_id=str(thuoc_id))
    return DaXoa(**kq)
