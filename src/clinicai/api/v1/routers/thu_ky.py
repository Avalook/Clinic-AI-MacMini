"""Phạm vi của thư ký y khoa (Tuyền chốt 15/09/2026: thư ký theo bác sĩ).

Màn hình (server component Next) hỏi ở đây thay vì tự đọc Supabase: luật "thư ký
nào theo bác sĩ ấy" nằm ở một chỗ — clinicai.services.thu_ky_bac_si.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.thu_ky_bac_si import khach_duoc_xem, kiem_khach, pham_vi

router = APIRouter()


@router.get("/thu-ky/pham-vi")
async def xem_pham_vi(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Người gọi có phải thư ký không; nếu có, đi cùng bác sĩ nào (có thể rỗng)."""
    return await pham_vi(pool, identity)


@router.get("/thu-ky/khach-duoc-xem")
async def danh_sach_khach_duoc_xem(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mã khách thư ký được xem. `gioi_han = false` = không phải thư ký."""
    ids = await khach_duoc_xem(pool, identity)
    return {"gioi_han": ids is not None, "ids": ids or []}


@router.get("/thu-ky/khach/{clinic_patient_id}")
async def duoc_xem_khach(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """200 = được xem khách này; 403 kèm lý do khi thư ký không được."""
    await kiem_khach(pool, identity, str(clinic_patient_id))
    return {"ok": True}
