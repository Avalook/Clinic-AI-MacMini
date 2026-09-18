"""Negative tests for the 3 DB safety-gate triggers of migration 017.

Medical Safety Gate (CANON 05_DATABASE_DESIGN_FINAL §261-267, TT13/2011/TT-BYT):
  1. trg_visit_finalized_block       — a FINALIZED visit cannot be UPDATEd
     (the only allowed transition is FINALIZED -> AMENDED).
  2. trg_visit_amendment_no_update   — visit_amendment is APPEND-ONLY: UPDATE blocked.
  3. trg_visit_amendment_no_delete   — visit_amendment is APPEND-ONLY: DELETE blocked.

These triggers were found missing from production (worklog 2026-05-24 debt #1) and
have since been applied. We do NOT trust a safety gate without a negative test.

Isolation: the disposable DATABASE_URL_TEST already carries the full
``supabase/migrations`` chain (``scripts/tests/dung-db-kiem.sh``). Each test runs
inside ONE transaction that is always rolled back — nothing is committed. (The
old fixture replayed ``src/migrations/*.sql``, a directory that no longer
exists, into a temp schema.)

The triggers raise with ERRCODE = 'check_violation' (SQLSTATE 23514), which asyncpg
surfaces as a subclass of asyncpg.exceptions.PostgresError.
"""

import os
from collections.abc import AsyncGenerator
from typing import cast
from uuid import UUID

import asyncpg
import pytest
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

_CHECK_VIOLATION_SQLSTATE = "23514"
_TEMP_SCHEMA = "test_safety_gate_017_temp"


CLINIC = "a0000000-0000-4000-8000-000000000001"


