"""Real dispensing SQL uses only TEMP objects on disposable localhost:55433."""

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlsplit

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.pharmacy_service import PharmacyService

CLINIC = "10000000-0000-0000-0000-000000000001"
RX = "20000000-0000-0000-0000-000000000001"
BATCH = "30000000-0000-0000-0000-000000000001"
STAFF = "40000000-0000-0000-0000-000000000001"
VISIT = "50000000-0000-0000-0000-000000000001"
CYCLE = "60000000-0000-0000-0000-000000000001"

pytestmark = [pytest.mark.asyncio, pytest.mark.db]


@pytest_asyncio.fixture
async def stock_conn(test_db_url: str) -> AsyncIterator[asyncpg.Connection]:
    target = urlsplit(test_db_url)
    if target.hostname not in {"localhost", "127.0.0.1"} or target.port != 55433:
        pytest.skip("Dispensing SQL tests only use disposable localhost:55433")
    conn = await asyncpg.connect(test_db_url)
    try:
        await conn.execute(
            """
            CREATE TEMP TABLE visit (
                visit_id uuid PRIMARY KEY, clinic_id uuid NOT NULL
            );
            -- CP3: cấp phát đòi tiền thuốc đã thu; lần thu cũ (`legacy`) đi
            -- đúng luồng cấp phát cũ mà file này kiểm.
            CREATE TEMP TABLE payment_cycle (
                payment_cycle_id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
                visit_id uuid NOT NULL, kind text NOT NULL, status text NOT NULL,
                legacy boolean NOT NULL
            );
            CREATE TEMP TABLE prescription (
                id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
                visit_id uuid NOT NULL,
                drug_name_raw text, purchased_qty numeric, drug_catalog_id uuid,
                quantity_num numeric, unit text,
                dispensed_qty numeric NOT NULL DEFAULT 0,
                closed_at timestamptz, refusal_reason text,
                removed_at timestamptz,
                dispensed_at timestamptz, dispensed_by_staff_id uuid,
                updated_at timestamptz,
                dispense_status text GENERATED ALWAYS AS (
                    CASE WHEN dispensed_qty >= quantity_num THEN 'CAP_DU'
                         WHEN dispensed_qty > 0 THEN 'CAP_MOT_PHAN'
                         ELSE 'CHUA_CAP' END
                ) STORED,
                CHECK (quantity_num IS NULL OR dispensed_qty <= quantity_num)
            );
            CREATE TEMP TABLE drug_catalog (id uuid PRIMARY KEY, name_base text);
            CREATE TEMP TABLE drug_batch (
                id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
                drug_catalog_id uuid, quantity_on_hand numeric NOT NULL,
                expiry_date date, unit text NOT NULL,
                CHECK (quantity_on_hand >= 0)
            );
            CREATE TEMP TABLE inventory_txn (
                clinic_id uuid, drug_batch_id uuid, txn_type text,
                quantity numeric, reason text, ref_type text, ref_id uuid,
                performed_by_staff_id uuid, performed_at timestamptz,
                payment_cycle_id uuid, allocation_id uuid
            );
            CREATE TEMP TABLE event_log (
                clinic_id uuid, event_type text, aggregate_type text,
                aggregate_id uuid, payload jsonb, metadata jsonb,
                source text, event_published boolean
            );
            CREATE FUNCTION pg_temp.apply_stock() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                UPDATE pg_temp.drug_batch
                   SET quantity_on_hand = quantity_on_hand + NEW.quantity
                 WHERE id = NEW.drug_batch_id AND clinic_id = NEW.clinic_id;
                RETURN NEW;
            END $$;
            CREATE TRIGGER apply_stock AFTER INSERT ON inventory_txn
            FOR EACH ROW EXECUTE FUNCTION pg_temp.apply_stock();
            """
        )
        await conn.execute(
            "INSERT INTO visit VALUES ($1::uuid, $2::uuid)", VISIT, CLINIC
        )
        await conn.execute(
            "INSERT INTO payment_cycle VALUES"
            " ($1::uuid, $2::uuid, $3::uuid, 'thuoc', 'PAID', true)",
            CYCLE,
            CLINIC,
            VISIT,
        )
        await conn.execute(
            "INSERT INTO prescription (id, clinic_id, visit_id, drug_name_raw, "
            "quantity_num, unit) VALUES ($1::uuid, $2::uuid, $3::uuid, 'Thuốc thử',"
            " 2, 'hộp')",
            RX,
            CLINIC,
            VISIT,
        )
        await conn.execute(
            "INSERT INTO drug_catalog VALUES ($1::uuid, 'Thuốc thử')", BATCH
        )
        await conn.execute(
            "INSERT INTO drug_batch VALUES "
            "($1::uuid, $2::uuid, $1::uuid, 100, '2099-12-31', 'viên')",
            BATCH,
            CLINIC,
        )
        yield conn
    finally:
        await conn.close()


