"""Retire test-created catalog rows without breaking their historical foreign keys."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import unquote, urlsplit

import asyncpg


def disposable_database_name(dsn: str) -> str:
    """Accept only local databases created by the project's test wrappers."""
    target = urlsplit(dsn)
    database = unquote(target.path.lstrip("/"))
    allowed_name = re.fullmatch(r"tam_[0-9]+_[a-zA-Z0-9_]+|ci_gw[0-9]+", database)
    known_ci = database == "postgres" and target.port in {55433, 55530}
    if (
        target.scheme != "postgresql"
        or target.hostname not in {"localhost", "127.0.0.1"}
        or target.port is None
        or target.port in {5432, 54422}
        or not (allowed_name or known_ci)
    ):
        raise ValueError("Catalog tests require a disposable local database")
    return database


@asynccontextmanager
async def retire_new_catalog_rows(
    pool: asyncpg.Pool, *, dsn: str
) -> AsyncIterator[None]:
    """Restore seed activation and hide newly created entries after one test."""
    database = disposable_database_name(dsn)
    if await pool.fetchval("SELECT current_database()") != database:
        raise ValueError("Connected database does not match disposable test DSN")
    snapshots = {
        table: await pool.fetch(f"SELECT id, is_active FROM {table}")
        for table in ("service_type", "vi_tri_lam_viec")
    }
    try:
        yield
    finally:
        for table, rows in snapshots.items():
            ids = [row["id"] for row in rows]
            active_ids = [row["id"] for row in rows if row["is_active"]]
            # Table names come exclusively from the two constants above.
            await pool.execute(
                f"UPDATE {table} SET is_active = (id = ANY($2::uuid[]))"
                " WHERE id = ANY($1::uuid[])",
                ids,
                active_ids,
            )
            await pool.execute(
                f"UPDATE {table} SET is_active = false"
                " WHERE NOT (id = ANY($1::uuid[]))",
                ids,
            )
