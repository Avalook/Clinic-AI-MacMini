"""Shared fixtures for tools.task tests.

The task tools use `async with pool.acquire() as conn` (unlike
find_work_sessions which calls pool.fetch directly). This fixture
returns (pool, conn) so each test can program conn.fetchrow / conn.fetch
return values independently.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_pool_conn() -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    acquire_ctx.__aexit__.return_value = False
    pool.acquire.return_value = acquire_ctx
    return pool, conn
