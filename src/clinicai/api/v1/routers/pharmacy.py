"""Nhà thuốc: hàng đợi đơn, tồn kho, và bốn thao tác ghi.

Trước file này, bốn màn `/pharmacy` đọc thẳng Supabase và không có đường ghi
nào — RLS chỉ cấp SELECT, nên kể cả có nút thì trình duyệt cũng không ghi được.
Mọi thao tác kho đi qua đây, chạy `service_role` phía sau, đúng luật CLAUDE.md:
"Frontend = UI only. All business logic belongs in the FastAPI backend."
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.pharmacy_service import PharmacyService

router = APIRouter()

# ĐỌC mở rộng hơn GHI. Thu ngân thuốc cần thấy đơn để thu tiền, Trưởng ca và
# Quản lý cần thấy tồn để biết sắp hết gì — nhưng chỉ Dược sĩ (và Quản lý, cho
# lúc dược sĩ nghỉ) mới được chạm vào kho.
_DOC = require_role(
    ClinicRole.PHARMACIST,
    ClinicRole.CASHIER_THUOC,
    ClinicRole.TRUONG_CA,
    ClinicRole.MANAGEMENT,
)
_GHI = require_role(ClinicRole.PHARMACIST, ClinicRole.MANAGEMENT)


@router.get("/pharmacy/queue")
async def hang_doi(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đơn thuốc chưa chốt — gồm cả đơn đã cấp một phần."""
    return {"items": await PharmacyService(pool).hang_doi(identity=identity)}


@router.get("/pharmacy/inventory")
async def ton_kho(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tồn theo lô, kèm hạn dùng và cờ hết hạn."""
    return {"items": await PharmacyService(pool).ton_kho(identity=identity)}


class NhapLoRequest(BaseModel):
    drug_catalog_id: UUID
    so_luong: float = Field(gt=0)
    # Cả ba BẮT BUỘC: `drug_batch` khai NOT NULL. Xem PharmacyService.nhap_lo.
    batch_code: str = Field(min_length=1, max_length=100)
    expiry_date: date
    unit: str = Field(min_length=1, max_length=50)
    cost_price: float | None = Field(default=None, ge=0)
    ly_do: str | None = Field(default=None, max_length=500)


@router.post("/pharmacy/receive", status_code=201)
async def nhap_lo(
    body: NhapLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Nhập hàng vào kho."""
    return await PharmacyService(pool).nhap_lo(
        identity=identity,
        drug_catalog_id=str(body.drug_catalog_id),
        so_luong=body.so_luong,
        batch_code=body.batch_code,
        expiry_date=body.expiry_date,
        unit=body.unit,
        cost_price=body.cost_price,
        ly_do=body.ly_do,
    )


class CapPhatRequest(BaseModel):
    prescription_id: UUID
    drug_batch_id: UUID
    so_luong: float = Field(gt=0)


@router.post("/pharmacy/dispense", status_code=201)
async def cap_phat(
    body: CapPhatRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Cấp thuốc cho một dòng đơn. Cấp một phần là chuyện bình thường."""
    return await PharmacyService(pool).cap_phat(
        identity=identity,
        prescription_id=str(body.prescription_id),
        drug_batch_id=str(body.drug_batch_id),
        so_luong=body.so_luong,
    )


class TuChoiRequest(BaseModel):
    prescription_id: UUID
    # Lý do BẮT BUỘC — xem PharmacyService.tu_choi.
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/pharmacy/refuse", status_code=201)
async def tu_choi(
    body: TuChoiRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khách không lấy thuốc."""
    return await PharmacyService(pool).tu_choi(
        identity=identity,
        prescription_id=str(body.prescription_id),
        ly_do=body.ly_do,
    )


class ChotRequest(BaseModel):
    prescription_id: UUID
    ly_do: str | None = Field(default=None, max_length=500)


@router.post("/pharmacy/close-line", status_code=201)
async def chot(
    body: ChotRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Không cấp thêm nữa — dùng cho 'lấy 5 rồi thôi' và cho đơn đã cấp đủ."""
    return await PharmacyService(pool).chot(
        identity=identity,
        prescription_id=str(body.prescription_id),
        ly_do=body.ly_do,
    )


class DieuChinhRequest(BaseModel):
    drug_batch_id: UUID
    # Mang dấu: âm là bớt, dương là thêm. 0 bị từ chối ở service.
    so_luong: float
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/pharmacy/adjust", status_code=201)
async def dieu_chinh(
    body: DieuChinhRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Kiểm kê lệch."""
    return await PharmacyService(pool).dieu_chinh(
        identity=identity,
        drug_batch_id=str(body.drug_batch_id),
        so_luong=body.so_luong,
        ly_do=body.ly_do,
    )


class HuyRequest(BaseModel):
    drug_batch_id: UUID
    so_luong: float = Field(gt=0)
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/pharmacy/discard", status_code=201)
async def huy(
    body: HuyRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Huỷ thuốc hỏng hoặc hết hạn. Ra khỏi kho nhưng không ra khỏi sổ."""
    return await PharmacyService(pool).huy(
        identity=identity,
        drug_batch_id=str(body.drug_batch_id),
        so_luong=body.so_luong,
        ly_do=body.ly_do,
    )
