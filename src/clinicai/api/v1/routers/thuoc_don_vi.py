"""Danh mục thuốc → đổi tên đơn vị gốc (PR C, kế hoạch
docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 16). Router mỏng: luật ở
`services/thuoc/doi_ten_goc.py`. Gắn vào router `pharmacy` (cùng tiền tố, cùng cửa).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.thuoc import doi_ten_goc

router = APIRouter()
# Cùng cửa ghi danh mục; quyền sửa giá kiểm thêm trong service (đổi gốc đổi giá).
_GHI = cua_quyen("pharmacy.dispense")


class DoiTenGocBody(BaseModel):
    drug_catalog_id: UUID
    ten_moi: str = Field(max_length=50)
    don_vi_me: str = Field(max_length=50)
    # Any: luật đọc số ở service, rác → câu tiếng Việt.
    he_so_me: Any = None
    gia_goc_moi: Any = None
    ly_do: str | None = Field(default=None, max_length=500)


class DoiTenGocKq(BaseModel):
    ok: bool
    su_kien_id: str
    so_lo: int
    bi_danh: bool
    cau: str


@router.post("/pharmacy/doi-ten-goc", response_model=DoiTenGocKq)
async def doi_ten_don_vi_goc(
    body: DoiTenGocBody,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi chữ đơn vị gốc ("hộp 60 viên" → "viên") + khai đơn vị mẹ; tồn giữ số."""
    return await doi_ten_goc.doi_ten_goc(
        pool,
        identity=identity,
        thuoc=str(body.drug_catalog_id),
        ten_moi=body.ten_moi,
        don_vi_me=body.don_vi_me,
        he_so_me=body.he_so_me,
        gia_goc_moi=body.gia_goc_moi,
        ly_do=body.ly_do,
    )


class HoanTacBody(BaseModel):
    su_kien_id: UUID
    ly_do: str = Field(min_length=1, max_length=500)


class HoanTacKq(BaseModel):
    ok: bool
    ten_goc: str
    cau: str


@router.post("/pharmacy/hoan-tac-doi-ten-goc", response_model=HoanTacKq)
async def hoan_tac_doi_ten_don_vi_goc(
    body: HoanTacBody,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lệnh bù: đưa tên gốc, giá gốc, chữ lô, đơn vị mẹ về như trước lần đổi."""
    return await doi_ten_goc.hoan_tac_doi_ten_goc(
        pool, identity=identity, su_kien_id=str(body.su_kien_id), ly_do=body.ly_do
    )
