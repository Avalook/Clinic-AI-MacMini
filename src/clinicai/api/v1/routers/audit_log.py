"""Nhật ký thao tác — ai đã làm gì, với ai, lúc nào.

Đường ĐỌC duy nhất cho màn ``/audit-log``. Trước đây màn ấy gọi thẳng Supabase
từ Server Component, nên không JOIN được sang ``staff``/``patient`` và phải
trộn hai nguồn bằng JavaScript.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query

from clinicai.api.identity import StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.audit_log_service import AUDIT_ROLES, MAX_ROWS, AuditLogService

router = APIRouter()

# Nhật ký cho biết ai đã đọc/sửa hồ sơ của ai — bản thân nó là thông tin nhạy
# cảm. Ba vai này khớp đúng policy `event_log_select_ops`; backend chạy service
# role và bỏ qua RLS, nên danh sách phải tự khớp chứ không được tin RLS.
_GUARD = require_role(*sorted(AUDIT_ROLES))


@router.get("/audit/events")
async def events(
    limit: int = Query(MAX_ROWS, ge=1, le=MAX_ROWS),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Nhật ký gần nhất, đã giải tên người và tên bệnh nhân.

    KHÔNG nhận ``clinic_id`` từ người gọi — nó lấy từ danh tính đã xác thực.
    """
    return await AuditLogService(pool).events(identity=identity, limit=limit)
