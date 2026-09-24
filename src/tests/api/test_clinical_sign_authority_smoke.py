"""Ký qua HTTP sau CORE-A (23/09/2026).

KHÔNG CÒN "KÝ BỆNH ÁN": mốc khoá hồ sơ là Hoàn tất khám (kiểm ở
`test_hoan_tat_khoa_ho_so_db.py`). Endpoint /clinical/{visit}/sign trả 410
với MỌI vai, không ghi gì — kể cả bác sĩ chính.

Ký kết quả SIÊU ÂM là chuyện khác (kết quả, không phải bệnh án) — vẫn còn.
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


def _locked(
    status: str = "OPEN",
    attending: str | None = ATTENDING_DOC,
    rev: int = 2,
    **kw: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": status,
        "attending_doctor_id": attending,
        "current_revision": rev,
        "soap_subjective": '{"s": "khám"}',
        "soap_objective": '{"o": "ổn"}',
        "soap_assessment": '{"a": "viêm"}',
        "soap_plan": '{"p": "theo dõi"}',
        "chief_complaint_at_visit": None,
        "phieu_chuyen_khoa": None,
        "co_sinh_hieu": False,
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


# ── Ký bệnh án đã nghỉ: 410 cho mọi vai, không chạm database ──────────────────
@pytest.mark.parametrize(
    ("role", "staff"),
    [
        (ClinicRole.DOCTOR, ATTENDING_DOC),
        (ClinicRole.DOCTOR, OTHER_DOC),
        (ClinicRole.ULTRASOUND_DOCTOR, US_DOC),
    ],
)
def test_ky_benh_an_da_nghi_tra_410(role: ClinicRole, staff: str) -> None:
    _as(role, staff)
    app.dependency_overrides[get_db_pool] = lambda: _pool()
    res = TestClient(app).post(
        f"/api/v1/clinical/{VISIT}/sign", json={"expected_revision": 2}
    )
    assert res.status_code == 410
    assert "Hoàn tất khám" in res.text


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
