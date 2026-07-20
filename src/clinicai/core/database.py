"""Asyncpg connection pool lifecycle + FastAPI dependency."""

import os
from typing import AsyncGenerator

import asyncpg
import structlog
from fastapi import Request

logger = structlog.get_logger()

POOL_MIN_SIZE = 2
POOL_MAX_SIZE = 10


def _normalize_dsn(dsn: str) -> str:
    """Strip SQLAlchemy-style '+asyncpg' driver suffix; asyncpg needs bare scheme."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


async def create_pool() -> asyncpg.Pool:
    """Create the asyncpg connection pool from DATABASE_URL env var."""
    dsn = _normalize_dsn(os.environ["DATABASE_URL"])
    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=POOL_MIN_SIZE,
        max_size=POOL_MAX_SIZE,
    )
    logger.info("DB pool ready", min_size=POOL_MIN_SIZE, max_size=POOL_MAX_SIZE)
    return pool


async def close_pool(pool: asyncpg.Pool) -> None:
    """Close the asyncpg connection pool."""
    await pool.close()
    logger.info("DB pool closed")


async def get_db_pool(request: Request) -> AsyncGenerator[asyncpg.Pool, None]:
    """FastAPI dependency that yields the application's asyncpg pool."""
    yield request.app.state.db_pool
