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

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.reports_service import (
    ReportsService,
    toan_canh,
    tong_quan,
)

router = APIRouter()

# Lego 17 "Báo cáo" (25/09/2026): hỏi quyền, không hỏi vai.
_READ_GUARD = cua_quyen("report.view")
#: Các ô đếm tổng (không tên khách, không so người với người) — cùng tập vai
#: trang /reports đang mở (`isOpsAdmin` = quản lý + trưởng ca).
# Toàn cảnh: tab của Vận hành (/ops) và báo cáo.
_TONG_QUAN_GUARD = cua_quyen("report.view", "ops.view")


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


@router.get("/reports/tong-quan")
async def bao_cao_tong_quan(
    identity: StaffIdentity = Depends(_TONG_QUAN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ô số trang /reports: hôm nay · ngày mai · theo bác sĩ · 30 ngày · 7 ngày."""
    return await tong_quan(pool, identity=identity)


@router.get("/reports/toan-canh")
async def bao_cao_toan_canh(
    identity: StaffIdentity = Depends(_TONG_QUAN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tab "Toàn cảnh" của /ops: nhân sự · bốn con số hôm nay · 10 sự kiện."""
    return await toan_canh(pool, identity=identity)
