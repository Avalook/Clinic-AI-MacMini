"""Bảng thu ngân — một đường, một vòng mạng.

Trước đây màn này đọc PostgREST theo hai đợt nối tiếp (≈420ms). Đo được một
truy vấn PostgREST ~210ms còn một vòng Postgres ~73ms, nên gộp xuống đây.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.cashier_board_service import (
    CashierBoardService,
)

router = APIRouter()

# Bảng thu ngân: người giữ một trong hai khối thu tiền (24/09/2026 — thay
# CASHIER_ROLES, cùng người).
_GUARD = cua_quyen("payment.service.collect", "payment.medicine.collect")


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


@router.get("/cashier/giao-dich")
async def cashier_giao_dich(
    tu: str | None = Query(None, description="YYYY-MM-DD; rỗng = hôm nay"),
    den: str | None = Query(None, description="YYYY-MM-DD; rỗng = hôm nay"),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Giao dịch đã ghi trong khoảng ngày (kể cả đã huỷ) — chỉ đọc."""
    return await CashierBoardService(pool).giao_dich(identity=identity, tu=tu, den=den)
