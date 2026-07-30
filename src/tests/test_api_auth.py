"""Tests for the X-API-Key middleware (src/clinicai/api/auth.py).

Covers the four behaviours promised by ``api_key_middleware``:
* /health (exempt path) always works
* development + no key → middleware logs warning and passes through
* production + no key → middleware fails closed with 503
* protected route + env var set + missing header → 401
* protected route + env var set + wrong header → 403
* protected route + env var set + right header → 200
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from clinicai.api.auth import API_KEY_HEADER, ENV_VAR_NAME, api_key_middleware


@pytest.fixture
def app() -> FastAPI:
    """Throwaway app that mounts only the middleware + a stub protected route.

    Keeps the unit isolated from the real ClinicAI app (which has DB pools
    and a lifespan handler we do not need here).
    """
    a = FastAPI()
    a.middleware("http")(api_key_middleware)

    @a.get("/health")
    async def _health() -> dict[str, str]:
        return {"status": "ok"}

    @a.get("/api/v1/patients/")
    async def _protected() -> dict[str, str]:
        return {"ok": "yes"}

    return a


@pytest.fixture
def patch_env() -> Iterator[None]:
    """Snapshot auth-related environment and restore it after each test."""
    prior = {
        ENV_VAR_NAME: os.environ.get(ENV_VAR_NAME),
        "APP_ENV": os.environ.get("APP_ENV"),
    }
    yield
    for name, value in prior.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.mark.asyncio
async def test_health_always_passes(app: FastAPI, patch_env: None) -> None:
    os.environ[ENV_VAR_NAME] = "secret-A"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_missing_env_falls_through_with_warning(
    app: FastAPI, patch_env: None
) -> None:
    """Dev-friendly fallback: missing env var → request still served."""
    os.environ["APP_ENV"] = "development"
    os.environ.pop(ENV_VAR_NAME, None)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/patients/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_missing_key_in_production_fails_closed(
    app: FastAPI, patch_env: None
) -> None:
    os.environ["APP_ENV"] = "production"
    os.environ.pop(ENV_VAR_NAME, None)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/patients/")
    assert r.status_code == 503
    assert r.json()["error"] == "SERVER_MISCONFIGURED"


@pytest.mark.asyncio
async def test_missing_key_and_app_env_fails_closed(
    app: FastAPI, patch_env: None
) -> None:
    """An unknown runtime must not be silently treated as development."""
    os.environ.pop("APP_ENV", None)
    os.environ.pop(ENV_VAR_NAME, None)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/patients/")
    assert r.status_code == 503
    assert r.json()["error"] == "SERVER_MISCONFIGURED"


@pytest.mark.asyncio
async def test_missing_header_returns_401(app: FastAPI, patch_env: None) -> None:
    os.environ[ENV_VAR_NAME] = "secret-B"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/patients/")
    assert r.status_code == 401
    body = r.json()
    assert body["error"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_wrong_header_returns_403(app: FastAPI, patch_env: None) -> None:
    os.environ[ENV_VAR_NAME] = "secret-C"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/patients/", headers={API_KEY_HEADER: "wrong"})
    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_correct_header_passes(app: FastAPI, patch_env: None) -> None:
    os.environ[ENV_VAR_NAME] = "secret-D"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/patients/", headers={API_KEY_HEADER: "secret-D"})
    assert r.status_code == 200
    assert r.json() == {"ok": "yes"}
