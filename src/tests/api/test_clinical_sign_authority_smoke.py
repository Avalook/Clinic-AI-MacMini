"""Tests kiểm tra quyền ký bệnh án và ràng buộc expected_revision.
(Final Pre-prod Audit)

9 TEST BẮT BUỘC:
1. DOCTOR chính + current revision => ký thành công
2. DOCTOR khác + current revision => 403
3. attending_doctor_id NULL => 403
4. ULTRASOUND_DOCTOR gọi /clinical/{visit}/sign => 403
5. ULTRASOUND_DOCTOR vẫn ký endpoint ultrasound của chính mình được
6. thiếu expected_revision => 422
7. stale expected_revision => 409
8. race: revision thay đổi trước câu ký => không ký
9. các test Ký → Khám xong → Thu ngân vẫn xanh
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
ATTENDING_DOC = str(uuid4())
OTHER_DOC = str(uuid4())
US_DOC = str(uuid4())
ULTRASOUND_ID = str(uuid4())


def who(role: ClinicRole, staff_id: str) -> StaffIdentity:
    return StaffIdentity(
        auth_user_id=staff_id,
        clinic_id=CLINIC,
        staff_id=staff_id,
        full_name=f"User {role.value}",
        department=role.value,
        role=role,
        location_id=CLINIC,
        location_name="Phòng khám",
    )


def _trang_thai(state: str = "DRAFT", **kw: Any) -> dict[str, Any]:
    base = {
        "visit_id": VISIT,
        "patient_name": "Bệnh Nhân Test",
        "patient_code": "BN001",
        "clinical_state": state,
        "version": 1,
        "record_revision": 2,
        "finalized_at": None,
        "signed_by_name": None,
        "released_at": None,
        "released_by_name": None,
        "last_amended_at": None,
        "soap_subjective": '{"s": "khám"}',
        "soap_objective": '{"o": "ổn"}',
        "soap_assessment": '{"a": "viêm"}',
        "soap_plan": '{"p": "theo dõi"}',
    }
    base.update(kw)
    return base


def _as(role: ClinicRole, staff_id: str) -> None:
    app.dependency_overrides[get_current_identity] = lambda: who(role, staff_id)


def _pool(*rules: tuple[str, Any]) -> SqlConn:
    return pool(*rules)


@pytest.fixture(autouse=True)
def _clean_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


# ── 1. DOCTOR chính + current revision => ký thành công ───────────────────────
def test_1_attending_doctor_signs_successfully() -> None:
    _as(ClinicRole.DOCTOR, ATTENDING_DOC)
    locked_row = {
        "status": "DRAFT",
        "attending_doctor_id": ATTENDING_DOC,
        "current_revision": 2,
    }
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("DRAFT")),
        ("SELECT visit_id FROM public.visit", VISIT),
        ("FROM public.visit v", locked_row),
        ("UPDATE public.visit", VISIT),
    )
    app.dependency_overrides[get_db_pool] = lambda: p

    client = TestClient(app)
    res = client.post(f"/api/v1/clinical/{VISIT}/sign", json={"expected_revision": 2})
    assert res.status_code == 201
    assert res.json() == {"ok": True, "state": "SIGNED"}


# ── 2. DOCTOR khác + current revision => 403 ─────────────────────────────────
def test_2_other_doctor_cannot_sign_403() -> None:
    _as(ClinicRole.DOCTOR, OTHER_DOC)
    locked_row = {
        "status": "DRAFT",
        "attending_doctor_id": ATTENDING_DOC,
        "current_revision": 2,
    }
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("DRAFT")),
        ("SELECT visit_id FROM public.visit", VISIT),
        ("FROM public.visit v", locked_row),
    )
    app.dependency_overrides[get_db_pool] = lambda: p

    client = TestClient(app)
    res = client.post(f"/api/v1/clinical/{VISIT}/sign", json={"expected_revision": 2})
    assert res.status_code == 403
    assert "bác sĩ khác" in res.json().get("message", "")


# ── 3. attending_doctor_id NULL => 403 ───────────────────────────────────────
def test_3_null_attending_doctor_cannot_sign_403() -> None:
    _as(ClinicRole.DOCTOR, ATTENDING_DOC)
    locked_row = {
        "status": "DRAFT",
        "attending_doctor_id": None,
        "current_revision": 2,
    }
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("DRAFT")),
        ("SELECT visit_id FROM public.visit", VISIT),
        ("FROM public.visit v", locked_row),
    )
    app.dependency_overrides[get_db_pool] = lambda: p

    client = TestClient(app)
    res = client.post(f"/api/v1/clinical/{VISIT}/sign", json={"expected_revision": 2})
    assert res.status_code == 403
    assert "chưa có bác sĩ chính" in res.json().get("message", "")


# ── 4. ULTRASOUND_DOCTOR gọi /clinical/{visit}/sign => 403 ──────────────────
def test_4_ultrasound_doctor_cannot_sign_main_clinical_record_403() -> None:
    _as(ClinicRole.ULTRASOUND_DOCTOR, US_DOC)
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("DRAFT")),
    )
    app.dependency_overrides[get_db_pool] = lambda: p

    client = TestClient(app)
    res = client.post(f"/api/v1/clinical/{VISIT}/sign", json={"expected_revision": 2})
    assert res.status_code == 403


# ── 5. ULTRASOUND_DOCTOR vẫn ký endpoint ultrasound của chính mình được ───────
def test_5_ultrasound_doctor_can_sign_own_ultrasound() -> None:
    _as(ClinicRole.ULTRASOUND_DOCTOR, US_DOC)
    p = _pool(
        (
            "SELECT performed_by, signed_at FROM public.ultrasound_record",
            {"performed_by": US_DOC, "signed_at": None},
        ),
        (
            "UPDATE public.ultrasound_record",
            "OK",
        ),
    )
    app.dependency_overrides[get_db_pool] = lambda: p

    client = TestClient(app)
    res = client.post(f"/api/v1/clinical/ultrasound/{ULTRASOUND_ID}/sign")
    assert res.status_code == 201
    assert res.json() == {"ok": True, "signed": True}


# ── 6. thiếu expected_revision => 422 ─────────────────────────────────────────
def test_6_missing_expected_revision_422() -> None:
    _as(ClinicRole.DOCTOR, ATTENDING_DOC)
    app.dependency_overrides[get_db_pool] = lambda: _pool()

    client = TestClient(app)
    # Gửi body trống
    res = client.post(f"/api/v1/clinical/{VISIT}/sign", json={})
    assert res.status_code == 422

    # Không gửi body
    res2 = client.post(f"/api/v1/clinical/{VISIT}/sign")
    assert res2.status_code == 422

    # Gửi expected_revision âm
    res3 = client.post(f"/api/v1/clinical/{VISIT}/sign", json={"expected_revision": -1})
    assert res3.status_code == 422


# ── 7. stale expected_revision => 409 ─────────────────────────────────────────
def test_7_stale_expected_revision_409() -> None:
    _as(ClinicRole.DOCTOR, ATTENDING_DOC)
    locked_row = {
        "status": "DRAFT",
        "attending_doctor_id": ATTENDING_DOC,
        "current_revision": 3,  # hiện tại trên DB là 3
    }
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("DRAFT", record_revision=3)),
        ("SELECT visit_id FROM public.visit", VISIT),
        ("FROM public.visit v", locked_row),
    )
    app.dependency_overrides[get_db_pool] = lambda: p

    client = TestClient(app)
    # Bác sĩ gửi expected_revision=2 (stale)
    res = client.post(f"/api/v1/clinical/{VISIT}/sign", json={"expected_revision": 2})
    assert res.status_code == 409
    assert "vừa được sửa" in res.json().get("message", "")


# ── 8. race: revision thay đổi trước câu ký => không ký (409) ─────────────────
def test_8_race_revision_changed_before_update_fails_closed_409() -> None:
    _as(ClinicRole.DOCTOR, ATTENDING_DOC)
    locked_row = {
        "status": "DRAFT",
        "attending_doctor_id": ATTENDING_DOC,
        "current_revision": 2,  # lúc đọc sau lock thấy 2
    }
    # Nhưng câu UPDATE trả về None (do subquery kiểm revision
    # trong UPDATE thấy không khớp vì concurrent commit)
    # và status = 'FINALIZED' trả về False (chưa bị ký bởi ai khác)
    p = _pool(
        ("FROM public.v_clinical_status", _trang_thai("DRAFT", record_revision=2)),
        ("SELECT visit_id FROM public.visit", VISIT),
        ("FROM public.visit v", locked_row),
        ("UPDATE public.visit", None),  # UPDATE matched 0 rows
        ("status = 'FINALIZED' FROM public.visit", False),
    )
    app.dependency_overrides[get_db_pool] = lambda: p

    client = TestClient(app)
    res = client.post(f"/api/v1/clinical/{VISIT}/sign", json={"expected_revision": 2})
    assert res.status_code == 409
    assert "vừa được sửa" in res.json().get("message", "")
