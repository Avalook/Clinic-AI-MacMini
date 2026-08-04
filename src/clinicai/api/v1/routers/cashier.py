"""Bảng thu ngân — một đường, một vòng mạng.

Trước đây màn này đọc PostgREST theo hai đợt nối tiếp (≈420ms). Đo được một
truy vấn PostgREST ~210ms còn một vòng Postgres ~73ms, nên gộp xuống đây.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query

from clinicai.api.identity import StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.cashier_board_service import (
    CASHIER_ROLES,
    CashierBoardService,
)

router = APIRouter()

_GUARD = require_role(*CASHIER_ROLES)


@router.get("/cashier/board")
async def cashier_board(
    modes: str = Query(
        "dich_vu,thuoc",
        description="Ô nào cần: dich_vu, thuoc, hoặc cả hai (ngăn bởi dấu phẩy).",
    ),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bệnh nhân cần thu tiền hôm nay, kèm dịch vụ / thuốc / đã thu.

    `modes` theo vai: CASHIER_THUOC chỉ thuốc, CASHIER_DV chỉ dịch vụ, CASHIER
    cả hai. Vai được kiểm ở tầng router; `modes` chỉ quyết định hiện ô nào.
    """
    wanted = [m.strip() for m in modes.split(",") if m.strip()]
    return await CashierBoardService(pool).board(identity=identity, modes=wanted)
