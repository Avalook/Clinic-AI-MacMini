"""Số liệu báo cáo."""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.reports_service import ReportsService

router = APIRouter()


@router.get("/reports/booking-channels")
async def booking_channels(
    days: int = Query(30, ge=1, le=365),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch hẹn theo nguồn đặt — MỘT truy vấn thay cho 8 lượt đếm rời."""
    return await ReportsService(pool).booking_channels(identity=identity, days=days)
