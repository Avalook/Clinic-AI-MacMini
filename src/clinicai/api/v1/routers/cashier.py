"""Bảng thu ngân — một đường, một vòng mạng.

Trước đây màn này đọc PostgREST theo hai đợt nối tiếp (≈420ms). Đo được một
truy vấn PostgREST ~210ms còn một vòng Postgres ~73ms, nên gộp xuống đây.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.cashier_board_service import (
    CashierBoardService,
)
from clinicai.services.quay_thu_service import QuayThuService, csv_lich_su

router = APIRouter()

# Bảng thu ngân: người giữ một trong hai khối thu tiền (24/09/2026 — thay
# CASHIER_ROLES, cùng người).
_GUARD = cua_quyen("payment.service.collect", "payment.medicine.collect")
#: IN phiếu thu (chỉ đọc): quầy thu + CSKH in hoá đơn trả khách (28/09/2026).
_PHIEU_GUARD = cua_quyen(
    "payment.service.collect", "payment.medicine.collect", "crm.manage"
)


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


# ── Quầy thu MỘT hoá đơn (27/09/2026, đợt 3) ───────────────────────────────
# Cùng cửa với bảng thu ngân. Bộ lọc rác → bỏ qua, không 422: người đứng quầy
# gõ sai ngày thì vẫn thấy sổ hôm nay, không thấy trang lỗi.


@router.get("/cashier/lich-su")
async def cashier_lich_su(
    tu: str | None = Query(None, description="YYYY-MM-DD; rỗng/rác = hôm nay"),
    den: str | None = Query(None, description="YYYY-MM-DD; rỗng/rác = hôm nay"),
    tim: str | None = Query(None, max_length=200),
    hinh_thuc: str | None = Query(None, max_length=20),
    nguoi_thu: str | None = Query(None, max_length=200),
    kind: str = Query("dich_vu", max_length=20),
    chi_tiet: bool = Query(False),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Sổ thu / hoàn GOM THEO KHÁCH (tab Đã thu hôm nay · Lịch sử) — chỉ đọc."""
    return await QuayThuService(pool).lich_su(
        identity=identity,
        tu=tu,
        den=den,
        tim=tim,
        hinh_thuc=hinh_thuc,
        nguoi_thu=nguoi_thu,
        kind=kind,
        chi_tiet=chi_tiet,
    )


@router.get("/cashier/lich-su.csv")
async def cashier_lich_su_csv(
    tu: str | None = Query(None),
    den: str | None = Query(None),
    tim: str | None = Query(None, max_length=200),
    hinh_thuc: str | None = Query(None, max_length=20),
    nguoi_thu: str | None = Query(None, max_length=200),
    kind: str = Query("dich_vu", max_length=20),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """[Xuất Excel]: CSV UTF-8 có BOM — mỗi lần thu / hoàn / huỷ một dòng."""
    kq = await QuayThuService(pool).lich_su(
        identity=identity,
        tu=tu,
        den=den,
        tim=tim,
        hinh_thuc=hinh_thuc,
        nguoi_thu=nguoi_thu,
        kind=kind,
    )
    ten = f"so-thu-{kq['tu']}_{kq['den']}.csv"
    return Response(
        content=csv_lich_su(kq["khach"]).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{ten}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/cashier/phieu/{phieu_id}")
async def cashier_phieu(
    phieu_id: UUID,
    loai: str = Query("thu", pattern="^(thu|hoan|huong_dan)$"),
    identity: StaffIdentity = Depends(_PHIEU_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dữ liệu bản in PHIẾU THU (hoặc PHIẾU HOÀN) — chỉ phiếu của phòng khám mình.

    ``loai=huong_dan``: ``phieu_id`` là mã LƯỢT — phiếu hướng dẫn phòng làm dịch
    vụ, in được cả khi chưa thu (làm trước, thu sau — 30/09/2026)."""
    return await QuayThuService(pool).phieu(
        identity=identity, id_=str(phieu_id), loai=loai
    )


@router.get("/cashier/phieu-luot/{visit_id}")
async def cashier_phieu_luot(
    visit_id: UUID,
    kind: str = Query("thuoc", pattern="^(thuoc|dich_vu)$"),
    identity: StaffIdentity = Depends(_PHIEU_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mọi phiếu thu ĐÃ THU của một lượt theo loại — CSKH in hoá đơn trả khách."""
    return await QuayThuService(pool).phieu_cua_luot(
        identity=identity, visit_id=str(visit_id), kind=kind
    )
