"""
Checkpointer factory — hybrid Memory|Postgres qua env CHECKPOINTER_BACKEND.

Postgres backend:
- Pool RIÊNG (psycopg.AsyncConnectionPool), KHÔNG share với services asyncpg
- Schema `langgraph` (sạch, tách khỏi business tables)
- LangGraph tự tạo 4 bảng qua await saver.setup()
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

logger = structlog.get_logger(__name__)

CHECKPOINTER_SCHEMA = "langgraph"


@asynccontextmanager
async def make_checkpointer(
    backend: Optional[str] = None,
    dsn: Optional[str] = None,
) -> AsyncIterator[BaseCheckpointSaver]:
    """
    Async context manager trả checkpointer + pool (auto-cleanup khi exit).

    backend: 'memory' | 'postgres' (env CHECKPOINTER_BACKEND, fallback 'memory').
    dsn:     Postgres DSN (env CHECKPOINT_DSN or DATABASE_URL).
    """
    backend = backend or os.getenv("CHECKPOINTER_BACKEND", "memory")
    logger.info("checkpointer_init", backend=backend)

    if backend == "memory":
        yield MemorySaver()
        return

    if backend == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        dsn = dsn or os.getenv("CHECKPOINT_DSN") or os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "Postgres checkpointer cần CHECKPOINT_DSN hoặc DATABASE_URL env."
            )

        if "+asyncpg" in dsn:
            dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

        async with AsyncConnectionPool(
            conninfo=dsn,
            max_size=10,
            min_size=2,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "options": f"-c search_path={CHECKPOINTER_SCHEMA},public",
            },
            open=False,
        ) as pool:
            await pool.open(wait=True)

            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"CREATE SCHEMA IF NOT EXISTS {CHECKPOINTER_SCHEMA}"
                    )

            saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
            await saver.setup()
            logger.info(
                "checkpointer_postgres_ready",
                schema=CHECKPOINTER_SCHEMA,
                pool_size=pool.max_size,
            )
            yield saver
        return

    raise ValueError(f"Unknown CHECKPOINTER_BACKEND: {backend}")
