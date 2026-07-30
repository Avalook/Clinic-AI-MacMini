"""Unit tests for MPIService deduplication engine."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.schemas.patient import PatientCreateDTO, PatientDTO
from clinicai.services.mpi_service import MPIService

identity = StaffIdentity(
    staff_id="s1",
    auth_user_id="u1",
    full_name="CSKH test",
    department="CSKH",
    role=ClinicRole.CSKH,
    clinic_id="a0000000-0000-4000-8000-000000000001",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_LOCATION = uuid4()
FAKE_NOW = datetime.datetime(2026, 5, 20, 10, 0, 0, tzinfo=datetime.timezone.utc)


def _make_dto(overrides: dict[str, Any] | None = None) -> PatientDTO:
    """Build a PatientDTO for scoring tests."""
    base = {
        "clinic_patient_id": uuid4(),
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
    return PatientDTO.model_validate(base)


def _make_record(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a raw dict simulating an asyncpg Record."""
    base = {
        "clinic_patient_id": uuid4(),
        "patient_code": "BN-2026-000002",
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
    """Return (pool, conn) with pool.acquire() wired."""
    pool = MagicMock()
    conn = AsyncMock()

    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    transaction_ctx = AsyncMock()
    transaction_ctx.__aenter__.return_value = conn
    conn.transaction = MagicMock(return_value=transaction_ctx)

    return pool, conn


# ===========================================================================
# Scoring tests
# ===========================================================================


def test_score_phone_match() -> None:
    """Exact phone_primary match should yield 50 pts (+ name fuzzy)."""
    candidate = _make_dto({"full_name": "Trần Văn B", "phone_primary": "+84901234567"})
    existing = _make_dto({"full_name": "Nguyễn Thị C", "phone_primary": "+84901234567"})
    result = MPIService.score(candidate, existing)
    # 50 (phone) + some small name ratio
    assert result >= 50.0
    assert result < 60.0 + 1  # name can't exceed 10


def test_score_phone_country_code_variant_matches() -> None:
    """Equivalent 0/+84 spellings receive the phone match weight."""
    candidate = _make_dto({"full_name": "A", "phone_primary": "0901234567"})
    existing = _make_dto({"full_name": "B", "phone_primary": "+84901234567"})

    assert MPIService.score(candidate, existing) >= 50.0


def test_score_national_id_match() -> None:
    """Exact national_id match should yield 40 pts (+ name fuzzy)."""
    candidate = _make_dto(
        {
            "full_name": "Trần Văn D",
            "phone_primary": "+84999999999",
            "national_id_number": "012345678901",
        }
    )
    existing = _make_dto(
        {
            "full_name": "Lê Thị E",
            "phone_primary": "+84888888888",
            "national_id_number": "012345678901",
        }
    )
    result = MPIService.score(candidate, existing)
    # 40 (national_id) + some small name ratio, no phone
    assert result >= 40.0
    assert result < 51.0


def test_score_full_match() -> None:
    """Phone + national_id + identical name should reach 100."""
    dto_a = _make_dto(
        {
            "full_name": "Nguyễn Thị Lan",
            "phone_primary": "+84901234567",
            "national_id_number": "012345678901",
        }
    )
    dto_b = _make_dto(
        {
            "full_name": "Nguyễn Thị Lan",
            "phone_primary": "+84901234567",
            "national_id_number": "012345678901",
        }
    )
    result = MPIService.score(dto_a, dto_b)
    # 50 + 40 + 10 = 100
    assert result == 100.0


def test_score_no_match() -> None:
    """Completely different patients should score below threshold."""
    candidate = _make_dto(
        {
            "full_name": "Phạm Văn X",
            "phone_primary": "+84111111111",
            "national_id_number": "999999999999",
        }
    )
    existing = _make_dto(
        {
            "full_name": "Lê Thị Y",
            "phone_primary": "+84222222222",
            "national_id_number": "000000000000",
        }
    )
    result = MPIService.score(candidate, existing)
    # No phone, no national_id, low name ratio
    assert result < 70.0


def test_score_name_only_fuzzy() -> None:
    """Similar names with no phone/id match should score name-only."""
    candidate = _make_dto(
        {
            "full_name": "Nguyễn Thị Lan",
            "phone_primary": None,
            "national_id_number": None,
        }
    )
    existing = _make_dto(
        {
            "full_name": "Nguyễn Thị Lan",
            "phone_primary": None,
            "national_id_number": None,
        }
    )
    result = MPIService.score(candidate, existing)
    # Only name match: ratio ~1.0 * 10 = 10.0
    assert 9.0 <= result <= 10.0


def test_score_capped_at_100() -> None:
    """Score should never exceed 100.0."""
    dto = _make_dto(
        {
            "full_name": "Nguyễn Thị Lan",
            "phone_primary": "+84901234567",
            "national_id_number": "012345678901",
        }
    )
    result = MPIService.score(dto, dto)
    assert result <= 100.0


# ===========================================================================
# find_candidates tests
# ===========================================================================


@pytest.mark.asyncio
async def test_find_candidates_returns_list() -> None:
    """find_candidates should return PatientDTOs from DB matches."""
    pool, conn = _mock_pool_and_conn()
    conn.fetch.return_value = [
        _make_record({"clinic_patient_id": uuid4()}),
        _make_record({"clinic_patient_id": uuid4()}),
    ]

    data = PatientCreateDTO(
        full_name="Nguyễn Thị Lan",
        phone_primary="0901234567",
        location_id=FAKE_LOCATION,
    )
    results = await MPIService.find_candidates(
        pool, data, "a0000000-0000-4000-8000-000000000001"
    )

    assert len(results) == 2
    conn.fetch.assert_awaited_once()
    sql_arg = conn.fetch.call_args[0][0]
    assert "phone_primary = ANY($1::text[])" in sql_arg
    assert "phone_secondary = ANY($1::text[])" in sql_arg
    assert set(conn.fetch.call_args[0][1]) == {
        "0901234567",
        "84901234567",
        "+84901234567",
    }


@pytest.mark.asyncio
async def test_find_candidates_with_national_id() -> None:
    """find_candidates should include national_id_number in query."""
    pool, conn = _mock_pool_and_conn()
    conn.fetch.return_value = []

    data = PatientCreateDTO(
        full_name="Trần Văn A",
        phone_primary="0901234567",
        national_id_number="012345678901",
        location_id=FAKE_LOCATION,
    )
    await MPIService.find_candidates(pool, data, "a0000000-0000-4000-8000-000000000001")

    sql_arg = conn.fetch.call_args[0][0]
    assert "phone_primary" in sql_arg
    assert "national_id_number" in sql_arg


@pytest.mark.asyncio
async def test_find_candidates_no_identifiers() -> None:
    """find_candidates should return empty when no phone or national_id."""
    pool, _conn = _mock_pool_and_conn()

    data = PatientCreateDTO(
        full_name="No Phone",
        location_id=FAKE_LOCATION,
    )
    results = await MPIService.find_candidates(
        pool, data, "a0000000-0000-4000-8000-000000000001"
    )

    assert results == []


# ===========================================================================
# auto_queue_if_needed tests
# ===========================================================================


@pytest.mark.asyncio
async def test_auto_queue_above_threshold() -> None:
    """Candidates scoring >= 70 should be inserted into the merge queue."""
    pool, conn = _mock_pool_and_conn()
    mpi = MPIService()

    new_id = uuid4()
    candidate_id = uuid4()

    # The new patient fetched from DB for scoring
    new_record = _make_record(
        {
            "clinic_patient_id": new_id,
            "phone_primary": "+84901234567",
            "national_id_number": "012345678901",
            "full_name": "Nguyễn Thị Lan",
        }
    )
    conn.fetchrow.side_effect = [
        new_record,  # SELECT for new patient
        {"id": uuid4()},  # INSERT RETURNING id
    ]

    # Candidate with same phone + same national_id + same name
    # → score = 50 (phone) + 40 (national_id) + 10 (name) = 100
    candidate = _make_dto(
        {
            "clinic_patient_id": candidate_id,
            "phone_primary": "+84901234567",
            "national_id_number": "012345678901",
            "full_name": "Nguyễn Thị Lan",
        }
    )

    queue_ids = await mpi.auto_queue_if_needed(
        pool, new_id, [candidate], "a0000000-0000-4000-8000-000000000001"
    )

    assert len(queue_ids) == 1
    # Verify INSERT into mpi_merge_queue was called
    insert_call = conn.fetchrow.call_args_list[1]
    sql_arg = insert_call[0][0]
    assert "INSERT INTO mpi_merge_queue" in sql_arg


@pytest.mark.asyncio
async def test_auto_queue_below_threshold() -> None:
    """Candidates scoring < 70 should NOT be queued."""
    pool, conn = _mock_pool_and_conn()
    mpi = MPIService()

    new_id = uuid4()

    # New patient with different phone, no national_id
    new_record = _make_record(
        {
            "clinic_patient_id": new_id,
            "phone_primary": "+84111111111",
            "national_id_number": None,
            "full_name": "Phạm Văn Hoàng",
        }
    )
    conn.fetchrow.return_value = new_record

    # Candidate with totally different data
    candidate = _make_dto(
        {
            "phone_primary": "+84222222222",
            "national_id_number": None,
            "full_name": "Lê Thị Xuân",
        }
    )

    queue_ids = await mpi.auto_queue_if_needed(
        pool, new_id, [candidate], "a0000000-0000-4000-8000-000000000001"
    )

    assert queue_ids == []
    # Only the SELECT for new patient, no INSERT
    assert conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_auto_queue_new_patient_not_found() -> None:
    """auto_queue should gracefully skip if new patient row is gone."""
    pool, conn = _mock_pool_and_conn()
    mpi = MPIService()

    conn.fetchrow.return_value = None  # patient deleted?

    candidate = _make_dto()
    queue_ids = await mpi.auto_queue_if_needed(
        pool, uuid4(), [candidate], "a0000000-0000-4000-8000-000000000001"
    )

    assert queue_ids == []


# ===========================================================================
# get_pending_queue tests
# ===========================================================================


@pytest.mark.asyncio
async def test_get_pending_queue() -> None:
    """get_pending_queue should return dicts sorted by score DESC."""
    pool, conn = _mock_pool_and_conn()

    fake_rows = [
        {
            "id": uuid4(),
            "patient_id_a": uuid4(),
            "patient_id_b": uuid4(),
            "score": 95.0,
            "status": "PENDING",
        },
        {
            "id": uuid4(),
            "patient_id_a": uuid4(),
            "patient_id_b": uuid4(),
            "score": 72.5,
            "status": "PENDING",
        },
    ]
    conn.fetch.return_value = fake_rows

    results = await MPIService.get_pending_queue(
        pool, limit=10, clinic_id="a0000000-0000-4000-8000-000000000001"
    )

    assert len(results) == 2
    conn.fetch.assert_awaited_once()
    sql_arg = conn.fetch.call_args[0][0]
    assert "status = 'PENDING'" in sql_arg
    assert "ORDER BY score DESC" in sql_arg


# ===========================================================================
# Integration: MPI failure does not block create_patient
# ===========================================================================


@pytest.mark.asyncio
async def test_mpi_failure_does_not_block_create() -> None:
    """PatientService.create_patient should succeed even if MPI throws."""
    from clinicai.services.patient_service import PatientService

    pool, conn = _mock_pool_and_conn()

    patient_record = _make_record({"clinic_patient_id": uuid4()})
    conn.fetchrow.return_value = patient_record
    conn.fetch.return_value = []  # no phone duplicates → proceed to insert

    svc = PatientService(pool)

    # Make MPI.find_candidates raise an exception
    with patch(
        "clinicai.services.mpi_service.MPIService.find_candidates",
        side_effect=RuntimeError("DB connection lost"),
    ):
        result = await svc.create_patient(
            PatientCreateDTO(
                full_name="Nguyễn Thị Lan",
                phone_primary="0901234567",
                location_id=FAKE_LOCATION,
            ),
            identity,
        )

    # Patient was still created successfully despite the MPI failure.
    assert result.patient is not None
    assert result.patient.full_name == "Nguyễn Thị Lan"
