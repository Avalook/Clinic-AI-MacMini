"""Synthetic Postgres probe for a stale event worker completing after lease reclaim.

Run only through scripts/test-nhanh.sh so the connection targets its disposable DB.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.events.catalogue import ChiDinhDaDat
from clinicai.events.emit import HE_THONG, emit_event
from clinicai.events.worker import SuKienDaNhan, dang_ky, lam_mot_dong, thu_hoi_thue

CLINIC = "a0000000-0000-4000-8000-000000000001"
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL_TEST") or ""
    if not url:
        pytest.skip("requires disposable DATABASE_URL_TEST")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    result = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield result
    await result.close()


async def test_expired_still_running_worker_can_duplicate_callback(pool: asyncpg.Pool) -> None:
    consumer = f"audit_stale_worker_{uuid.uuid4().hex[:10]}"
    probe_id = str(uuid.uuid4())
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    callback_count = 0
    await pool.execute(
        "CREATE TABLE IF NOT EXISTS audit_worker_lease_probe ("
        " probe_id uuid NOT NULL, event_id uuid NOT NULL, attempt integer NOT NULL)"
    )

    async def callback(conn: asyncpg.Connection, event: SuKienDaNhan) -> None:
        nonlocal callback_count
        callback_count += 1
        this_attempt = callback_count
        if this_attempt == 1:
            first_entered.set()
            await release_first.wait()
        await conn.execute(
            "INSERT INTO audit_worker_lease_probe (probe_id,event_id,attempt)"
            " VALUES ($1::uuid,$2::uuid,$3)",
            probe_id,
            event.event_id,
            this_attempt,
        )

    dang_ky(consumer, callback)
    visit_id, order_id = str(uuid.uuid4()), str(uuid.uuid4())
    async with pool.acquire() as conn, conn.transaction():
        event_id = await emit_event(
            conn,
            ten="service_order.placed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=1,
            payload=ChiDinhDaDat(
                order_id=order_id,
                service_code="SA-DAUDO",
                service_name="Synthetic probe",
                consultation_id=str(uuid.uuid4()),
                visit_id=visit_id,
                selection_status="PENDING",
                billing_status="UNPAID",
            ),
            boi=HE_THONG,
        )
    await pool.execute(
        "INSERT INTO event_delivery (event_id,consumer,clinic_id,aggregate_id,"
        " aggregate_version) VALUES ($1::uuid,$2,$3::uuid,$4::uuid,1)",
        event_id,
        consumer,
        CLINIC,
        order_id,
    )

    old_worker = asyncio.create_task(lam_mot_dong(pool, consumer, ten_worker="old"))
    try:
        await asyncio.wait_for(first_entered.wait(), timeout=5)
        await pool.execute(
            "UPDATE event_delivery SET lease_expires_at = now() - interval '1 second'"
            " WHERE event_id = $1::uuid AND consumer = $2",
            event_id,
            consumer,
        )
        assert await thu_hoi_thue(pool) >= 1
        assert await asyncio.wait_for(
            lam_mot_dong(pool, consumer, ten_worker="new"), timeout=5
        ) is True
        assert await pool.fetchval(
            "SELECT status FROM event_delivery WHERE event_id=$1::uuid AND consumer=$2",
            event_id,
            consumer,
        ) == "DONE"
    finally:
        release_first.set()
        await asyncio.wait_for(old_worker, timeout=5)

    committed = await pool.fetchval(
        "SELECT count(*) FROM audit_worker_lease_probe WHERE probe_id=$1::uuid",
        probe_id,
    )
    assert callback_count == 2
    assert committed == 2
    await pool.execute(
        "DELETE FROM audit_worker_lease_probe WHERE probe_id=$1::uuid", probe_id
    )
