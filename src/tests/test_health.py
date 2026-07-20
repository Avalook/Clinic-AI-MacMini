"""Health check endpoint tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.core.database import get_db_pool
from clinicai.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_db():
    """GET /health/db returns ok with latency when pool's SELECT 1 succeeds."""
    mock_conn = MagicMock()
    mock_conn.fetchval = AsyncMock(return_value=1)

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=acquire_ctx)

    async def override_pool():
        yield mock_pool

    app.dependency_overrides[get_db_pool] = override_pool
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "connected"
    assert isinstance(body["latency_ms"], (int, float))
    mock_conn.fetchval.assert_awaited_once_with("SELECT 1")
