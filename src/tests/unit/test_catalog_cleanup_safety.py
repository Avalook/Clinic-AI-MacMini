"""Catalog teardown must never touch a shared or production database."""

from unittest.mock import AsyncMock

import pytest

from tests.catalog_cleanup import retire_new_catalog_rows


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://postgres:pw@222.255.214.133:55433/postgres",
        "postgresql://postgres:pw@localhost:54422/postgres",
        "postgresql://postgres:pw@localhost:55600/clinicai",
        "postgresql://postgres:pw@localhost:55600/khuon",
    ],
)
async def test_unsafe_database_is_rejected_before_any_query(dsn: str) -> None:
    pool = AsyncMock()
    with pytest.raises(ValueError, match="disposable"):
        async with retire_new_catalog_rows(pool, dsn=dsn):
            pass
    pool.fetchval.assert_not_awaited()
    pool.fetch.assert_not_awaited()
    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_connection_database_must_match_validated_dsn() -> None:
    pool = AsyncMock()
    pool.fetchval.return_value = "clinicai"
    with pytest.raises(ValueError, match="database"):
        async with retire_new_catalog_rows(
            pool, dsn="postgresql://postgres:pw@localhost:55600/tam_123_work"
        ):
            pass
    pool.fetch.assert_not_awaited()
    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "port,database",
    [(55600, "tam_123_work"), (55530, "ci_gw0"), (55433, "postgres")],
)
async def test_disposable_database_allows_cleanup(port: int, database: str) -> None:
    pool = AsyncMock()
    pool.fetchval.return_value = database
    pool.fetch.return_value = []
    async with retire_new_catalog_rows(
        pool, dsn=f"postgresql://postgres:pw@localhost:{port}/{database}"
    ):
        pass
    assert pool.execute.await_count == 4
