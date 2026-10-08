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
from fastapi.responses import Response

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.bao_cao_cuoi_ngay_service import (
    BaoCaoCuoiNgayService,
    csv_bao_cao,
)
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

# Lọc theo cơ sở (08/10/2026 — mở cơ sở Hào Nam). Rỗng = tất cả cơ sở; mã rác
# KHÔNG 422/500 mà ra số 0 (`co_so_bao_cao.doc_co_so`), cùng lối "rác không làm
# sập báo cáo" với ngày rác ở dưới.
_CO_SO = Query(None, max_length=64, description="uuid cơ sở; rỗng = tất cả; rác = số 0")


@router.get("/reports/booking-channels")
async def booking_channels(
    days: int = Query(30, ge=1, le=365),
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch hẹn theo nguồn đặt — MỘT truy vấn thay cho 8 lượt đếm rời."""
    return await ReportsService(pool).booking_channels(
        identity=identity, days=days, location_id=co_so
    )


@router.get("/reports/kpi-dat-lich")
async def kpi_dat_lich(
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mỗi nhân viên đặt được bao nhiêu lịch — hôm nay, tuần này, tháng này.

    CHỈ QUẢN LÝ ĐỌC ĐƯỢC, cùng cửa với các số liệu báo cáo khác. Đây là bảng so
    sánh giữa người với người; mở cho chính những người bị so sánh là một quyết
    định về quản trị con người, không phải một quyết định kỹ thuật, nên nó phải
    được nói ra chứ không rơi vào mặc định.
    """
    return await ReportsService(pool).kpi_dat_lich_theo_nhan_vien(
        identity=identity, location_id=co_so
    )


@router.get("/reports/tong-quan")
async def bao_cao_tong_quan(
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(_TONG_QUAN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ô số trang /reports: hôm nay · ngày mai · theo bác sĩ · 30 ngày · 7 ngày."""
    return await tong_quan(pool, identity=identity, location_id=co_so)


@router.get("/reports/toan-canh")
async def bao_cao_toan_canh(
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(_TONG_QUAN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tab "Toàn cảnh" của /ops: nhân sự · bốn con số hôm nay · 10 sự kiện."""
    return await toan_canh(pool, identity=identity, location_id=co_so)


# ── Báo cáo cuối ngày (29/09/2026) — tài chính kiểu KiotViet, CHỈ ĐỌC ──────
# Ngày rác / rỗng → hôm nay, không 422: người xem gõ sai ngày vẫn thấy số hôm
# nay chứ không thấy trang lỗi.


@router.get("/reports/cuoi-ngay")
async def bao_cao_cuoi_ngay(
    tu: str | None = Query(
        None, max_length=40, description="YYYY-MM-DD; rác = hôm nay"
    ),
    den: str | None = Query(
        None, max_length=40, description="YYYY-MM-DD; rác = hôm nay"
    ),
    loai: str | None = Query(
        None,
        max_length=20,
        description="dich_vu | thuoc — xem riêng một loại tiền; rỗng/rác = cả hai",
    ),
    co_so: str | None = _CO_SO,
    ca: str | None = Query(
        None,
        max_length=10,
        description="SANG | CHIEU | TOI — cuối ca (một ngày); rác = cả ngày",
    ),
    identity: StaffIdentity = Depends(_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thu gốc · huỷ · hoàn · thực thu; theo hình thức / loại / người thu / ngày;
    thuốc kê vs thực bán theo khách. ``ca`` → chỉ khung giờ một ca (cuối ca).

    Không chọn cơ sở → thêm ``theo_co_so`` (từng cơ sở, tiền cộng lại = tổng)."""
    return await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=identity, tu=tu, den=den, loai=loai, co_so=co_so, ca=ca
    )


@router.get("/reports/cuoi-ngay.csv")
async def bao_cao_cuoi_ngay_csv(
    tu: str | None = Query(None, max_length=40),
    den: str | None = Query(None, max_length=40),
    loai: str | None = Query(None, max_length=20),
    co_so: str | None = _CO_SO,
    ca: str | None = Query(None, max_length=10),
    identity: StaffIdentity = Depends(_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """[Xuất Excel]: CSV UTF-8 có BOM."""
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=identity, tu=tu, den=den, loai=loai, co_so=co_so, ca=ca
    )
    ten = f"bao-cao-cuoi-ngay-{bc['tu']}_{bc['den']}.csv"
    return Response(
        content=csv_bao_cao(bc).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{ten}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
