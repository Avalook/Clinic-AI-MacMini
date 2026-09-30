"""Authorization and response tests for the MANAGEMENT-only Ops endpoint."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app


class _Acquire:
    async def __aenter__(self) -> "_Acquire":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def fetchval(self, _query: str) -> int:
        return 1


class _Pool:
    def acquire(self) -> _Acquire:
        return _Acquire()


@pytest.fixture(autouse=True)
def overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("OPS_STATUS_FILE", str(tmp_path / "missing.json"))
    # Lego 20 (25/09/2026): cửa hỏi QUYỀN ops.view — pool giả trả lời theo nhóm mẫu.
    from tests.quyen_gia import cua_router_theo_nhom_mau

    cua_router_theo_nhom_mau(monkeypatch)
    app.dependency_overrides[get_db_pool] = lambda: _Pool()
    yield
    app.dependency_overrides.clear()


def _identity(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        "staff-1",
        "user-1",
        "Test User",
        role.value,
        role,
        "a0000000-0000-4000-8000-000000000001",
        "fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        "Kim Ngưu",
    )


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


def test_ops_traffic_khong_dang_nhap_thi_bi_chan() -> None:
    """30/09/2026: /ops/traffic từng mở cho cả Internet (admin/12345678). Không
    có khoá dịch vụ + danh tính nhân viên thì bị chặn, kể cả đúng mật khẩu."""
    client = TestClient(app)
    for mat_khau in ("wrongpassword", "12345678"):
        response = client.post(
            "/api/v1/ops/traffic",
            json={"username": "admin", "password": mat_khau},
        )
        assert response.status_code in (401, 403)
