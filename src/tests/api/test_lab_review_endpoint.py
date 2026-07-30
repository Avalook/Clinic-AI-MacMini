"""Authorization and patient-boundary tests for lab doctor review."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app

CLINIC_ID = UUID("a0000000-0000-4000-8000-000000000001")
PATIENT_ID = uuid4()
LAB_RESULT_ID = uuid4()
STAFF_ID = uuid4()
NOW = datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc)


def _identity(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id=str(STAFF_ID),
        auth_user_id=str(uuid4()),
        full_name="Nhân viên Test",
        department=role.value,
        role=role,
        clinic_id=str(CLINIC_ID),
    )


def _pool_with(rows: list[dict[str, object] | None]) -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow.side_effect = rows
    conn.transaction = MagicMock(return_value=AsyncMock())
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_lab_review_is_doctor_only(client: TestClient) -> None:
    app.dependency_overrides[get_current_identity] = lambda: _identity(
        ClinicRole.RECEPTION
    )
    app.dependency_overrides[get_db_pool] = lambda: MagicMock()

    response = client.post(
        f"/api/v1/lab/results/{LAB_RESULT_ID}/review",
        json={"clinic_patient_id": str(PATIENT_ID)},
    )

    assert response.status_code == 403


def test_lab_review_finalizes_scoped_result_and_returns_audit_state(
    client: TestClient,
) -> None:
    pending = {
        "lab_result_id": LAB_RESULT_ID,
        "clinic_patient_id": PATIENT_ID,
        "triage_group": "GROUP_B",
        "requires_doctor_review": True,
        "is_finalized": False,
        "reviewed_by_staff_id": None,
        "reviewed_at": None,
        "has_result": True,
    }
    finalized = {
        **pending,
        "is_finalized": True,
        "reviewed_by_staff_id": STAFF_ID,
        "reviewed_at": NOW,
    }
    pool = _pool_with([pending, finalized])
    app.dependency_overrides[get_current_identity] = lambda: _identity(
        ClinicRole.DOCTOR
    )
    app.dependency_overrides[get_db_pool] = lambda: pool

    response = client.post(
        f"/api/v1/lab/results/{LAB_RESULT_ID}/review",
        json={"clinic_patient_id": str(PATIENT_ID)},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "lab_result_id": str(LAB_RESULT_ID),
        "clinic_patient_id": str(PATIENT_ID),
        "triage_group": "GROUP_B",
        "is_finalized": True,
        "reviewed_by_staff_id": str(STAFF_ID),
        "reviewed_at": NOW.isoformat().replace("+00:00", "Z"),
        "already_finalized": False,
    }


def test_lab_review_wrong_patient_is_not_found(client: TestClient) -> None:
    pool = _pool_with([None])
    app.dependency_overrides[get_current_identity] = lambda: _identity(
        ClinicRole.DOCTOR
    )
    app.dependency_overrides[get_db_pool] = lambda: pool

    response = client.post(
        f"/api/v1/lab/results/{LAB_RESULT_ID}/review",
        json={"clinic_patient_id": str(PATIENT_ID)},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "NOT_FOUND"
