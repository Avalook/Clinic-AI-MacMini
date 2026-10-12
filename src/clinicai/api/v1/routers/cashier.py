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

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.cashier_board_service import (
    CashierBoardService,
)
from clinicai.services.cashier_scope_service import CashierScopeService
from clinicai.services.quay_thu_service import QuayThuService, csv_lich_su

router = APIRouter()

# Authentication first; each read checks exact roster scope below.
_GUARD = get_current_identity
_PHIEU_GUARD = get_current_identity


@router.get("/cashier/ngay-truc")
async def cashier_ngay_truc(
    quay: str = Query("dich_vu", max_length=20),
    cursor: str | None = Query(None, max_length=40),
    limit: int = Query(30, ge=1, le=100),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await CashierScopeService(pool).days(
        identity, kind=quay, cursor=cursor, limit=limit
    )


@router.get("/cashier/board")
async def cashier_board(
    modes: str = Query(
        "dich_vu,thuoc",
        description="Ô nào cần: dich_vu, thuoc, hoặc cả hai (ngăn bởi dấu phẩy).",
    ),
    ngay: str | None = Query(
        None,
        max_length=32,
        description="YYYY-MM-DD giờ VN — xem lại một ngày cũ (02/10/2026); "
        "rỗng / rác = hôm nay",
    ),
    ca: str | None = Query(None, max_length=10),
    co_so: str | None = Query(None, max_length=40),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bệnh nhân cần thu tiền trong ngày (mặc định hôm nay), kèm dịch vụ /
    thuốc / đã thu.

    `modes` theo vai: CASHIER_THUOC chỉ thuốc, CASHIER_DV chỉ dịch vụ, CASHIER
    cả hai. Vai được kiểm ở tầng router; `modes` chỉ quyết định hiện ô nào.
    """
    wanted = [m.strip() for m in modes.split(",") if m.strip()]
    scopes = [
        await CashierScopeService(pool).authorize_active(
            identity, kind=kind, co_so=co_so
        )
        for kind in wanted
    ]
    if not scopes:
        from clinicai.core.exceptions import SafetyGateError

        raise SafetyGateError("Hãy chọn quầy dịch vụ hoặc thuốc.")
    scope = scopes[0]
    if any(s != scope for s in scopes):
        from clinicai.core.exceptions import SafetyGateError

        raise SafetyGateError("Hãy xem từng quầy trong ca được phân công.")
    return await CashierBoardService(pool).board(
        identity=scope.identity,
        modes=wanted,
        ngay=None,
        scope_starts=scope.starts,
        scope_ends=scope.ends,
        scope_actor=scope.actor_id,
    )


@router.get("/cashier/giao-dich")
async def cashier_giao_dich(
    tu: str | None = Query(None, description="YYYY-MM-DD; rỗng = hôm nay"),
    den: str | None = Query(None, description="YYYY-MM-DD; rỗng = hôm nay"),
    kind: str | None = Query(
        None,
        max_length=20,
        description="dich_vu | thuoc — mỗi quầy chỉ xem sổ loại tiền của mình; "
        "rỗng = cả hai (01/10/2026)",
    ),
    ca: str | None = Query(None, max_length=10),
    co_so: str | None = Query(None, max_length=40),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Giao dịch đã ghi trong khoảng ngày (kể cả đã huỷ) — chỉ đọc."""
    scope = await CashierScopeService(pool).authorize(
        identity, tu=tu, den=den, kind=kind or "", ca=ca, co_so=co_so
    )
    return await CashierBoardService(pool).giao_dich(
        identity=scope.identity,
        tu=tu,
        den=den,
        kind=kind,
        scope_starts=scope.starts,
        scope_ends=scope.ends,
        scope_actor=scope.actor_id,
    )


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
    ca: str | None = Query(None, max_length=10),
    co_so: str | None = Query(None, max_length=40),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Sổ thu / hoàn GOM THEO KHÁCH (tab Đã thu hôm nay · Lịch sử) — chỉ đọc."""
    scope = await CashierScopeService(pool).authorize(
        identity, tu=tu, den=den, kind=kind, ca=ca, co_so=co_so
    )
    return await QuayThuService(pool).lich_su(
        identity=scope.identity,
        tu=tu,
        den=den,
        tim=tim,
        hinh_thuc=hinh_thuc,
        nguoi_thu=nguoi_thu,
        kind=kind,
        chi_tiet=chi_tiet,
        scope_starts=scope.starts,
        scope_ends=scope.ends,
        scope_actor=scope.actor_id,
    )


@router.get("/cashier/lich-su.csv")
async def cashier_lich_su_csv(
    tu: str | None = Query(None),
    den: str | None = Query(None),
    tim: str | None = Query(None, max_length=200),
    hinh_thuc: str | None = Query(None, max_length=20),
    nguoi_thu: str | None = Query(None, max_length=200),
    kind: str = Query("dich_vu", max_length=20),
    ca: str | None = Query(None, max_length=10),
    co_so: str | None = Query(None, max_length=40),
    identity: StaffIdentity = Depends(_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """[Xuất Excel]: CSV UTF-8 có BOM — mỗi lần thu / hoàn / huỷ một dòng."""
    scope = await CashierScopeService(pool).authorize(
        identity, tu=tu, den=den, kind=kind, ca=ca, co_so=co_so
    )
    kq = await QuayThuService(pool).lich_su(
        identity=scope.identity,
        tu=tu,
        den=den,
        tim=tim,
        hinh_thuc=hinh_thuc,
        nguoi_thu=nguoi_thu,
        kind=kind,
        scope_starts=scope.starts,
        scope_ends=scope.ends,
        scope_actor=scope.actor_id,
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
    await CashierScopeService(pool).receipt(identity, id_=str(phieu_id), loai=loai)
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
    service = CashierScopeService(pool)
    if not await service.receipt_exempt(identity):
        ids = await pool.fetch(
            """SELECT payment_cycle_id::text AS id FROM payment_cycle
                WHERE clinic_id=$1::uuid AND visit_id=$2::uuid AND kind=$3
                AND status='PAID' ORDER BY coalesce(paid_at,created_at),1""",
            identity.clinic_id,
            str(visit_id),
            kind,
        )
        from clinicai.core.exceptions import SafetyGateError

        visible = []
        for row in ids:
            try:
                await service.receipt(identity, id_=row["id"], loai="thu")
            except SafetyGateError:
                continue
            visible.append(
                await QuayThuService(pool).phieu(
                    identity=identity, id_=row["id"], loai="thu"
                )
            )
        return {"phieu": visible}
    return await QuayThuService(pool).phieu_cua_luot(
        identity=identity, visit_id=str(visit_id), kind=kind
    )
