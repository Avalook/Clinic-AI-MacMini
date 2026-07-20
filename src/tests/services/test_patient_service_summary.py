"""Service-layer tests for PatientService.get_summary_data."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.services.patient_service import PatientService


@pytest.fixture
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool, conn


@pytest.mark.asyncio
async def test_get_summary_data_not_found_returns_none(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """Service returns None when no patient row matches the id."""
    pool, conn = mock_pool
    conn.fetchrow.return_value = None

    svc = PatientService(pool)
    result = await svc.get_summary_data(uuid4())

    assert result is None
    conn.fetchrow.assert_awaited_once()
