"""Sinh hiệu KHÔNG còn là cửa (luồng chuẩn bước 6, Tuyền chốt 23/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_sinh_hieu_khong_chan_db.py

"Có đo cũng chả sao, vẫn có event phát ra cho điều dưỡng, không làm cũng không
sai." Check-in xong khách hiện ngay ở hàng bác sĩ chính; điều dưỡng vẫn thấy
khách ở hàng đo sinh hiệu.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.services.booking_service import BookingService
from clinicai.services.luot_kham_service import LuotKhamService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _lich_hom_nay(
    pool: asyncpg.Pool,  # noqa: F811
) -> tuple[str, StaffIdentity, StaffIdentity, str]:
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
            " VALUES ($1::uuid, $2, 'BN không đo', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"SH-{uuid.uuid4().hex[:10]}",
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
    return str(appt), le_tan, bac_si, str(loc)


async def _hang_bac_si(pool: asyncpg.Pool, appt: str) -> list[str]:  # noqa: F811
    rows = await pool.fetch(
        "SELECT q.status FROM queue_entry q JOIN visit v ON v.visit_id = q.visit_id"
        " WHERE v.appointment_id = $1::uuid AND q.lane = 'DOCTOR'"
        "   AND q.status NOT IN ('done', 'left', 'cancelled')",
        appt,
    )
    return [r["status"] for r in rows]


async def test_check_in_xong_vao_ngay_hang_bac_si_chinh_du_chua_do(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    appt, le_tan, bac_si, _ = await _lich_hom_nay(pool)
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=le_tan
    )
    row = await pool.fetchrow(
        "SELECT f.vitals_status, f.route_decision,"
        " (SELECT count(*) FROM consultation c WHERE c.visit_id = v.visit_id) AS phien"
        " FROM visit v JOIN encounter_flow f ON f.visit_id = v.visit_id"
        " WHERE v.appointment_id = $1::uuid",
        appt,
    )
    assert row["vitals_status"] == "pending"  # chưa đo
    assert row["route_decision"] == "PRIMARY"
    assert row["phien"] == 1
    assert len(await _hang_bac_si(pool, appt)) == 1

    # Điều dưỡng vẫn thấy khách ở hàng đo sinh hiệu.
    ds = (await LuotKhamService(pool).bang(identity=bac_si))["luot"]
    vid = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    khach = [x for x in ds if x["visit_id"] == vid]
    assert khach and khach[0]["sinh_hieu"] is None


async def test_do_sau_van_duoc_khong_nhan_doi_hang(pool: asyncpg.Pool) -> None:  # noqa: F811
    appt, le_tan, _, loc = await _lich_hom_nay(pool)
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=le_tan
    )
    vid = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, loc, "NURSE_ULTRASOUND")
    svc = LuotKhamService(pool)
    await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=dd)
    await svc.record_vitals(
        visit_id=vid, raw={"systolic": 118, "diastolic": 76}, identity=dd
    )
    assert len(await _hang_bac_si(pool, appt)) == 1


async def test_check_in_lai_sau_hoan_tac_van_vao_hang_bac_si(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    appt, le_tan, _, _ = await _lich_hom_nay(pool)
    svc = BookingService(pool)
    await svc.apply_action(appointment_id=appt, action="checkin", identity=le_tan)
    await svc.apply_action(appointment_id=appt, action="undo_checkin", identity=le_tan)
    assert await _hang_bac_si(pool, appt) == []
    await svc.apply_action(appointment_id=appt, action="checkin", identity=le_tan)
    assert len(await _hang_bac_si(pool, appt)) == 1, (
        "check-in lại: khách phải về lại hàng bác sĩ chính"
    )
