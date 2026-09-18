"""Run prescription identity SQL against local disposable Postgres temp tables.

Opt in with DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:55433/postgres.
No permanent schema, functions, or public records are created or changed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.clinical_record_service import ClinicalRecordService

VISIT = "10000000-0000-0000-0000-000000000001"
OTHER_VISIT = "10000000-0000-0000-0000-000000000002"
CLINIC = "20000000-0000-0000-0000-000000000001"
OTHER_CLINIC = "20000000-0000-0000-0000-000000000002"
PATIENT = "30000000-0000-0000-0000-000000000001"
RX_A = "40000000-0000-0000-0000-000000000001"
RX_B = "40000000-0000-0000-0000-000000000002"
RX_OTHER_VISIT = "40000000-0000-0000-0000-000000000003"
RX_OTHER_CLINIC = "40000000-0000-0000-0000-000000000004"

pytestmark = [pytest.mark.asyncio, pytest.mark.db]


@pytest_asyncio.fixture
async def rx_conn(test_db_url: str) -> AsyncIterator[asyncpg.Connection]:
    target = urlsplit(test_db_url)
    if target.hostname not in {"localhost", "127.0.0.1"} or target.port != 55433:
        pytest.skip("Identity SQL tests only use disposable localhost:55433")
    conn = await asyncpg.connect(test_db_url)
    try:
        await conn.execute(
            """
            CREATE TEMP TABLE prescription (
                id uuid PRIMARY KEY,
                visit_id uuid NOT NULL,
                clinic_id uuid NOT NULL,
                drug_name_raw text,
                quantity text,
                dosage_instructions text,
                caution text,
                dispensed_qty numeric NOT NULL DEFAULT 0,
                closed_at timestamptz,
                source_ref text NOT NULL UNIQUE,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            );
            CREATE TEMP TABLE rx_stock_movement (
                prescription_id uuid REFERENCES prescription(id),
                quantity numeric NOT NULL
            );
            """
        )
        await conn.executemany(
            """
            INSERT INTO prescription (
                id, visit_id, clinic_id, drug_name_raw, quantity,
                dosage_instructions, dispensed_qty, closed_at, source_ref
            ) VALUES ($1::uuid, $2::uuid, $3::uuid, 'Drug A', '10 viên',
                      $4, $5, CASE WHEN $6 THEN now() ELSE NULL END, $7)
            """,
            [
                (RX_A, VISIT, CLINIC, "Original morning", 2, False, "original-a"),
                (RX_B, VISIT, CLINIC, "Original evening", 0, True, "original-b"),
                (
                    RX_OTHER_VISIT,
                    OTHER_VISIT,
                    CLINIC,
                    "Other visit",
                    1,
                    False,
                    "other-visit",
                ),
                (
                    RX_OTHER_CLINIC,
                    VISIT,
                    OTHER_CLINIC,
                    "Other clinic",
                    1,
                    False,
                    "other-clinic",
                ),
            ],
        )
        await conn.execute("INSERT INTO rx_stock_movement VALUES ($1::uuid, 2)", RX_A)
        yield conn
    finally:
        await conn.close()


def item(rx_id: str | None, dosage: str) -> dict[str, str | None]:
    return {
        "id": rx_id,
        "drug_name": "Drug A",
        "quantity": "10 viên",
        "dosage": dosage,
        "caution": "After food",
    }


async def replace(conn: asyncpg.Connection, items: list[dict[str, str | None]]) -> None:
    await ClinicalRecordService(None)._replace_prescriptions(
        conn,
        visit_id=VISIT,
        clinic_patient_id=PATIENT,
        clinic_id=CLINIC,
        prescriptions=items,
    )


async def snapshot(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    rows: list[asyncpg.Record] = await conn.fetch(
        "SELECT * FROM prescription ORDER BY id"
    )
    return rows


async def test_reordered_same_drug_rows_preserve_identity_and_stock_reference(
    rx_conn: asyncpg.Connection,
) -> None:
    before = await snapshot(rx_conn)
    await replace(rx_conn, [item(RX_B, "Evening"), item(RX_A, "Morning")])
    after = await snapshot(rx_conn)
    assert [(str(row["id"]), row["dosage_instructions"]) for row in after[:2]] == [
        (RX_A, "Morning"),
        (RX_B, "Evening"),
    ]
    for old, new in zip(before[:2], after[:2], strict=True):
        for field in ("id", "dispensed_qty", "closed_at", "source_ref", "created_at"):
            assert new[field] == old[field]
    assert after[2:] == before[2:]
    assert (
        await rx_conn.fetchval("SELECT prescription_id::text FROM rx_stock_movement")
        == RX_A
    )
    assert await rx_conn.fetchval("SELECT sum(quantity) FROM rx_stock_movement") == 2


@pytest.mark.parametrize("rx_id", [RX_OTHER_VISIT, RX_OTHER_CLINIC])
async def test_cross_visit_or_clinic_ids_reject_without_modifying_any_rows(
    rx_conn: asyncpg.Connection,
    rx_id: str,
) -> None:
    before = await snapshot(rx_conn)
    with pytest.raises(ValidationError):
        await replace(
            rx_conn,
            [item(RX_A, "Morning"), item(RX_B, "Evening"), item(rx_id, "Foreign")],
        )
    assert await snapshot(rx_conn) == before


@pytest.mark.parametrize(
    "items,error",
    [
        ([item(None, "Morning"), item(None, "Evening")], ValidationError),
        ([item(RX_A, "Morning"), item(RX_A, "Evening")], ValidationError),
        ([item(RX_A, "Changed morning")], ConflictError),
        ([], ConflictError),
    ],
)
async def test_invalid_payload_does_not_partially_update_locked_rows(
    rx_conn: asyncpg.Connection,
    items: list[dict[str, str | None]],
    error: type[Exception],
) -> None:
    before = await snapshot(rx_conn)
    with pytest.raises(error):
        await replace(rx_conn, items)
    assert await snapshot(rx_conn) == before


async def test_unambiguous_legacy_payload_updates_existing_locked_id(
    rx_conn: asyncpg.Connection,
) -> None:
    # Remove one closed row in this disposable fixture to make legacy identity unique.
    await rx_conn.execute("DELETE FROM prescription WHERE id = $1::uuid", RX_B)
    await replace(rx_conn, [item(None, "Legacy correction")])
    assert (
        await rx_conn.fetchval(
            "SELECT dosage_instructions FROM prescription WHERE id = $1::uuid", RX_A
        )
        == "Legacy correction"
    )
    assert (
        await rx_conn.fetchval("SELECT prescription_id::text FROM rx_stock_movement")
        == RX_A
    )


async def test_clear_drafts_only_deletes_current_visit_and_clinic(
    rx_conn: asyncpg.Connection,
) -> None:
    # Convert local rows to drafts; foreign locked rows remain outside the write scope.
    await rx_conn.execute("DELETE FROM rx_stock_movement")
    await rx_conn.execute(
        "UPDATE prescription SET dispensed_qty = 0, closed_at = NULL "
        "WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        CLINIC,
        VISIT,
    )
    before = await snapshot(rx_conn)
    await replace(rx_conn, [])
    assert await snapshot(rx_conn) == before[2:]