def temporary_service(conn: asyncpg.Connection) -> PharmacyService:
    """Redirect explicit public references to connection-local TEMP fixtures."""

    async def fetchrow(sql: str, *args: Any) -> Any:
        return await conn.fetchrow(sql.replace("public.", "pg_temp."), *args)

    async def execute(sql: str, *args: Any) -> Any:
        return await conn.execute(sql.replace("public.", "pg_temp."), *args)

    async def fetchval(sql: str, *args: Any) -> Any:
        return await conn.fetchval(sql.replace("public.", "pg_temp."), *args)

    proxy = MagicMock()
    proxy.transaction = conn.transaction
    proxy.fetchrow = AsyncMock(side_effect=fetchrow)
    proxy.execute = AsyncMock(side_effect=execute)
    proxy.fetchval = AsyncMock(side_effect=fetchval)
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=proxy)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return PharmacyService(pool)


async def dispense(conn: asyncpg.Connection) -> dict[str, Any]:
    staff = StaffIdentity(
        staff_id=STAFF,
        auth_user_id=STAFF,
        full_name="Dược sĩ kiểm thử",
        department="Nhà thuốc",
        role=ClinicRole.PHARMACIST,
        clinic_id=CLINIC,
        location_id=CLINIC,
        location_name="Cơ sở kiểm thử",
    )
    return await temporary_service(conn).cap_phat(
        identity=staff, prescription_id=RX, drug_batch_id=BATCH, so_luong="2"
    )


async def test_box_rx_tablet_stock_rejection_keeps_both_ledgers_unchanged(
    stock_conn: asyncpg.Connection,
) -> None:
    before = await stock_conn.fetchrow("SELECT * FROM prescription")
    with pytest.raises(ValidationError, match="hộp.*viên"):
        await dispense(stock_conn)
    assert await stock_conn.fetchrow("SELECT * FROM prescription") == before
    assert await stock_conn.fetchval("SELECT quantity_on_hand FROM drug_batch") == 100
    assert await stock_conn.fetchval("SELECT count(*) FROM inventory_txn") == 0
    assert await stock_conn.fetchval("SELECT count(*) FROM event_log") == 0


@pytest.mark.parametrize("rx_unit", [" VIÊN ", "vie\u0302n", None])
async def test_same_or_legacy_units_update_stock_and_rx_atomically(
    stock_conn: asyncpg.Connection, rx_unit: str | None
) -> None:
    await stock_conn.execute("UPDATE prescription SET unit = $1", rx_unit)
    assert await dispense(stock_conn) == {
        "ok": True,
        "dispensed_qty": Decimal("2"),
        "dispense_status": "CAP_DU",
    }
    assert await stock_conn.fetchval("SELECT quantity_on_hand FROM drug_batch") == 98
    assert await stock_conn.fetchval("SELECT quantity FROM inventory_txn") == -2
    assert await stock_conn.fetchval("SELECT ref_id::text FROM inventory_txn") == RX
    assert await stock_conn.fetchval("SELECT count(*) FROM event_log") == 1
