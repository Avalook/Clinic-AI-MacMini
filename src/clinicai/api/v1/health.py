"""Health check endpoints (liveness + database)."""

import time

import asyncpg
import structlog
from fastapi import APIRouter, Depends

from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import ExternalServiceError

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Liveness probe — does not touch external dependencies."""
    return {"status": "ok", "service": "clinicai"}


@router.get("/health/db")
async def health_db(pool: asyncpg.Pool = Depends(get_db_pool)) -> dict:
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
