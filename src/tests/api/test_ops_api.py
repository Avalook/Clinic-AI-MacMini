"""Authorization and response tests for the MANAGEMENT-only Ops endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app


class _Acquire:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def fetchval(self, _query: str) -> int:
        return 1


class _Pool:
    def acquire(self) -> _Acquire:
        return _Acquire()


@pytest.fixture(autouse=True)
def overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_STATUS_FILE", str(tmp_path / "missing.json"))
    app.dependency_overrides[get_db_pool] = lambda: _Pool()
    yield
    app.dependency_overrides.clear()


def _identity(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity("staff-1", "user-1", "Test User", role.value, role)


def test_ops_status_rejects_non_management() -> None:
    app.dependency_overrides[get_current_identity] = lambda: _identity(
        ClinicRole.RECEPTION
    )
    response = TestClient(app).get("/api/v1/ops/status")
    assert response.status_code == 403


def test_ops_status_allows_management_and_disables_cache() -> None:
    app.dependency_overrides[get_current_identity] = lambda: _identity(
        ClinicRole.MANAGEMENT
    )
    response = TestClient(app).get("/api/v1/ops/status")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["snapshot_state"] == "unknown"


def test_ops_status_requires_verified_identity() -> None:
    app.dependency_overrides[get_db_pool] = lambda: MagicMock()
    response = TestClient(app).get("/api/v1/ops/status")
    assert response.status_code == 401