@pytest.fixture
async def db_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Yield a conn on the migrated schema inside a rolled-back transaction."""
    if not DATABASE_URL:
        pytest.skip("no DB")

    dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    try:
        yield conn
    finally:
        await tx.rollback()
        await conn.close()


async def _seed_location(conn: asyncpg.Connection) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "SELECT id FROM clinic_location WHERE clinic_id = $1::uuid "
            "ORDER BY created_at, id LIMIT 1;",
            CLINIC,
        ),
    )


async def _seed_patient(conn: asyncpg.Connection, location_id: UUID) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id) "
            "VALUES ($1::uuid, 'SG017-BN-001', 'Safety Gate Patient', $2) "
            "RETURNING clinic_patient_id;",
            CLINIC,
            location_id,
        ),
    )


async def _seed_staff(conn: asyncpg.Connection, location_id: UUID) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id) "
            "VALUES ('Dr Safety Gate', 'DOCTOR', $1) RETURNING id;",
            location_id,
        ),
    )


async def _seed_visit(conn: asyncpg.Connection, patient_id: UUID, status: str) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status) "
            "VALUES ($1::uuid, $2, $3) RETURNING visit_id;",
            CLINIC,
            patient_id,
            status,
        ),
    )


async def _seed_amendment(
    conn: asyncpg.Connection, visit_id: UUID, staff_id: UUID
) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            """
        INSERT INTO visit_amendment (
            clinic_id, visit_id, amended_by, reason, corrected_fields,
            original_values, corrected_values
        )
        VALUES ($3::uuid, $1, $2, 'typo fix', ARRAY['soap_plan'],
                '{"soap_plan": "old"}'::jsonb, '{"soap_plan": "new"}'::jsonb)
        RETURNING amendment_id;
        """,
            visit_id,
            staff_id,
            CLINIC,
        ),
    )


# --- Trigger 1: trg_visit_finalized_block ---


@pytest.mark.asyncio
async def test_update_finalized_visit_is_blocked(db_conn: asyncpg.Connection) -> None:
    """UPDATE on a FINALIZED visit must be rejected by the DB trigger."""
    location_id = await _seed_location(db_conn)
    patient_id = await _seed_patient(db_conn, location_id)
    visit_id = await _seed_visit(db_conn, patient_id, "FINALIZED")

    with pytest.raises(asyncpg.exceptions.PostgresError) as exc_info:
        await db_conn.execute(
            "UPDATE visit SET checked_in_at = NOW() WHERE visit_id = $1;",
            visit_id,
        )

    assert exc_info.value.sqlstate == _CHECK_VIOLATION_SQLSTATE
    assert "FINALIZED" in str(exc_info.value)
    assert "blocked" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_non_finalized_visit_is_allowed(
    db_conn: asyncpg.Connection,
) -> None:
    """Control case: UPDATE on a non-FINALIZED visit must NOT be blocked."""
    location_id = await _seed_location(db_conn)
    patient_id = await _seed_patient(db_conn, location_id)
    visit_id = await _seed_visit(db_conn, patient_id, "OPEN")

    # Must not raise — proves the trigger does not over-block legitimate edits.
    await db_conn.execute(
        "UPDATE visit SET checked_in_at = NOW() WHERE visit_id = $1;",
        visit_id,
    )

    status = await db_conn.fetchval(
        "SELECT status FROM visit WHERE visit_id = $1;", visit_id
    )
    assert status == "OPEN"


# --- Triggers 2 & 3: visit_amendment append-only ---


@pytest.mark.asyncio
async def test_visit_amendment_no_update(db_conn: asyncpg.Connection) -> None:
    """UPDATE on a visit_amendment row must be rejected (append-only)."""
    location_id = await _seed_location(db_conn)
    patient_id = await _seed_patient(db_conn, location_id)
    staff_id = await _seed_staff(db_conn, location_id)
    visit_id = await _seed_visit(db_conn, patient_id, "AMENDED")
    amendment_id = await _seed_amendment(db_conn, visit_id, staff_id)

    with pytest.raises(asyncpg.exceptions.PostgresError) as exc_info:
        await db_conn.execute(
            "UPDATE visit_amendment SET reason = 'tampered' WHERE amendment_id = $1;",
            amendment_id,
        )

    assert exc_info.value.sqlstate == _CHECK_VIOLATION_SQLSTATE
    assert "append-only" in str(exc_info.value)


@pytest.mark.asyncio
async def test_visit_amendment_no_delete(db_conn: asyncpg.Connection) -> None:
    """DELETE on a visit_amendment row must be rejected (append-only)."""
    location_id = await _seed_location(db_conn)
    patient_id = await _seed_patient(db_conn, location_id)
    staff_id = await _seed_staff(db_conn, location_id)
    visit_id = await _seed_visit(db_conn, patient_id, "AMENDED")
    amendment_id = await _seed_amendment(db_conn, visit_id, staff_id)

    with pytest.raises(asyncpg.exceptions.PostgresError) as exc_info:
        await db_conn.execute(
            "DELETE FROM visit_amendment WHERE amendment_id = $1;",
            amendment_id,
        )

    assert exc_info.value.sqlstate == _CHECK_VIOLATION_SQLSTATE
    assert "append-only" in str(exc_info.value)


@pytest.mark.asyncio
async def test_visit_amendment_insert_is_allowed(db_conn: asyncpg.Connection) -> None:
    """Control case: INSERT of a visit_amendment must succeed (append IS allowed)."""
    location_id = await _seed_location(db_conn)
    patient_id = await _seed_patient(db_conn, location_id)
    staff_id = await _seed_staff(db_conn, location_id)
    visit_id = await _seed_visit(db_conn, patient_id, "AMENDED")

    # Must not raise — append-only blocks UPDATE/DELETE, never INSERT.
    amendment_id = await _seed_amendment(db_conn, visit_id, staff_id)
    assert amendment_id is not None

    count = await db_conn.fetchval(
        "SELECT count(*) FROM visit_amendment WHERE amendment_id = $1;",
        amendment_id,
    )
    assert count == 1
