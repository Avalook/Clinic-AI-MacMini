"""Xem lại một lượt khám — chỉ đọc, cắt theo QUYỀN ở ``XemLuotService``."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from clinicai.api.identity import StaffIdentity, cua_noi_bo
from clinicai.core.database import get_db_pool
from clinicai.services.bang_hanh_trinh_service import BangHanhTrinhService
from clinicai.services.hanh_trinh_khach_service import HanhTrinhKhachService
from clinicai.services.xem_luot_service import XemLuotService

router = APIRouter()
#: Mọi thành viên nội bộ (vai tài khoản) — Hành trình "luôn bật" (đợt 3,
#: 27/09/2026). Nội dung cắt theo quyền trong hàm dịch vụ.
_GUARD = cua_noi_bo


@router.get("/xem-luot/{visit_id}")
async def xem_luot(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await XemLuotService(pool).doc(visit_id=str(visit_id), identity=identity)


@router.get("/hanh-trinh/hom-nay")
async def bang_hanh_trinh(
    ngay: str | None = Query(default=None, max_length=20),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bảng hành trình chung (nhóm 3, 24/09/2026): mỗi khách của MỘT ngày (mặc
    định hôm nay; ``ngay`` YYYY-MM-DD xem lại ngày khác — 30/09/2026) — đang ở
    đâu, đã xong gì, còn chờ gì."""
    return await BangHanhTrinhService(pool).hom_nay(identity=identity, ngay=ngay)


@router.get("/luot-kham/visits/{visit_id}/hanh-trinh-khach")
async def hanh_trinh_khach(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khung ĐẦY ĐỦ hành trình một khách (Tuyền chốt 29/09/2026): đang ở, tiếp
    theo, dòng thời gian từng bước kèm giờ vào hàng / bắt đầu / xong."""
    return await HanhTrinhKhachService(pool).mot_luot(
        visit_id=str(visit_id), identity=identity
    )


@router.get("/luot-kham/hanh-trinh-khach")
async def hanh_trinh_khach_gon(
    luot: str = Query("", max_length=12000),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dạng GỌN của nhiều lượt (`?luot=id1,id2`) — mỗi khách một dòng. Mã rác
    bị bỏ qua (trả rỗng, không lỗi)."""
    return await HanhTrinhKhachService(pool).gon_nhieu_luot(
        luot=luot, identity=identity
    )
