"""Phiếu NHẬP vật tư chờ duyệt (G8b, 14/10/2026) — Quản lý / Trưởng ca có lego
"Duyệt vật tư" duyệt hoặc từ chối; người lập rút lại được khi còn chờ.

Quyền = lego, không theo vai: xem danh sách theo lego "Kho vật tư"
(`vat_tu.manage`), duyệt / từ chối theo `vat_tu.approve`. Mọi luật nằm ở
`vat_tu_nhap_duyet_service`; lệnh tự là máy trạng thái (gọi lại không nhân đôi) nên
không cần khoá gửi lại.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.can import can
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services import vat_tu_nhap_duyet_service as nhap

router = APIRouter()
_QL = cua_quyen("vat_tu.manage")
_DUYET = cua_quyen("vat_tu.approve")


@router.get("/vat-tu-kho/cho-duyet")
async def danh_sach(
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Yêu cầu nhập chờ duyệt + đã quyết gần đây của cơ sở; `duoc_duyet` = người xem
    có lego Duyệt vật tư (màn chỉ hiện nút khi true — lệnh vẫn kiểm lại)."""
    async with pool.acquire() as conn:
        duoc_duyet = await can(conn, identity, "vat_tu.approve")
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
