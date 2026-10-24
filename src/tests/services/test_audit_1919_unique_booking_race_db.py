"""Disposable-DB probe: concurrent duplicate booking reaches the SQL unique index."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import asyncpg
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from clinicai.core.database import get_db_pool
from clinicai.api.idempotency import IdempotencyGuard, idempotency_guard
from clinicai.api.v1.routers import booking as booking_router
from clinicai.services.booking_service import BookingService
from tests.services.test_check_in_lai_sau_hoan_tac_db import CLINIC, _nguoi, pool

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_concurrent_same_patient_slot_returns_500_unique_violation(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        identity = await _nguoi(conn, str(loc), "RECEPTION")
        patient_id = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'Synthetic unique race', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"AUR-{uuid.uuid4().hex[:10]}",
            loc,
        )
        service_id = await conn.fetchval(
            "SELECT id::text FROM service_type WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY code LIMIT 1",
            CLINIC,
        )
        await conn.execute(
            "UPDATE clinic SET settings = coalesce(settings, '{}'::jsonb)"
            " || jsonb_build_object('booking',"
            " coalesce(settings->'booking', '{}'::jsonb)"
            " || jsonb_build_object('regular_cap', 10))"
            " WHERE id=$1::uuid",
            CLINIC,
        )

        tz = ZoneInfo("Asia/Ho_Chi_Minh")
        start = None
        local_today = datetime.now(tz).date()
        for offset in range(21, 91):
            day = local_today + timedelta(days=offset)
            hours = await conn.fetchrow(
                "SELECT open_minute, close_minute"
                " FROM clinic_hours_for_date($1::uuid, $2::date)",
                CLINIC,
                day,
            )
            if not hours or hours["open_minute"] is None:
                continue
            minute = ((int(hours["open_minute"]) + 14) // 15) * 15
            if minute + 15 <= int(hours["close_minute"]):
                start = datetime.combine(day, time(minute // 60, minute % 60), tzinfo=tz)
                break
        assert start is not None, "No future open clinic slot found in synthetic DB"

    original = BookingService._patient_double_booked
    reached = 0
    gate = asyncio.Lock()
    both_checked = asyncio.Event()

    async def synchronized_precheck(self: BookingService, *args: object, **kwargs: object):
        nonlocal reached
        result = await original(self, *args, **kwargs)
        async with gate:
            reached += 1
            if reached == 2:
                both_checked.set()
        await asyncio.wait_for(both_checked.wait(), timeout=10)
        return result

    monkeypatch.setattr(BookingService, "_patient_double_booked", synchronized_precheck)
    app = FastAPI()
    app.include_router(booking_router.router, prefix="/api/v1")
    app.dependency_overrides[booking_router._BOOKING_GUARD] = lambda: identity
    app.dependency_overrides[get_db_pool] = lambda: pool
    app.dependency_overrides[idempotency_guard] = lambda: IdempotencyGuard()
    captured: list[dict[str, str | None]] = []

    @app.exception_handler(asyncpg.UniqueViolationError)
    async def observe_unique_violation(
        request: Request, exc: asyncpg.UniqueViolationError
    ) -> JSONResponse:
        del request
        captured.append(
            {
                "type": type(exc).__name__,
                "constraint": getattr(exc, "constraint_name", None),
            }
        )
        return JSONResponse(
            status_code=500,
            content={"exception_type": type(exc).__name__},
        )

    body = {
        "clinic_patient_id": str(patient_id),
        "service_type_id": str(service_id),
        "location_id": str(loc),
        "slot_start": start.astimezone(UTC).isoformat(),
        "slot_end": (start + timedelta(minutes=15)).astimezone(UTC).isoformat(),
    }
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://audit.local",
    ) as client:
        responses = await asyncio.gather(
            client.post("/api/v1/appointments/bookings", json=body),
            client.post("/api/v1/appointments/bookings", json=body),
        )

    statuses = sorted(response.status_code for response in responses)
    response_bodies = [response.text for response in responses]
    async with pool.acquire() as conn:
        appointments = await conn.fetchval(
            "SELECT count(*) FROM appointment WHERE clinic_id=$1::uuid"
            " AND clinic_patient_id=$2::uuid AND slot_start=$3",
            CLINIC,
            patient_id,
            start.astimezone(UTC),
        )
        episodes = await conn.fetchval(
            "SELECT count(*) FROM care_episode WHERE clinic_id=$1::uuid"
            " AND clinic_patient_id=$2::uuid AND service_type_id=$3::uuid"
            " AND status <> 'CLOSED'",
            CLINIC,
            patient_id,
            service_id,
        )

    print(json.dumps({
        "probe": "concurrent_same_patient_same_slot_via_booking_router",
        "http_statuses": statuses,
        "response_bodies": response_bodies,
        "captured_database_exception": captured,
        "appointments_after": appointments,
        "live_episodes_after": episodes,
    }, ensure_ascii=False))
    assert statuses == [201, 500]
    assert len(captured) == 1
    assert captured[0]["type"] == "UniqueViolationError"
    assert captured[0]["constraint"] == "uq_appointment_patient_slot_live"
    assert appointments == 1
    assert episodes == 1
