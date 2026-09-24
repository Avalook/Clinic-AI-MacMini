"""Quầy thuốc chỉnh ĐƠN BÁN trước khi thu (Tuyền 24/09/2026).

Cửa theo QUYỀN "Thu tiền thuốc" (``payment.medicine.collect``) — kiểm trong
QuayThuocService, trong chính giao dịch. Router mỏng.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.quay_thuoc_service import QuayThuocService

router = APIRouter()


@router.get("/quay-thuoc/luot/{visit_id}")
async def doc_don_ban(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đơn bán của lượt: dòng bác sĩ kê + dòng quầy thêm, kèm tích / số mua."""
    return await QuayThuocService(pool).doc(visit_id=str(visit_id), identity=identity)


class ChonBody(BaseModel):
    prescription_id: UUID
    mua: bool


@router.post("/quay-thuoc/chon")
async def chon(
    body: ChonBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tích (khách lấy) / bỏ tick (khách không lấy)."""
    return await QuayThuocService(pool).chon(
        prescription_id=str(body.prescription_id), mua=body.mua, identity=identity
    )


class SoLuongBody(BaseModel):
    prescription_id: UUID
    so_luong: float = Field(gt=0, le=100000)


@router.post("/quay-thuoc/so-luong")
async def doi_so_luong(
    body: SoLuongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đơn bác sĩ: số mua (≤ số kê). Dòng quầy thêm: số lượng."""
    return await QuayThuocService(pool).doi_so_luong(
        prescription_id=str(body.prescription_id),
        so_luong=body.so_luong,
        identity=identity,
    )


class DongThemBody(BaseModel):
    id: UUID | None = None
    drug_catalog_id: UUID | None = None
    quantity: str | None = Field(default=None, max_length=64)
    dosage: str | None = Field(default=None, max_length=500)
    caution: str | None = Field(default=None, max_length=500)


class LuuThemBody(BaseModel):
    dong: list[DongThemBody] = Field(default_factory=list, max_length=50)


@router.post("/quay-thuoc/luot/{visit_id}/them")
async def luu_dong_them(
    visit_id: UUID,
    body: LuuThemBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lấy thêm thuốc: thêm dòng mới / sửa dòng quầy đã thêm. Không xoá dòng nào."""
    return await QuayThuocService(pool).luu_dong_them(
        visit_id=str(visit_id),
        dong=[
            {
                "id": str(d.id) if d.id else None,
                "drug_catalog_id": str(d.drug_catalog_id)
                if d.drug_catalog_id
                else None,
                "quantity": d.quantity,
                "dosage": d.dosage,
                "caution": d.caution,
            }
            for d in body.dong
        ],
        identity=identity,
    )
