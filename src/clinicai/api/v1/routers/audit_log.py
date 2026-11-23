"""Nhật ký thao tác — ai đã làm gì, với ai, lúc nào.

Đường ĐỌC duy nhất cho màn ``/audit-log``. Trước đây màn ấy gọi thẳng Supabase
từ Server Component, nên không JOIN được sang ``staff``/``patient`` và phải
trộn hai nguồn bằng JavaScript.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.schemas.nhat_ky_xem import NhatKyXemHoSo
from clinicai.services import nhat_ky_xem_ho_so
from clinicai.services.audit_log_service import AuditLogService

router = APIRouter()

# Nhật ký cho biết ai đã đọc/sửa hồ sơ của ai — bản thân nó là thông tin nhạy
# cảm. Ba vai này khớp đúng policy `event_log_select_ops`; backend chạy service
# role và bỏ qua RLS, nên danh sách phải tự khớp chứ không được tin RLS.
# Lego 20 — "Lịch sử thao tác" (25/09/2026): hỏi quyền, không hỏi vai.
_GUARD = cua_quyen("audit.view")


@router.get("/audit/events")
async def events(
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Toàn bộ nhật ký trong ngày Việt Nam hiện tại, đã giải nghĩa.

    KHÔNG nhận ``clinic_id`` từ người gọi — nó lấy từ danh tính đã xác thực.
    """
    return await AuditLogService(pool).events(identity=identity)


# AI XEM HỒ SƠ (24/11/2026, NĐ 356/2025): quyền `permission.manage` (khối Phân
# quyền — chỉ Quản lý, ngoài "mở full lego"). KHÔNG `ops.view` / `audit.view`: từ
# 30/09 gần như ai cũng có hai quyền ấy.
_XEM_HO_SO_GUARD = cua_quyen(
    "permission.manage", cau="Chỉ quản lý xem được nhật ký ai mở hồ sơ."
)


@router.get("/ops/xem-ho-so", response_model=NhatKyXemHoSo)
async def ai_xem_ho_so(
    response: Response,
    tu: str | None = Query(default=None, max_length=10),
    den: str | None = Query(default=None, max_length=10),
    ma_khach: str | None = Query(default=None, max_length=32),
    staff_id: str | None = Query(default=None, max_length=36),
    identity: StaffIdentity = Depends(_XEM_HO_SO_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Ai đã mở hồ sơ khách nào, lúc nào, qua cửa nào. Ngày rác → hôm nay; id
    nhân viên rác → bỏ lọc. clinic_id lấy từ danh tính."""
    response.headers["Cache-Control"] = "private, no-store"
    return await nhat_ky_xem_ho_so.doc_nhat_ky_xem(
        pool,
        clinic_id=identity.clinic_id,
        tu=tu,
        den=den,
        ma_khach=ma_khach,
        staff_id=staff_id,
    )
