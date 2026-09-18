"""Check-in → hoàn tác → check-in lại, trên Postgres thật.

Bắt được khi bấm thật trên final cloud 18/09/2026: hoàn tác đưa lượt khám về
INCOMPLETE, và lần check-in sau gặp ``ON CONFLICT DO NOTHING`` nên lượt cũ
nằm im INCOMPLETE. Khách đứng trong hàng đợi lễ tân mà màn bác sĩ — lọc
``status IN ('OPEN','IN_PROGRESS')`` — không bao giờ thấy.

    DATABASE_URL_TEST=postgresql://postgres:$P@127.0.0.1:54422/postgres \\
        poetry run pytest src/tests/services/test_check_in_lai_sau_hoan_tac_db.py
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.booking_service import BookingService

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


async def _nguoi(conn: asyncpg.Connection, loc: str, role: str) -> StaffIdentity:
    ten = f"Test {role} {uuid.uuid4().hex[:6]}"
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        CLINIC,
        sid,
        role,
    )
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


async def test_check_in_lai_sau_hoan_tac_mo_lai_luot_kham(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        le_tan = await _nguoi(conn, loc, "RECEPTION")
        bac_si = await _nguoi(conn, loc, "DOCTOR")
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN check-in lại', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"CIL-{uuid.uuid4().hex[:10]}",
            loc,
        )
        dv = await conn.fetchval(
            "SELECT id::text FROM service_type WHERE is_active ORDER BY code LIMIT 1"
        )
        bd = datetime.now(UTC) + timedelta(minutes=30)
        appt = await conn.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, doctor_id, status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
            " 'CONFIRMED') RETURNING id::text",
            CLINIC,
            pid,
            loc,
            dv,
            bd,
            bd + timedelta(minutes=15),
            bac_si.staff_id,
        )

    svc = BookingService(pool)
    await svc.apply_action(appointment_id=appt, action="checkin", identity=le_tan)
    await svc.apply_action(appointment_id=appt, action="undo_checkin", identity=le_tan)

    async with pool.acquire() as conn:
        sau_hoan_tac = await conn.fetchval(
            "SELECT status FROM visit WHERE appointment_id = $1::uuid", appt
        )
    assert sau_hoan_tac == "INCOMPLETE"

    await svc.apply_action(appointment_id=appt, action="checkin", identity=le_tan)

    async with pool.acquire() as conn:
        luot = await conn.fetch(
            "SELECT status, incomplete_reason, incomplete_at FROM visit"
            " WHERE appointment_id = $1::uuid",
            appt,
        )
        lich = await conn.fetchval(
            "SELECT status FROM appointment WHERE id = $1::uuid", appt
        )
    assert lich == "CHECKED_IN"
    assert len(luot) == 1, "check-in lại phải dùng đúng lượt cũ, không mở lượt thứ hai"
    # Như một lần check-in mới: lượt mở rồi được xếp vào trạm đầu (IN_PROGRESS).
    assert luot[0]["status"] in ("OPEN", "IN_PROGRESS"), (
        "lượt khám phải mở lại — INCOMPLETE thì màn bác sĩ không thấy khách"
    )
    assert luot[0]["incomplete_reason"] is None
    assert luot[0]["incomplete_at"] is None
