"""Asyncpg connection pool lifecycle + FastAPI dependency."""

import asyncio
import os
from typing import AsyncGenerator

import asyncpg
import structlog
from fastapi import Request

logger = structlog.get_logger()

POOL_MIN_SIZE = 2
POOL_MAX_SIZE = 10
COMMAND_TIMEOUT = 15  # seconds — per-query timeout to prevent runaway queries
STARTUP_RETRIES = 3
STARTUP_BACKOFF = 2.0  # seconds between retries


def _normalize_dsn(dsn: str) -> str:
    """Strip SQLAlchemy-style '+asyncpg' driver suffix; asyncpg needs bare scheme."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


async def create_pool() -> asyncpg.Pool:
    """Create the asyncpg connection pool from DATABASE_URL env var.

    Retries up to STARTUP_RETRIES times with backoff if Supabase is
    temporarily unreachable during container boot (avoids crash loop).
    """
    dsn = _normalize_dsn(os.environ["DATABASE_URL"])
    last_error: Exception | None = None

    for attempt in range(1, STARTUP_RETRIES + 1):
        try:
            pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                command_timeout=COMMAND_TIMEOUT,
            )
            logger.info(
                "DB pool ready",
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                command_timeout=COMMAND_TIMEOUT,
                attempt=attempt,
            )
            return pool
        except (asyncpg.PostgresConnectionError, OSError) as exc:
            last_error = exc
            logger.warning(
                "db_pool_connect_retry",
                attempt=attempt,
                max_retries=STARTUP_RETRIES,
                error=str(exc),
            )
            if attempt < STARTUP_RETRIES:
                await asyncio.sleep(STARTUP_BACKOFF * attempt)

    # All retries exhausted — raise so the container exits (Docker restarts it).
    raise RuntimeError(
        f"Failed to create DB pool after {STARTUP_RETRIES} attempts"
    ) from last_error


async def close_pool(pool: asyncpg.Pool) -> None:
    """Close the asyncpg connection pool."""
    await pool.close()
    logger.info("DB pool closed")


async def get_db_pool(request: Request) -> AsyncGenerator[asyncpg.Pool, None]:
    """FastAPI dependency that yields the application's asyncpg pool."""
    yield request.app.state.db_pool
