"""CP6–4c HTTP smoke: /clinical/{visit}/amend và /release qua FastAPI TestClient.

KHÔNG gọi service trực tiếp; gọi HTTP endpoint qua TestClient để đảm bảo:
  1. Router schema (AmendRequest, ReleaseRequest) parse đúng
  2. Guard RBAC chặn vai trò sai
  3. expected_revision / expected_amendment_id đi tới service đầy đủ
  4. Exception handler trả đúng status code (409, 422, 403)
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from tests.services.fake_sql import SqlConn, pool

CLINIC = "00000000-aaaa-4000-8000-000000000001"
VISIT = str(uuid4())
ME = str(uuid4())
OTHER_DOC = str(uuid4())

# ── helpers ───────────────────────────────────────────────────────────────


def who(role: ClinicRole = ClinicRole.DOCTOR, staff: str = ME) -> StaffIdentity:
    return StaffIdentity(
        auth_user_id=staff,
        clinic_id=CLINIC,
        staff_id=staff,
        full_name="BS Test",
        department=role.value,
        role=role,
        location_id=CLINIC,
        location_name="CS",
    )


def _trang_thai(state: str, **kw: Any) -> dict[str, Any]:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return {
        "visit_id": VISIT,
        "patient_name": "Nguyễn Thị A",
        "patient_code": "BN1",
        "clinical_state": "AMENDED"
        if state == "AMENDED"
        else ("SIGNED" if state in ("SIGNED", "RELEASED") else state),
        "version": 1,
        "record_revision": 1,
        "finalized_at": now if state in ("SIGNED", "RELEASED", "AMENDED") else None,
        "signed_by_name": "BS",
        "released_at": now if state == "RELEASED" else None,
        "released_by_name": "BS" if state == "RELEASED" else None,
        "has_active_release": state == "RELEASED",
        "attending_doctor_id": ME,
        "last_amendment_id": "00000000-1111-4000-8000-000000000001"
        if state == "AMENDED"
        else None,
        "last_amended_at": now if state == "AMENDED" else None,
        "soap_subjective": '{"s": "ok"}',
        "soap_objective": '{"o": "ok"}',
        "soap_assessment": '{"a": "ok"}',
        "soap_plan": '{"p": "ok"}',
        **kw,
    }


def _as(role: ClinicRole, staff: str = ME) -> None:
    app.dependency_overrides[get_current_identity] = lambda: who(role, staff)


def _pool(*rules: tuple[str, Any]) -> SqlConn:
    return pool(*rules)


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


# ── amend route tests ────────────────────────────────────────────────────


def test_amend_route_returns_201_on_success() -> None:
    """POST /clinical/{visit}/amend: SOAP-only with valid revision → 201."""
    _as(ClinicRole.DOCTOR)
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("SIGNED")),
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status",
            {
                "status": "FINALIZED",
                "attending_doctor_id": ME,
                "record_revision": 1,
                "was_released": False,
            },
        ),
        ("SELECT revision FROM", 1),
        ("INSERT INTO public.visit_amendment", "OK"),
        ("UPDATE public.clinical_record", "OK"),
        ("INSERT INTO public.event_log", "OK"),
    )
    app.dependency_overrides[get_db_pool] = lambda: p
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/amend",
        json={
            "reason": "test",
            "corrected": {"soap_plan": {"p": "x"}},
            "expected_revision": 1,
        },
    )
    assert r.status_code == 201
    assert r.json()["ok"] is True


def test_amend_route_ultrasound_doctor_gets_403() -> None:
    """POST /clinical/{visit}/amend: ULTRASOUND_DOCTOR → 403."""
    _as(ClinicRole.ULTRASOUND_DOCTOR)
    app.dependency_overrides[get_db_pool] = lambda: _pool()
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/amend",
        json={
            "reason": "test",
            "corrected": {"soap_plan": {"p": "x"}},
            "expected_revision": 1,
        },
    )
    assert r.status_code == 403


def test_amend_route_missing_expected_revision_gets_422() -> None:
    """POST /clinical/{visit}/amend: missing expected_revision → 422."""
    _as(ClinicRole.DOCTOR)
    app.dependency_overrides[get_db_pool] = lambda: _pool()
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/amend",
        json={
            "reason": "test",
            "corrected": {"soap_plan": {"p": "x"}},
            # no expected_revision
        },
    )
    assert r.status_code == 422


# ── release route tests ──────────────────────────────────────────────────


def test_release_route_returns_201_on_success() -> None:
    """POST /clinical/{visit}/release: SIGNED state → 201."""
    _as(ClinicRole.DOCTOR)
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("SIGNED")),
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status",
            {
                "status": "FINALIZED",
                "attending_doctor_id": ME,
                "active_release": False,
                "latest_amendment_id": None,
            },
        ),
        ("INSERT INTO public.clinical_release", "OK"),
        ("INSERT INTO public.event_log", "OK"),
    )
    app.dependency_overrides[get_db_pool] = lambda: p
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/release",
        json={"note": "ok"},
    )
    assert r.status_code == 201
    assert r.json()["state"] == "RELEASED"


def test_release_route_ultrasound_doctor_gets_403() -> None:
    """POST /clinical/{visit}/release: ULTRASOUND_DOCTOR → 403."""
    _as(ClinicRole.ULTRASOUND_DOCTOR)
    app.dependency_overrides[get_db_pool] = lambda: _pool()
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/release",
        json={},
    )
    assert r.status_code == 403


def test_release_route_other_doctor_gets_403() -> None:
    """POST /clinical/{visit}/release: Doctor but not attending → 403."""
    _as(ClinicRole.DOCTOR, staff=OTHER_DOC)
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("SIGNED")),
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status",
            {
                "status": "FINALIZED",
                "attending_doctor_id": ME,  # attending is ME, not OTHER_DOC
                "active_release": False,
                "latest_amendment_id": None,
            },
        ),
    )
    app.dependency_overrides[get_db_pool] = lambda: p
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/release",
        json={},
    )
    # SafetyGateError → 403
    assert r.status_code == 403


def test_release_route_amended_stale_amendment_gets_409() -> None:
    """POST /clinical/{visit}/release: stale expected_amendment_id → 409."""
    _as(ClinicRole.DOCTOR)
    latest_amend = str(uuid4())
    stale_amend = str(uuid4())
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("AMENDED")),
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status",
            {
                "status": "FINALIZED",
                "attending_doctor_id": ME,
                "active_release": False,
                "latest_amendment_id": latest_amend,
            },
        ),
    )
    app.dependency_overrides[get_db_pool] = lambda: p
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/release",
        json={"expected_amendment_id": stale_amend},
    )
    assert r.status_code == 409


def test_release_route_amended_correct_amendment_gets_201() -> None:
    """POST /clinical/{visit}/release: correct expected_amendment_id → 201."""
    _as(ClinicRole.DOCTOR)
    amend_id = str(uuid4())
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("AMENDED")),
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status",
            {
                "status": "FINALIZED",
                "attending_doctor_id": ME,
                "active_release": False,
                "latest_amendment_id": amend_id,
            },
        ),
        ("INSERT INTO public.clinical_release", "OK"),
        ("INSERT INTO public.event_log", "OK"),
    )
    app.dependency_overrides[get_db_pool] = lambda: p
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/release",
        json={"expected_amendment_id": amend_id},
    )
    assert r.status_code == 201
    assert r.json()["state"] == "RELEASED"


def test_release_route_reception_cannot_release() -> None:
    """POST /clinical/{visit}/release: RECEPTION → 403."""
    _as(ClinicRole.RECEPTION)
    app.dependency_overrides[get_db_pool] = lambda: _pool()
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/release",
        json={},
    )
    assert r.status_code == 403


def test_release_route_null_attending_doctor_gets_403() -> None:
    """POST /clinical/{visit}/release: attending_doctor_id NULL → 403."""
    _as(ClinicRole.DOCTOR)
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("SIGNED")),
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status",
            {
                "status": "FINALIZED",
                "attending_doctor_id": None,
                "active_release": False,
                "latest_amendment_id": None,
            },
        ),
    )
    app.dependency_overrides[get_db_pool] = lambda: p
    c = TestClient(app)
    r = c.post(
        f"/api/v1/clinical/{VISIT}/release",
        json={},
    )
    assert r.status_code == 403
    assert "bác sĩ chính" in r.json().get("message", "")
