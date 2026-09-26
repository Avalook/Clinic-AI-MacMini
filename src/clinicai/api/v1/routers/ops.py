"""MANAGEMENT-only, read-only operations endpoints: service status and telemetry."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.core.telemetry import SLOW_REQUEST_MS, telemetry
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.schemas.ops import OpsStatusResponse
from clinicai.services.ops_status import OpsStatusService

router = APIRouter()
# Lego 20 "Vận hành hệ thống" (25/09/2026): hỏi quyền, không hỏi vai.
_MANAGEMENT_GUARD = cua_quyen("ops.view")


@router.get("/ops/status", response_model=OpsStatusResponse)
async def get_ops_status(
    response: Response,
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> OpsStatusResponse:
    response.headers["Cache-Control"] = "private, no-store"
    return await OpsStatusService(pool).collect()


@router.get("/ops/telemetry")
async def get_telemetry(
    response: Response,
    window_s: float | None = Query(default=900, ge=0, le=86400),
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
) -> dict[str, object]:
    """Response times and recent failures, from the API process's ring buffer.

    Behind the MANAGEMENT guard like the rest of /ops. It carries no patient
    data by construction (route templates only — see core/telemetry), but it
    does describe the shape of the system, and that is not something to hand to
    every logged-in staff member.

    Defaults to the last 15 minutes: the question at a front desk is "is it slow
    right now", and an average over a whole uptime hides the answer.
    """
    response.headers["Cache-Control"] = "no-store"
    snapshot = telemetry.snapshot(window_s=window_s or None)
    snapshot["slow_threshold_ms"] = SLOW_REQUEST_MS
    return snapshot


@router.get("/ops/su-kien")
async def suc_khoe_su_kien(
    response: Response,
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Sức khoẻ đường đưa tin — bốn số, không hơn.

    Google SRE: số đo nào không có người nhìn hoặc không gắn với cảnh báo thì bỏ.
    Bốn số ở đây là bốn kiểu hỏng khác nhau, không phải bốn cách nói một chuyện:

        cho_lam   tin chưa giao được — tắc ở đâu đó
        chet      đã thử hết lượt, có người phải xử lý tay
        dang_lam  đang giao; số này treo cao nghĩa là worker chết giữa chừng
        cho_lau_giay  tin cũ nhất đã chờ bao lâu — thứ nói "có đang tắc không"

    Hai số đầu đáng bắn Telegram. Hai số sau để nhìn trên bảng.
    """
    response.headers["Cache-Control"] = "no-store"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT consumer, cho_lam, chet, dang_lam,"
            " EXTRACT(EPOCH FROM tuoi_dong_cu_nhat)::int AS cho_lau_giay"
            "  FROM v_event_delivery_suc_khoe ORDER BY consumer"
        )
        tong_su_kien = await conn.fetchval("SELECT count(*) FROM domain_event")
    ben_nhan = [dict(r) for r in rows]
    return {
        "ben_nhan": ben_nhan,
        "tong_su_kien": tong_su_kien,
        # Một cờ để Uptime Kuma hỏi mà không phải hiểu từng con số.
        "on": all(
            (b["chet"] or 0) == 0 and (b["cho_lau_giay"] or 0) < 300 for b in ben_nhan
        ),
    }
