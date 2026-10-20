"""Audit probes: run only with scripts/test-nhanh.sh on a disposable database.

These assert intended security/replay contracts. A failure is audit evidence,
not a proposed production change. No patient records are read or written.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_discount_migration_can_be_reapplied() -> None:
    """A schema migration must tolerate replay on the current schema."""
    dsn = os.environ["DATABASE_URL_TEST"]
    database_name = urlsplit(dsn).path.removeprefix("/")
    assert database_name.startswith("tam_"), "Audit probe requires temporary DB"
    root = Path(__file__).resolve().parents[3]
    migration = root / "supabase/migrations/20261013100000_giam_gia.sql"
    connection = await asyncpg.connect(dsn)
    transaction = connection.transaction()
    await transaction.start()
    try:
        await connection.execute(migration.read_text())
    finally:
        await transaction.rollback()
        await connection.close()
