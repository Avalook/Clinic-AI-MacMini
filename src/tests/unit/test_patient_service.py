"""Unit tests for PatientService with mock asyncpg pool."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.schemas.patient import PatientCreateDTO, PatientUpdateDTO
from clinicai.services.patient_service import PatientService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_UUID = uuid4()
FAKE_LOCATION = uuid4()
FAKE_NOW = datetime.datetime(2026, 5, 20, 10, 0, 0, tzinfo=datetime.timezone.utc)


def _make_record(overrides: dict | None = None) -> dict:
    """Build a dict that looks like an asyncpg.Record for the patient table."""
    base = {
        "clinic_patient_id": FAKE_UUID,
        "patient_code": "BN-2026-000001",
        "national_id_number": None,
        "full_name": "Nguyễn Thị Lan",
        "date_of_birth": datetime.date(1990, 3, 15),
        "phone_primary": "+84901234567",
        "phone_secondary": None,
        "location_id": FAKE_LOCATION,
        "is_active": True,
        "created_at": FAKE_NOW,
        "updated_at": FAKE_NOW,
    }
    if overrides:
        base.update(overrides)
    return base


def _mock_pool_and_conn() -> tuple[MagicMock, AsyncMock]:
    """Return (pool, conn) with pool.acquire() wired as async ctx mgr."""
    pool = MagicMock()
    conn = AsyncMock()

    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx

    return pool, conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_patient_success() -> None:
    """create_patient should INSERT and return the new patient in the result."""
    pool, conn = _mock_pool_and_conn()
    record = _make_record()
    conn.fetchrow.return_value = record
    conn.fetch.return_value = []  # no phone duplicates → proceed to insert

    svc = PatientService(pool)
    result = await svc.create_patient(
        PatientCreateDTO(
            full_name="Nguyễn Thị Lan",
            date_of_birth=datetime.date(1990, 3, 15),
            phone_primary="0901234567",
            location_id=FAKE_LOCATION,
        )
    )

    assert result.duplicate is False
    assert result.patient is not None
    assert result.patient.clinic_patient_id == FAKE_UUID
    assert result.patient.full_name == "Nguyễn Thị Lan"
    assert result.patient.location_id == FAKE_LOCATION
    assert result.patient.is_active is True
    # national_id_number was None → stays None after masking
    assert result.patient.national_id_number is None

    # Verify INSERT was called once (no CCCD pre-check: national_id was None)
    conn.fetchrow.assert_awaited_once()
    sql_arg = conn.fetchrow.call_args[0][0]
    assert "INSERT INTO patient" in sql_arg


@pytest.mark.asyncio
async def test_create_patient_cccd_conflict_raises() -> None:
    """An existing CCCD → ConflictError, BEFORE any insert (force can't override)."""
    from clinicai.api.exceptions import ConflictError

    pool, conn = _mock_pool_and_conn()
    # CCCD pre-check fetchrow returns an existing row → conflict.
    conn.fetchrow.return_value = {
        "patient_code": "BN-2026-000001",
        "full_name": "Người Khác",
    }

    svc = PatientService(pool)
    with pytest.raises(ConflictError, match="CCCD"):
        await svc.create_patient(
            PatientCreateDTO(
                full_name="Nguyễn Thị Lan",
                national_id_number="012345678901",
                location_id=FAKE_LOCATION,
                force=True,  # force does NOT bypass a CCCD conflict
            )
        )


@pytest.mark.asyncio
async def test_create_patient_phone_duplicate_blocks() -> None:
    """Phone on file (no force) → duplicate result, no insert."""
    pool, conn = _mock_pool_and_conn()
    conn.fetch.return_value = [
        {
            "clinic_patient_id": FAKE_UUID,
            "patient_code": "BN-2026-000001",
            "full_name": "Nguyễn Thị Lan",
            "date_of_birth": datetime.date(1990, 3, 15),
        }
    ]

    svc = PatientService(pool)
    result = await svc.create_patient(
        PatientCreateDTO(
            full_name="Nguyễn Thị Lan",
            phone_primary="0901234567",
            location_id=FAKE_LOCATION,
        )
    )

    assert result.duplicate is True
    assert result.patient is None
    assert len(result.matches) == 1
    assert result.matches[0].patient_code == "BN-2026-000001"
    # No INSERT happened — fetchrow (the insert) was never awaited.
    conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_patient_force_bypasses_phone_duplicate() -> None:
    """force=True skips the phone soft-block and inserts anyway."""
    pool, conn = _mock_pool_and_conn()
    record = _make_record()
    conn.fetchrow.return_value = record
    # Even if a phone duplicate exists, force must not consult it.
    conn.fetch.return_value = [{"patient_code": "BN-OLD"}]

    svc = PatientService(pool)
    result = await svc.create_patient(
        PatientCreateDTO(
            full_name="Nguyễn Thị Lan",
            phone_primary="0901234567",
            location_id=FAKE_LOCATION,
            force=True,
        )
    )

    assert result.duplicate is False
    assert result.patient is not None
    sql_arg = conn.fetchrow.call_args[0][0]
    assert "INSERT INTO patient" in sql_arg


@pytest.mark.asyncio
async def test_create_patient_generates_patient_code() -> None:
    """patient_code should follow BN-YYYY-XXXXXX format."""
    pool, conn = _mock_pool_and_conn()
    record = _make_record()
    conn.fetchrow.return_value = record

    svc = PatientService(pool)
    with patch(
        "clinicai.services.patient_service._generate_patient_code",
        return_value="BN-2026-123456",
    ):
        await svc.create_patient(
            PatientCreateDTO(
                full_name="Trần Văn A",
                location_id=FAKE_LOCATION,
            )
        )

    # The generated code was passed as the first positional arg
    call_args = conn.fetchrow.call_args[0]
    assert call_args[1] == "BN-2026-123456"


@pytest.mark.asyncio
async def test_get_by_id_found() -> None:
    """get_by_id should return PatientDTO when patient exists."""
    pool, conn = _mock_pool_and_conn()
    record = _make_record({"national_id_number": "012345678901"})
    conn.fetchrow.return_value = record

    svc = PatientService(pool)
    dto = await svc.get_by_id(FAKE_UUID)

    assert dto is not None
    assert dto.clinic_patient_id == FAKE_UUID
    # Verify masking: "012345678901" → "012*******01"
    assert dto.national_id_number == "012*******01"

    conn.fetchrow.assert_awaited_once()
    sql_arg = conn.fetchrow.call_args[0][0]
    assert "clinic_patient_id" in sql_arg


@pytest.mark.asyncio
async def test_get_by_id_not_found() -> None:
    """get_by_id should return None when patient does not exist."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = None

    svc = PatientService(pool)
    result = await svc.get_by_id(uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_by_phone_returns_list() -> None:
    """get_by_phone should return a list of PatientDTO matches."""
    pool, conn = _mock_pool_and_conn()
    conn.fetch.return_value = [
        _make_record({"clinic_patient_id": uuid4()}),
        _make_record({"clinic_patient_id": uuid4()}),
    ]

    svc = PatientService(pool)
    results = await svc.get_by_phone("+84901234567")

    assert len(results) == 2
    assert all(r.phone_primary == "+84901234567" for r in results)

    conn.fetch.assert_awaited_once()
    sql_arg = conn.fetch.call_args[0][0]
    assert "phone_primary" in sql_arg


@pytest.mark.asyncio
async def test_get_by_phone_returns_empty() -> None:
    """get_by_phone should return empty list when no matches."""
    pool, conn = _mock_pool_and_conn()
    conn.fetch.return_value = []

    svc = PatientService(pool)
    results = await svc.get_by_phone("+84999999999")

    assert results == []


# ---------------------------------------------------------------------------
# find_phone_duplicates + phone normalisation (feedback #9)
# ---------------------------------------------------------------------------


def test_phone_variants_normalises_to_same_set() -> None:
    """0xxx, 84xxx, +84xxx and a bare subscriber all map to the SAME variants."""
    from clinicai.services.patient_service import _phone_variants

    expected = {"0901234567", "84901234567", "+84901234567"}
    assert set(_phone_variants("0901234567")) == expected
    assert set(_phone_variants("+84901234567")) == expected
    assert set(_phone_variants("84901234567")) == expected
    # Spaces / dashes are stripped before normalising.
    assert set(_phone_variants("090 123 4567")) == expected
    assert set(_phone_variants("901234567")) == expected
    # No digits → nothing to match.
    assert _phone_variants("") == []
    assert _phone_variants("abc") == []


@pytest.mark.asyncio
async def test_find_phone_duplicates_returns_minimal_fields() -> None:
    """find_phone_duplicates returns only full_name/patient_code/birth_year."""
    pool, conn = _mock_pool_and_conn()
    conn.fetch.return_value = [
        {
            "patient_code": "BN-2026-000001",
            "full_name": "Nguyễn Thị Lan",
            "birth_year": 1990,
        },
    ]

    svc = PatientService(pool)
    matches = await svc.find_phone_duplicates("0901234567")

    assert matches == [
        {
            "full_name": "Nguyễn Thị Lan",
            "patient_code": "BN-2026-000001",
            "birth_year": 1990,
        }
    ]
    # No CCCD / address leaked.
    assert "national_id_number" not in matches[0]
    assert "address" not in matches[0]

    # Queried with the normalised variant array (catches +84 vs 0).
    conn.fetch.assert_awaited_once()
    sql_arg, variants = conn.fetch.call_args[0]
    assert "= ANY($1::text[])" in sql_arg
    assert set(variants) == {"0901234567", "84901234567", "+84901234567"}


@pytest.mark.asyncio
async def test_find_phone_duplicates_empty_when_no_match() -> None:
    """No rows → empty list (exists=false upstream)."""
    pool, conn = _mock_pool_and_conn()
    conn.fetch.return_value = []

    svc = PatientService(pool)
    assert await svc.find_phone_duplicates("0987654321") == []


@pytest.mark.asyncio
async def test_find_phone_duplicates_skips_db_when_no_digits() -> None:
    """Blank/garbage input never touches the DB."""
    pool, conn = _mock_pool_and_conn()

    svc = PatientService(pool)
    assert await svc.find_phone_duplicates("   ") == []
    conn.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_patient_success() -> None:
    """update_patient should SET only provided fields and return updated DTO."""
    pool, conn = _mock_pool_and_conn()
    updated_record = _make_record({"full_name": "Lê Thị Hoa", "is_active": False})
    conn.fetchrow.return_value = updated_record

    svc = PatientService(pool)
    dto = await svc.update_patient(
        FAKE_UUID,
        PatientUpdateDTO(full_name="Lê Thị Hoa", is_active=False),
    )

    assert dto.full_name == "Lê Thị Hoa"

    conn.fetchrow.assert_awaited_once()
    sql_arg = conn.fetchrow.call_args[0][0]
    assert "UPDATE patient SET" in sql_arg
    assert "full_name" in sql_arg
    assert "is_active" in sql_arg
    assert "RETURNING" in sql_arg


@pytest.mark.asyncio
async def test_update_patient_not_found() -> None:
    """update_patient should raise ResourceNotFoundError if row missing."""
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = None

    svc = PatientService(pool)
    missing_id = uuid4()

    with pytest.raises(ResourceNotFoundError, match=str(missing_id)):
        await svc.update_patient(
            missing_id,
            PatientUpdateDTO(full_name="Nobody"),
        )


@pytest.mark.asyncio
async def test_update_patient_no_fields() -> None:
    """update_patient should raise ValidationError with empty update."""
    pool, _conn = _mock_pool_and_conn()
    svc = PatientService(pool)

    with pytest.raises(ValidationError, match="No fields to update"):
        await svc.update_patient(FAKE_UUID, PatientUpdateDTO())


# ---------------------------------------------------------------------------
# Schema unit tests
# ---------------------------------------------------------------------------


def test_patient_dto_masks_national_id() -> None:
    """PatientDTO should mask national_id_number on construction."""
    from clinicai.schemas.patient import _mask_national_id

    assert _mask_national_id(None) is None
    assert _mask_national_id("012345678901") == "012*******01"
    assert _mask_national_id("12345") == "*****"
    assert _mask_national_id("AB") == "**"


def test_create_dto_rejects_blank_name() -> None:
    """PatientCreateDTO should reject empty/whitespace full_name."""
    with pytest.raises(Exception, match="full_name must not be blank"):
        PatientCreateDTO(
            full_name="   ",
            location_id=uuid4(),
        )


def test_patient_dto_from_record() -> None:
    """PatientDTO should populate from a dict (simulating asyncpg Record)."""
    from clinicai.schemas.patient import PatientDTO

    record = _make_record({"national_id_number": "001099001234"})
    dto = PatientDTO.model_validate(record)

    assert dto.clinic_patient_id == FAKE_UUID
    assert dto.patient_code == "BN-2026-000001"
    # Masked: "001099001234" → "001*******34"
    assert dto.national_id_number == "001*******34"
