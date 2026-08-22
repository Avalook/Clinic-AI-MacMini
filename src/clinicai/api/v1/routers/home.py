"""Trang chủ — một endpoint gói thay 6 vòng PostgREST + 3 endpoint rời.

Lát 3 của lộ trình chịu tải, 22/08/2026. Xem man_trang_chu_service để biết vì
sao và gói những gì.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.man_trang_chu_service import ManTrangChuService

router = APIRouter()


@router.get("/home/bang-dieu-khien")
async def bang_dieu_khien(
    week_appt: date_cls,
    week_roster: date_cls,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mọi dữ liệu Trang chủ trong một lượt.

    Không guard theo vai — roles.ts khai `"/home": "all"`, trang chủ mở cho
    mọi vai đã đăng nhập (get_current_identity đã chặn DISPLAY và người lạ);
    các KHỐI theo vai (bảng Lễ tân, ô check-in Quản lý) do service tự quyết
    từ identity, không nhận cờ từ client.

    Hai tham số tuần khai kiểu ``date`` để chuỗi rác bị FastAPI chặn bằng 422
    ngay cửa — cùng lý do với ``/appointments/week``.

    KHÔNG ``response_model``: các khối bắt chước hình PostgREST với khoá lồng
    tuỳ dữ liệu; một model khai thiếu trường sẽ âm thầm cắt nó khỏi JSON (bẫy
    đã ghi ở /cskh/man-khach-hang).
    """
    du_lieu = await ManTrangChuService(pool).goi_du_lieu(
        identity=identity, week_appt=week_appt, week_roster=week_roster
    )
    return {"ok": True, **du_lieu}
