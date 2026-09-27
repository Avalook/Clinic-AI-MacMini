"""Health check endpoints (liveness + database)."""

import time
from typing import Any

import asyncpg
import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import ExternalServiceError

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Liveness probe — does not touch external dependencies."""
    return {"status": "ok", "service": "clinicai"}


@router.get("/health/db")
async def health_db(pool: asyncpg.Pool = Depends(get_db_pool)) -> dict[str, Any]:
    """Readiness probe — runs SELECT 1 against the asyncpg pool."""
    start = time.perf_counter()
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as exc:
        logger.error("db_health_check_failed", error=str(exc))
        raise ExternalServiceError("Database health check failed") from exc
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return {"status": "ok", "db": "connected", "latency_ms": latency_ms}


#: Ngưỡng (27/09/2026 — kế hoạch theo dõi lỗi Pha 0). Worker quét hàng mỗi 1 giây
#: (``events/worker.py: chay_vong``), nên tin ĐÃ TỚI HẠN giao mà nằm quá 3 phút
#: = worker chết / treo. Đo theo "tới hạn" chứ không theo "lần giao cuối": giờ
#: vắng khách worker im cả tiếng là bình thường. Tin tồn quá 15 phút (dù đang
#: đợi lượt thử lại) = bên nhận hỏng lặp đi lặp lại — khách check-in xong không
#: vào hàng.
TRE_GIAO_PHUT = 3
TON_LAU_PHUT = 15


def danh_gia_su_kien(so: dict[str, Any]) -> list[str]:
    """Hàm THUẦN: các lý do "không khoẻ" từ số đếm. Rỗng = khoẻ."""
    ly_do: list[str] = []
    if so["tre_giao"]:
        ly_do.append(
            f"{so['tre_giao']} tin tới hạn quá {TRE_GIAO_PHUT} phút chưa ai giao"
            " (worker chết / treo?)"
        )
    if so["ton_lau"]:
        ly_do.append(f"{so['ton_lau']} tin tồn quá {TON_LAU_PHUT} phút chưa giao xong")
    if so["chet_24h"]:
        ly_do.append(f"{so['chet_24h']} tin chết (DEAD) trong 24 giờ")
    if so["hen_gio_tre"]:
        ly_do.append(f"{so['hen_gio_tre']} hẹn giờ trễ quá {TRE_GIAO_PHUT} phút")
    if so["hen_gio_chet_24h"]:
        ly_do.append(f"{so['hen_gio_chet_24h']} hẹn giờ chết trong 24 giờ")
    return ly_do


@router.get("/health/su-kien")
async def health_su_kien(pool: asyncpg.Pool = Depends(get_db_pool)) -> Any:
    """Người đưa tin sự kiện có đang giao không (Kuma gọi mỗi phút).

    503 khi có tin trễ / tồn lâu / chết mới, hoặc hẹn giờ trễ / chết. Chỉ SỐ
    ĐẾM — không mã đối tượng, không nội dung lỗi (có thể mang dữ liệu khách).
    Không có service ``su-kien`` thì khách check-in xong không vào hàng nào.
    """
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """
            SELECT
              count(*) FILTER (WHERE status IN ('PENDING', 'RETRY')) AS dang_cho,
              count(*) FILTER (WHERE
                (status IN ('PENDING', 'RETRY')
                  AND coalesce(next_attempt_at, created_at)
                      < now() - make_interval(mins => $1))
                OR (status = 'IN_PROGRESS'
                  AND lease_expires_at < now() - make_interval(mins => $1)))
                AS tre_giao,
              count(*) FILTER (WHERE status IN ('PENDING', 'RETRY', 'IN_PROGRESS')
                AND created_at < now() - make_interval(mins => $2)) AS ton_lau,
              count(*) FILTER (WHERE status = 'DEAD'
                AND created_at > now() - interval '24 hours') AS chet_24h
              FROM event_delivery
            """,
            TRE_GIAO_PHUT,
            TON_LAU_PHUT,
        )
        h = await conn.fetchrow(
            """
            SELECT
              count(*) FILTER (WHERE
                (trang_thai = 'CHO' AND den_gio < now() - make_interval(mins => $1))
                OR (trang_thai = 'DANG_LAM'
                  AND thue_den < now() - make_interval(mins => $1)))
                AS hen_gio_tre,
              count(*) FILTER (WHERE trang_thai = 'CHET'
                AND den_gio > now() - interval '24 hours') AS hen_gio_chet_24h
              FROM hen_gio
            """,
            TRE_GIAO_PHUT,
        )
    so = {**dict(r), **dict(h)}
    ly_do = danh_gia_su_kien(so)
    than = {"status": "degraded" if ly_do else "ok", "so": so, "ly_do": ly_do}
    return JSONResponse(than, status_code=503 if ly_do else 200)
