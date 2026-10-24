"""Phiếu NHẬP vật tư chờ duyệt (G8b, 14/10/2026) — chỉ Quản lý duyệt hoặc từ chối;
người lập rút lại được khi còn chờ.

Máy chủ kiểm tra cả vai Quản lý gốc và capability `vat_tu.approve`; ẩn nút ở giao diện
chỉ là bổ sung, không phải hàng rào bảo mật. Người lập vẫn có thể rút lại yêu cầu của
mình khi còn chờ.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
)
from clinicai.core.database import get_db_pool
from clinicai.permissions.can import can
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services import vat_tu_nhap_duyet_service as nhap

router = APIRouter()
_QL = cua_quyen("vat_tu.manage")
_DUYET = cua_quyen("vat_tu.approve")


async def _quan_ly_goc(
    identity: StaffIdentity = Depends(get_current_identity),
) -> StaffIdentity:
    """Chỉ membership MANAGEMENT gốc; vai theo ca/lego không được nâng quyền."""
    if identity.vai_goc != ClinicRole.MANAGEMENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản lý được duyệt phiếu vật tư.",
        )
    return identity


@router.get("/vat-tu-kho/cho-duyet")
async def danh_sach(
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Quản lý xem toàn bộ; nhân viên xem yêu cầu do chính mình lập để rút lại."""
    async with pool.acquire() as conn:
        duoc_duyet = identity.vai_goc == ClinicRole.MANAGEMENT and await can(
            conn, identity, "vat_tu.approve"
        )
    kq: dict[str, Any] = jsonable_encoder(
        {
            "items": await nhap.doc_cho_duyet(pool, identity=identity),
            "duoc_duyet": duoc_duyet,
        }
    )
    return kq


@router.post("/vat-tu-kho/cho-duyet/{yeu_cau_id}/duyet", status_code=201)
async def duyet(
    yeu_cau_id: UUID,
    identity: StaffIdentity = Depends(_DUYET),
    _quan_ly: StaffIdentity = Depends(_quan_ly_goc),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await nhap.duyet(pool, identity=identity, yeu_cau_id=str(yeu_cau_id))
    )
    return kq


class TuChoiRequest(BaseModel):
    # Any: lý do rác phải tới service để trả 422 có lời.
    ly_do: Any = None


@router.post("/vat-tu-kho/cho-duyet/{yeu_cau_id}/tu-choi")
async def tu_choi(
    yeu_cau_id: UUID,
    body: TuChoiRequest,
    identity: StaffIdentity = Depends(_DUYET),
    _quan_ly: StaffIdentity = Depends(_quan_ly_goc),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await nhap.tu_choi(
            pool, identity=identity, yeu_cau_id=str(yeu_cau_id), ly_do=body.ly_do
        )
    )
    return kq


class RutLaiRequest(BaseModel):
    ly_do: str | None = Field(default=None, max_length=500)


@router.post("/vat-tu-kho/cho-duyet/{yeu_cau_id}/rut-lai")
async def rut_lai(
    yeu_cau_id: UUID,
    body: RutLaiRequest | None = None,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await nhap.rut_lai(
            pool,
            identity=identity,
            yeu_cau_id=str(yeu_cau_id),
            ly_do=body.ly_do if body else None,
        )
    )
    return kq
