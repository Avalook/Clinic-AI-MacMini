"""Nhật ký thao tác — ai đã làm gì, với ai, lúc nào.

Đường ĐỌC duy nhất cho màn ``/audit-log``. Trước đây màn ấy gọi thẳng Supabase
từ Server Component, nên không JOIN được sang ``staff``/``patient`` và phải
trộn hai nguồn bằng JavaScript.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
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
