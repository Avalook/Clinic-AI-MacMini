"""Số liệu báo cáo — CHỈ QUẢN LÝ (Quang chốt 2026-08-06).

Màn /reports vốn đã chỉ mở cho MANAGEMENT trên menu, nhưng endpoint phía sau
không gác vai nào: bất kỳ ai đăng nhập cũng gọi thẳng được và lấy số liệu vận
hành của cả phòng khám. Cửa phòng có khoá, cái tủ bên trong thì không.

Chốt phải đặt ở đây chứ không ở màn hình: màn hình chỉ quyết định người ta THẤY
gì, nó không ngăn được ai gõ thẳng đường dẫn.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.reports_service import ReportsService

router = APIRouter()

_READ_GUARD = require_role(ClinicRole.MANAGEMENT)


@router.get("/reports/booking-channels")
async def booking_channels(
    days: int = Query(30, ge=1, le=365),
    identity: StaffIdentity = Depends(_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch hẹn theo nguồn đặt — MỘT truy vấn thay cho 8 lượt đếm rời."""
    return await ReportsService(pool).booking_channels(identity=identity, days=days)


@router.get("/reports/kpi-dat-lich")
async def kpi_dat_lich(
    identity: StaffIdentity = Depends(_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mỗi nhân viên đặt được bao nhiêu lịch — hôm nay, tuần này, tháng này.

    CHỈ QUẢN LÝ ĐỌC ĐƯỢC, cùng cửa với các số liệu báo cáo khác. Đây là bảng so
    sánh giữa người với người; mở cho chính những người bị so sánh là một quyết
    định về quản trị con người, không phải một quyết định kỹ thuật, nên nó phải
    được nói ra chứ không rơi vào mặc định.
    """
    return await ReportsService(pool).kpi_dat_lich_theo_nhan_vien(identity=identity)
