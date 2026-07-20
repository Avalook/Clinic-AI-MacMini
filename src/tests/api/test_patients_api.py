import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import ResourceNotFoundError
from clinicai.main import app
from clinicai.schemas.patient import DuplicateMatch, PatientCreateResult, PatientDTO


@pytest.fixture(autouse=True)
def override_db():
    """Fixture that overrides database dependency globally for unit tests."""
    app.dependency_overrides[get_db_pool] = lambda: MagicMock()
    app.dependency_overrides[get_current_identity] = lambda: StaffIdentity(
        staff_id="staff-1",
        auth_user_id="user-1",
        full_name="Reception A",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    """Fixture providing a TestClient instance for the FastAPI application."""
    return TestClient(app)


@patch("clinicai.api.v1.patients.PatientService")
def test_create_patient_requires_verified_staff(mock_service_class, client) -> None:
    """A shared API key without a verified staff JWT must never create PII."""
    app.dependency_overrides.pop(get_current_identity, None)
    mock_service_class.return_value.create_patient = AsyncMock()

    response = client.post(
        "/api/v1/patients",
        json={
            "full_name": "Nguyen Van A",
            "location_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 401
    mock_service_class.return_value.create_patient.assert_not_awaited()


@patch("clinicai.api.v1.patients.PatientService")
def test_create_patient_returns_201(mock_service_class, client) -> None:
    """POST /api/v1/patients returns 201 Created and the created PatientDTO."""
    mock_service = mock_service_class.return_value

    patient_id = uuid.uuid4()
    loc_id = uuid.uuid4()
    mock_dto = PatientDTO(
        clinic_patient_id=patient_id,
        patient_code="BN-2026-123456",
        national_id_number="012345678901",
        full_name="Nguyen Van A",
        date_of_birth=datetime.date(1990, 1, 1),
        phone_primary="+84901234567",
        location_id=loc_id,
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    mock_service.create_patient = AsyncMock(
        return_value=PatientCreateResult(patient=mock_dto)
    )

    payload = {
        "full_name": "Nguyen Van A",
        "date_of_birth": "1990-01-01",
        "phone_primary": "0901234567",
        "national_id_number": "012345678901",
        "location_id": str(loc_id),
        "is_active": True,
    }

    response = client.post("/api/v1/patients", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["clinic_patient_id"] == str(patient_id)
    assert data["full_name"] == "Nguyen Van A"
    assert data["national_id_number"] == "012*******01"  # Masked!

    mock_service.create_patient.assert_called_once()
    args, _ = mock_service.create_patient.call_args
    assert args[0].full_name == "Nguyen Van A"
    assert args[0].phone_primary == "0901234567"


@patch("clinicai.api.v1.patients.PatientService")
def test_create_patient_phone_duplicate_returns_200(mock_service_class, client) -> None:
    """Phone already on file (no force) → 200 {duplicate, matches}, no insert."""
    mock_service = mock_service_class.return_value
    existing_id = uuid.uuid4()
    mock_service.create_patient = AsyncMock(
        return_value=PatientCreateResult(
            duplicate=True,
            matches=[
                DuplicateMatch(
                    clinic_patient_id=existing_id,
                    patient_code="BN-2026-000001",
                    full_name="Nguyen Thi Lan",
                    date_of_birth=datetime.date(1990, 3, 15),
                )
            ],
        )
    )

    payload = {
        "full_name": "Nguyen Thi Lan",
        "phone_primary": "0901234567",
        "location_id": str(uuid.uuid4()),
    }
    response = client.post("/api/v1/patients", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["duplicate"] is True
    assert len(data["matches"]) == 1
    assert data["matches"][0]["clinic_patient_id"] == str(existing_id)
    assert data["matches"][0]["patient_code"] == "BN-2026-000001"


@patch("clinicai.api.v1.patients.PatientService")
def test_create_patient_cccd_conflict_returns_409(mock_service_class, client) -> None:
    """Duplicate CCCD raises ConflictError → 409 with friendly message."""
    mock_service = mock_service_class.return_value
    mock_service.create_patient = AsyncMock(
        side_effect=ConflictError("CCCD này đã có hồ sơ (BN-2026-000001 · Lan).")
    )

    payload = {
        "full_name": "Nguyen Thi Lan",
        "national_id_number": "012345678901",
        "location_id": str(uuid.uuid4()),
    }
    response = client.post("/api/v1/patients", json=payload)
    assert response.status_code == 409

    data = response.json()
    assert data["error"] == "CONFLICT_ERROR"
    assert "CCCD" in data["message"]


@patch("clinicai.api.v1.patients.PatientService")
def test_get_patient_by_id_returns_200(mock_service_class, client) -> None:
    """GET /api/v1/patients/{id} returns 200 OK and the PatientDTO."""
    mock_service = mock_service_class.return_value

    patient_id = uuid.uuid4()
    loc_id = uuid.uuid4()
    mock_dto = PatientDTO(
        clinic_patient_id=patient_id,
        patient_code="BN-2026-123456",
        national_id_number="012345678901",
        full_name="Nguyen Van A",
        date_of_birth=datetime.date(1990, 1, 1),
        phone_primary="+84901234567",
        location_id=loc_id,
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    mock_service.get_by_id = AsyncMock(return_value=mock_dto)

    response = client.get(f"/api/v1/patients/{patient_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["clinic_patient_id"] == str(patient_id)
    assert data["full_name"] == "Nguyen Van A"

    mock_service.get_by_id.assert_called_once_with(patient_id)


@patch("clinicai.api.v1.patients.PatientService")
def test_get_patient_not_found_returns_404(mock_service_class, client) -> None:
    """GET /api/v1/patients/{id} returns 404 NOT FOUND if resource is absent."""
    mock_service = mock_service_class.return_value
    mock_service.get_by_id = AsyncMock(return_value=None)

    patient_id = uuid.uuid4()
    response = client.get(f"/api/v1/patients/{patient_id}")
    assert response.status_code == 404

    data = response.json()
    assert data["error"] == "NOT_FOUND"
    assert "not found" in data["message"]

    mock_service.get_by_id.assert_called_once_with(patient_id)


@patch("clinicai.api.v1.patients.PatientService")
def test_get_by_phone_returns_list(mock_service_class, client) -> None:
    """GET /api/v1/patients?phone=... returns 200 OK and a list of PatientDTOs."""
    mock_service = mock_service_class.return_value

    patient_id = uuid.uuid4()
    loc_id = uuid.uuid4()
    mock_dto = PatientDTO(
        clinic_patient_id=patient_id,
        patient_code="BN-2026-123456",
        national_id_number="012345678901",
        full_name="Nguyen Van A",
        date_of_birth=datetime.date(1990, 1, 1),
        phone_primary="+84901234567",
        location_id=loc_id,
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    mock_service.get_by_phone = AsyncMock(return_value=[mock_dto])

    response = client.get("/api/v1/patients", params={"phone": "+84901234567"})
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["clinic_patient_id"] == str(patient_id)
    assert data[0]["phone_primary"] == "+84901234567"

    mock_service.get_by_phone.assert_called_once_with("+84901234567")


@patch("clinicai.api.v1.patients.PatientService")
def test_check_phone_exists_returns_minimal_matches(mock_service_class, client) -> None:
    """GET /api/v1/patients/check-phone → {exists, matches} with lean fields."""
    mock_service = mock_service_class.return_value
    mock_service.find_phone_duplicates = AsyncMock(
        return_value=[
            {
                "full_name": "Nguyen Thi Lan",
                "patient_code": "BN-2026-000001",
                "birth_year": 1990,
            }
        ]
    )

    response = client.get(
        "/api/v1/patients/check-phone", params={"phone": "0901234567"}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["exists"] is True
    assert len(data["matches"]) == 1
    match = data["matches"][0]
    assert match == {
        "full_name": "Nguyen Thi Lan",
        "patient_code": "BN-2026-000001",
        "birth_year": 1990,
    }
    # Route resolves to check-phone, NOT get_patient_by_id (UUID route).
    mock_service.find_phone_duplicates.assert_awaited_once_with("0901234567")


@patch("clinicai.api.v1.patients.PatientService")
def test_check_phone_absent_returns_exists_false(mock_service_class, client) -> None:
    """No match → exists=false, empty matches."""
    mock_service = mock_service_class.return_value
    mock_service.find_phone_duplicates = AsyncMock(return_value=[])

    response = client.get(
        "/api/v1/patients/check-phone", params={"phone": "0999999999"}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["exists"] is False
    assert data["matches"] == []


@patch("clinicai.api.v1.patients.PatientService")
def test_update_patient_returns_200(mock_service_class, client) -> None:
    """PATCH /api/v1/patients/{id} returns 200 OK and the updated PatientDTO."""
    mock_service = mock_service_class.return_value

    patient_id = uuid.uuid4()
    loc_id = uuid.uuid4()
    updated_dto = PatientDTO(
        clinic_patient_id=patient_id,
        patient_code="BN-2026-123456",
        national_id_number="012345678901",
        full_name="Nguyen Van A Updated",
        date_of_birth=datetime.date(1990, 1, 1),
        phone_primary="+84901234567",
        location_id=loc_id,
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    mock_service.update_patient = AsyncMock(return_value=updated_dto)

    payload = {"full_name": "Nguyen Van A Updated"}
    response = client.patch(f"/api/v1/patients/{patient_id}", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["clinic_patient_id"] == str(patient_id)
    assert data["full_name"] == "Nguyen Van A Updated"

    mock_service.update_patient.assert_called_once()
    args, _ = mock_service.update_patient.call_args
    assert args[0] == patient_id
    assert args[1].full_name == "Nguyen Van A Updated"


@patch("clinicai.api.v1.patients.PatientService")
def test_update_patient_not_found_returns_404(mock_service_class, client) -> None:
    """PATCH /api/v1/patients/{id} returns 404 if ResourceNotFoundError is raised."""
    mock_service = mock_service_class.return_value
    mock_service.update_patient = AsyncMock(
        side_effect=ResourceNotFoundError("Patient not found")
    )

    patient_id = uuid.uuid4()
    payload = {"full_name": "Nguyen Van A Updated"}
    response = client.patch(f"/api/v1/patients/{patient_id}", json=payload)
    assert response.status_code == 404

    data = response.json()
    assert data["error"] == "NOT_FOUND"
    assert "not found" in data["message"]

    mock_service.update_patient.assert_called_once()
