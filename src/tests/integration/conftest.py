import os
from uuid import UUID

import asyncpg
import pytest
from dotenv import load_dotenv

from clinicai.services.patient_service import PatientService

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


@pytest.fixture(scope="function")
async def db_pool():
    """Fixture yielding an asyncpg pool to staging DB, or skips if unconfigured."""
    if not DATABASE_URL:
        pytest.skip("no DB")

    # Normalize DSN (asyncpg requires postgresql:// instead of postgresql+asyncpg://)
    dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=3,
    )
    yield pool
    await pool.close()


@pytest.fixture(scope="function")
def patient_service(db_pool) -> PatientService:
    """Fixture that initializes the PatientService with the active db pool."""
    return PatientService(db_pool)


@pytest.fixture(scope="function")
async def location_id(db_pool) -> UUID:
    """Fixture returning a valid location UUID (fetches or seeds default)."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM clinic_location LIMIT 1;")
        if row:
            return row["id"]

        # Insert fallback location if clinic_location is empty
        loc_id = await conn.fetchval(
            """
            INSERT INTO clinic_location (code, name, address, is_active)
            VALUES ('TEST-INTEG-LOC', 'Test Integration Location', '123 Test St', TRUE)
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id;
            """
        )
        return loc_id


@pytest.fixture(scope="function")
async def cleanup_patients(db_pool):
    """Fixture that accepts a list of patient codes to clean up after test execution."""
    patient_codes = []
    yield patient_codes
    if patient_codes:
        async with db_pool.acquire() as conn:
            # Fetch patient IDs for the registered codes
            rows = await conn.fetch(
                "SELECT clinic_patient_id FROM patient WHERE patient_code = ANY($1);",
                patient_codes,
            )
            patient_ids = [row["clinic_patient_id"] for row in rows]

            if patient_ids:
                # Delete related rows in order of constraints to avoid FK errors
                await conn.execute(
                    "DELETE FROM pregnancy WHERE clinic_patient_id = ANY($1);",
                    patient_ids,
                )
                await conn.execute(
                    "DELETE FROM patient_medical_profile "
                    "WHERE clinic_patient_id = ANY($1);",
                    patient_ids,
                )
                await conn.execute(
                    "DELETE FROM mpi_merge_queue "
                    "WHERE patient_id_a = ANY($1) OR patient_id_b = ANY($1);",
                    patient_ids,
                )
                await conn.execute(
                    "DELETE FROM patient WHERE clinic_patient_id = ANY($1);",
                    patient_ids,
                )


@pytest.fixture(scope="function")
async def async_client(db_pool):
    """Fixture providing an HTTPX AsyncClient for FastAPI endpoint testing."""
    from clinicai.core.database import get_db_pool
    from clinicai.main import app

    app.dependency_overrides[get_db_pool] = lambda: db_pool
    # Use ASGITransport
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def clean_db(db_pool):
    """Fixture to clean up tables in reverse dependency order after each test."""

    async def _clean():
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM appointment;")
            await conn.execute("DELETE FROM work_session_staff;")
            await conn.execute("DELETE FROM work_session;")
            await conn.execute("DELETE FROM staff;")
            await conn.execute("DELETE FROM pregnancy;")
            await conn.execute("DELETE FROM patient_medical_profile;")
            await conn.execute("DELETE FROM mpi_merge_queue;")
            await conn.execute("DELETE FROM patient;")

    await _clean()
    yield
    await _clean()


@pytest.fixture(scope="function")
async def service_type_id(db_pool) -> UUID:
    """Fixture returning a valid service type UUID."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM service_type LIMIT 1;")
        if row:
            return row["id"]
        s_id = await conn.fetchval(
            "INSERT INTO service_type (code, name) "
            "VALUES ('TEST-SVC', 'Test Service') RETURNING id;"
        )
        return s_id
