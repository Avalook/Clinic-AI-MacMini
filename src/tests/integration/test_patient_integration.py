import datetime
import os
from uuid import UUID

import asyncpg
import pytest
from dotenv import load_dotenv

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.schemas.patient import PatientCreateDTO, PatientUpdateDTO
from clinicai.services.patient_service import PatientService

# PatientService takes the caller now; the tenant rides on the identity.
identity = StaffIdentity(
    staff_id="s1",
    auth_user_id="u1",
    full_name="CSKH test",
    department="CSKH",
    role=ClinicRole.CSKH,
    clinic_id="a0000000-0000-4000-8000-000000000001",
    location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
    location_name="Kim Ngưu",
)

# Load environment variables from .env
load_dotenv()

# Skip all integration tests in this file if DATABASE_URL is not provided
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="no DB",
)


@pytest.mark.asyncio
async def test_create_and_fetch_round_trip(
    patient_service: PatientService, location_id: UUID, cleanup_patients: list[str]
) -> None:
    """Insert a new patient and retrieve by ID, ensuring fields match."""
    data = PatientCreateDTO(
        full_name="Nguyen Van A",
        date_of_birth=datetime.date(1990, 5, 20),
        phone_primary="+84901234567",
        national_id_number="012345678901",
        location_id=location_id,
        is_active=True,
    )
    result = await patient_service.create_patient(data, identity)
    assert not result.duplicate
    created = result.patient
    assert created is not None
    cleanup_patients.append(created.patient_code)

    assert created.clinic_patient_id is not None
    assert created.patient_code is not None
    assert created.full_name == "Nguyen Van A"
    assert created.phone_primary == "+84901234567"

    fetched = await patient_service.get_by_id(
        created.clinic_patient_id, "a0000000-0000-4000-8000-000000000001"
    )
    assert fetched is not None
    assert fetched.clinic_patient_id == created.clinic_patient_id
    assert fetched.patient_code == created.patient_code
    assert fetched.full_name == created.full_name
    assert fetched.phone_primary == created.phone_primary


@pytest.mark.asyncio
async def test_get_by_phone_returns_created(
    patient_service: PatientService, location_id: UUID, cleanup_patients: list[str]
) -> None:
    """Create a patient, search by phone primary, and check matching record."""
    phone = "+84901234568"
    data = PatientCreateDTO(
        full_name="Nguyen Van B",
        date_of_birth=datetime.date(1991, 6, 21),
        phone_primary=phone,
        location_id=location_id,
        is_active=True,
    )
    created = (await patient_service.create_patient(data, identity)).patient
    assert created is not None
    cleanup_patients.append(created.patient_code)

    results = await patient_service.get_by_phone(
        phone, "a0000000-0000-4000-8000-000000000001"
    )
    assert len(results) >= 1

    matched = [p for p in results if p.clinic_patient_id == created.clinic_patient_id]
    assert len(matched) == 1
    assert matched[0].full_name == "Nguyen Van B"


@pytest.mark.asyncio
async def test_update_patient_persists(
    patient_service: PatientService, location_id: UUID, cleanup_patients: list[str]
) -> None:
    """Create patient, update name, and assert persistent changes."""
    data = PatientCreateDTO(
        full_name="Nguyen Van C",
        date_of_birth=datetime.date(1992, 7, 22),
        phone_primary="+84901234569",
        location_id=location_id,
        is_active=True,
    )
    created = (await patient_service.create_patient(data, identity)).patient
    assert created is not None
    cleanup_patients.append(created.patient_code)

    update_data = PatientUpdateDTO(full_name="Nguyen Van C Updated")
    updated = await patient_service.update_patient(
        created.clinic_patient_id, update_data, identity
    )
    assert updated.full_name == "Nguyen Van C Updated"

    fetched = await patient_service.get_by_id(
        created.clinic_patient_id, "a0000000-0000-4000-8000-000000000001"
    )
    assert fetched is not None
    assert fetched.full_name == "Nguyen Van C Updated"


@pytest.mark.asyncio
async def test_duplicate_phone_triggers_mpi_queue(
    patient_service: PatientService,
    location_id: UUID,
    cleanup_patients: list[str],
    db_pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create patient A, then patient B with same primary phone number.

    Expect that matching MPI is identified and entry queued in mpi_merge_queue.
    """
    # Lower threshold to 50.0 so phone primary match (50 pts) triggers queueing
    import clinicai.services.mpi_service

    monkeypatch.setattr(clinicai.services.mpi_service, "MPI_THRESHOLD", 50.0)

    phone = "+84909999999"

    # Insert Patient A
    data_a = PatientCreateDTO(
        full_name="Patient A",
        date_of_birth=datetime.date(1985, 1, 1),
        phone_primary=phone,
        location_id=location_id,
        is_active=True,
    )
    patient_a = (await patient_service.create_patient(data_a, identity)).patient
    assert patient_a is not None
    cleanup_patients.append(patient_a.patient_code)

    # Insert Patient B. The same phone is a SOFT block: without force=True the
    # service returns duplicate matches and inserts nothing, so there would be
    # no second patient for MPI to compare against.
    data_b = PatientCreateDTO(
        full_name="Patient B",
        date_of_birth=datetime.date(1986, 2, 2),
        phone_primary=phone,
        location_id=location_id,
        is_active=True,
        force=True,
    )
    patient_b = (await patient_service.create_patient(data_b, identity)).patient
    assert patient_b is not None
    cleanup_patients.append(patient_b.patient_code)

    # Verify that a row exists in mpi_merge_queue referencing B's ID with PENDING status
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM mpi_merge_queue
            WHERE patient_id_a = $1 OR patient_id_b = $1;
            """,
            patient_b.clinic_patient_id,
        )

    assert len(rows) >= 1
    assert any(row["status"] == "PENDING" for row in rows)


@pytest.mark.asyncio
async def test_cannot_duplicate_national_id(
    patient_service: PatientService, location_id: UUID, cleanup_patients: list[str]
) -> None:
    """A second patient with the same CCCD is a hard conflict, not a soft one."""
    national_id = "123456789012"

    # Insert Patient A
    data_a = PatientCreateDTO(
        full_name="Patient A",
        date_of_birth=datetime.date(1980, 1, 1),
        phone_primary="+84901111111",
        national_id_number=national_id,
        location_id=location_id,
        is_active=True,
    )
    patient_a = (await patient_service.create_patient(data_a, identity)).patient
    assert patient_a is not None
    cleanup_patients.append(patient_a.patient_code)

    # Insert Patient B with the same national ID
    data_b = PatientCreateDTO(
        full_name="Patient B",
        date_of_birth=datetime.date(1981, 2, 2),
        phone_primary="+84902222222",
        national_id_number=national_id,
        location_id=location_id,
        is_active=True,
    )

    with pytest.raises(ConflictError) as exc_info:
        await patient_service.create_patient(data_b, identity)

    assert "CCCD này đã có hồ sơ" in str(exc_info.value)
