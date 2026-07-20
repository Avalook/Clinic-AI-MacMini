"""Service-layer tests for SchedulingService.get_oncall_staff."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.services.scheduling_service import SchedulingService


@pytest.fixture
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool, conn


@pytest.mark.asyncio
async def test_get_oncall_staff_not_found_returns_none(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """Missing work_session row → service returns None (no exception)."""
    pool, conn = mock_pool
    conn.fetchrow.return_value = None

    svc = SchedulingService(pool)
    result = await svc.get_oncall_staff(uuid4())

    assert result is None
    # fetch should not be called when session lookup misses
    conn.fetch.assert_not_awaited()
