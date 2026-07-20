"""Negative tests for the 3 DB safety-gate triggers of migration 017.

Medical Safety Gate (CANON 05_DATABASE_DESIGN_FINAL §261-267, TT13/2011/TT-BYT):
  1. trg_visit_finalized_block       — a FINALIZED visit cannot be UPDATEd
     (the only allowed transition is FINALIZED -> AMENDED).
  2. trg_visit_amendment_no_update   — visit_amendment is APPEND-ONLY: UPDATE blocked.
  3. trg_visit_amendment_no_delete   — visit_amendment is APPEND-ONLY: DELETE blocked.

These triggers were found missing from production (worklog 2026-05-24 debt #1) and
have since been applied. We do NOT trust a safety gate without a negative test.

Isolation: every test runs the full migration set into a transient schema inside a
transaction that is ALWAYS rolled back, then the schema is dropped. Nothing is ever
committed to the production ``public`` schema — no seeded rows survive.

The triggers raise with ERRCODE = 'check_violation' (SQLSTATE 23514), which asyncpg
surfaces as a subclass of asyncpg.exceptions.PostgresError.
"""

import os
import pathlib
import re
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


async def _run_all_migrations_in_tx(conn: asyncpg.Connection) -> None:
    """Run every UP migration in order inside the active transaction/schema."""
    migrations_dir = pathlib.Path(__file__).parent.parent.parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"), key=lambda p: p.name)
    up_files = [
        f
        for f in sql_files
        if not f.name.endswith(".down.sql") and f.name.startswith("2026")
    ]

    for f in up_files:
        content = f.read_text(encoding="utf-8")
        # Strip per-file transaction boundaries; we drive one outer transaction.
        cleaned = re.sub(r"^\s*BEGIN\s*;\s*", "", content, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*COMMIT\s*;\s*$", "", cleaned, flags=re.IGNORECASE)
        await conn.execute(cleaned)


@pytest.fixture
async def db_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Yield a conn with full schema built in a rolled-back transient schema."""
    if not DATABASE_URL:
        pytest.skip("no DB")

    dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)

    await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_TEMP_SCHEMA};")
    await conn.execute(f"SET search_path TO {_TEMP_SCHEMA};")

    tx = conn.transaction()
    await tx.start()
    try:
        await _run_all_migrations_in_tx(conn)
        yield conn
    finally:
        # Roll back ALL migration DDL + any seeded test rows: nothing persists.
        await tx.rollback()
        await conn.execute(f"DROP SCHEMA IF EXISTS {_TEMP_SCHEMA} CASCADE;")
        await conn.close()


async def _seed_location(conn: asyncpg.Connection) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "INSERT INTO clinic_location (code, name) "
            "VALUES ('SG017-LOC', 'Safety Gate 017 Loc') RETURNING id;"
        ),
    )


async def _seed_patient(conn: asyncpg.Connection, location_id: UUID) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "INSERT INTO patient (patient_code, full_name, location_id) "
            "VALUES ('SG017-BN-001', 'Safety Gate Patient', $1) "
            "RETURNING clinic_patient_id;",
            location_id,
        ),
    )


async def _seed_staff(conn: asyncpg.Connection) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department) "
            "VALUES ('Dr Safety Gate', 'DOCTOR') RETURNING id;"
        ),
    )


async def _seed_visit(conn: asyncpg.Connection, patient_id: UUID, status: str) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "INSERT INTO visit (clinic_patient_id, status) VALUES ($1, $2) "
            "RETURNING visit_id;",
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
            visit_id, amended_by, reason, corrected_fields,
            original_values, corrected_values
        )
        VALUES ($1, $2, 'typo fix', ARRAY['soap_plan'],
                '{"soap_plan": "old"}'::jsonb, '{"soap_plan": "new"}'::jsonb)
        RETURNING amendment_id;
        """,
            visit_id,
            staff_id,
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
    staff_id = await _seed_staff(db_conn)
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
    staff_id = await _seed_staff(db_conn)
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
    staff_id = await _seed_staff(db_conn)
    visit_id = await _seed_visit(db_conn, patient_id, "AMENDED")

    # Must not raise — append-only blocks UPDATE/DELETE, never INSERT.
    amendment_id = await _seed_amendment(db_conn, visit_id, staff_id)
    assert amendment_id is not None

    count = await db_conn.fetchval(
        "SELECT count(*) FROM visit_amendment WHERE amendment_id = $1;",
        amendment_id,
    )
    assert count == 1
