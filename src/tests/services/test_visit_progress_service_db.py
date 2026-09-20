"""Kiểm tra VisitProgressService trên PostgreSQL thật với cả 2 trường hợp:
1. Lượt khám có lịch hẹn (appointment_id != NULL).
2. Lượt khám walk-in / không có lịch hẹn (appointment_id IS NULL).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.core.clock import CLINIC_TZ as _VN
from clinicai.services.visit_progress_service import VisitProgressService
from tests.services.test_luot_kham_service_db import CLINIC

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_TEST") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


async def test_visit_progress_db_appointmentless_and_appointment(
    pool: asyncpg.Pool,
) -> None:
    """Kiểm tra query _PROGRESS_SQL thật trên DB:
    - Visit 1 có appointment, payment PAID -> appointment_id và paid_kinds.
    - Visit 2 không appointment (walk-in), payment PAID -> appointment_id None.
    - Visit 3 có payment VOIDED -> không tính vào paid_kinds.
    """
    svc = VisitProgressService(pool)
    hom_nay = datetime.now(_VN).date()

    # 1. Tạo bệnh nhân test
    loc_id = await pool.fetchval(
        "SELECT primary_location_id FROM staff "
        "WHERE primary_location_id IS NOT NULL LIMIT 1"
    ) or str(uuid.uuid4())
    pid = str(uuid.uuid4())
    code = f"BN-PROG-{uuid.uuid4().hex[:6]}"
    await pool.execute(
        """
        INSERT INTO patient (
            clinic_patient_id, clinic_id, location_id,
            patient_code, full_name, phone_primary, gender
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid,
            $4, 'BN Test Progress', '0912345678', 'Nữ'
        )
        """,
        pid,
        CLINIC,
        loc_id,
        code,
    )

    # 2. Tạo appointment cho Visit 1
    aid1 = str(uuid.uuid4())
    slot = datetime.now(_VN)
    dv_id = await pool.fetchval(
        "SELECT id::text FROM service_type WHERE is_active ORDER BY code LIMIT 1"
    )
    await pool.execute(
        """
        INSERT INTO appointment (
            id, clinic_id, clinic_patient_id, location_id,
            service_type_id, slot_start, slot_end, status
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4::uuid,
            $5::uuid, $6::timestamptz,
            $6::timestamptz + interval '30 minutes', 'CHECKED_IN'
        )
        """,
        aid1,
        CLINIC,
        pid,
        loc_id,
        dv_id,
        slot,
    )

    # 3. Tạo Visit 1 (có appointment)
    vid1 = str(uuid.uuid4())
    await pool.execute(
        """
        INSERT INTO visit (
            visit_id, clinic_id, clinic_patient_id,
            appointment_id, status, created_at
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'OPEN', now())
        """,
        vid1,
        CLINIC,
        pid,
        aid1,
    )
    # Payment PAID cho Visit 1
    pay1_id = str(uuid.uuid4())
    cycle1_id = str(uuid.uuid4())
    await pool.execute(
        """
        INSERT INTO payment_cycle (
            payment_cycle_id, clinic_id, visit_id,
            kind, amount, status, legacy, paid_at
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 200000, 'PAID', true, now())
        """,
        cycle1_id,
        CLINIC,
        vid1,
    )
    await pool.execute(
        """
        INSERT INTO payment (
            id, clinic_id, visit_id, payment_cycle_id,
            kind, amount, status, paid_at
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4::uuid,
            'dich_vu', 200000, 'PAID', now()
        )
        """,
        pay1_id,
        CLINIC,
        vid1,
        cycle1_id,
    )

    # 4. Tạo Visit 2 (walk-in, appointment_id = NULL)
    vid2 = str(uuid.uuid4())
    await pool.execute(
        """
        INSERT INTO visit (
            visit_id, clinic_id, clinic_patient_id,
            appointment_id, status, created_at
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, NULL, 'OPEN', now())
        """,
        vid2,
        CLINIC,
        pid,
    )
    # Payment PAID cho Visit 2
    pay2_id = str(uuid.uuid4())
    cycle2_id = str(uuid.uuid4())
    await pool.execute(
        """
        INSERT INTO payment_cycle (
            payment_cycle_id, clinic_id, visit_id,
            kind, amount, status, legacy, paid_at
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 300000, 'PAID', true, now())
        """,
        cycle2_id,
        CLINIC,
        vid2,
    )
    await pool.execute(
        """
        INSERT INTO payment (
            id, clinic_id, visit_id, payment_cycle_id,
            kind, amount, status, paid_at
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4::uuid,
            'dich_vu', 300000, 'PAID', now()
        )
        """,
        pay2_id,
        CLINIC,
        vid2,
        cycle2_id,
    )

    # 5. Tạo Visit 3 (walk-in, appointment_id = NULL) nhưng payment bị VOIDED
    vid3 = str(uuid.uuid4())
    await pool.execute(
        """
        INSERT INTO visit (
            visit_id, clinic_id, clinic_patient_id,
            appointment_id, status, created_at
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, NULL, 'OPEN', now())
        """,
        vid3,
        CLINIC,
        pid,
    )
    pay3_id = str(uuid.uuid4())
    cycle3_id = str(uuid.uuid4())
    await pool.execute(
        """
        INSERT INTO payment_cycle (
            payment_cycle_id, clinic_id, visit_id,
            kind, amount, status, legacy, paid_at, closed_at
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid,
            'dich_vu', 150000, 'VOIDED', true, now(), now()
        )
        """,
        cycle3_id,
        CLINIC,
        vid3,
    )
    staff_id = await pool.fetchval("SELECT id FROM staff LIMIT 1")
    await pool.execute(
        """
        INSERT INTO payment (
            id, clinic_id, visit_id, payment_cycle_id,
            kind, amount, status, paid_at, voided_at,
            voided_by_staff_id, void_reason
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4::uuid,
            'dich_vu', 150000, 'VOIDED', now(), now(),
            $5::uuid, 'Thu nhầm hoá đơn'
        )
        """,
        pay3_id,
        CLINIC,
        vid3,
        cycle3_id,
        staff_id,
    )

    # 6. Chạy for_range
    rows = await svc.for_range(date_from=hom_nay, date_to=hom_nay, clinic_id=CLINIC)
    by_visit = {r.visit_id: r for r in rows if r.visit_id}

    # Kiểm tra Visit 1 (có appointment)
    assert vid1 in by_visit, "Visit 1 (có appointment) phải có trong kết quả"
    r1 = by_visit[vid1]
    assert r1.appointment_id == aid1
    assert r1.paid_kinds == ["dich_vu"]
    assert r1.paid_at is not None

    # Kiểm tra Visit 2 (walk-in, không appointment)
    assert vid2 in by_visit, "Visit 2 (walk-in) PHẢI có trong kết quả tiến trình"
    r2 = by_visit[vid2]
    assert r2.appointment_id is None, "appointment_id phải là None đối với lượt walk-in"
    assert r2.paid_kinds == ["dich_vu"], "paid_kinds phải chứa dich_vu"
    assert r2.paid_at is not None

    # Kiểm tra Visit 3 (payment VOIDED)
    assert vid3 in by_visit, "Visit 3 phải có trong kết quả"
    r3 = by_visit[vid3]
    assert r3.paid_kinds == [], "Payment VOIDED không được tính vào paid_kinds"
    assert r3.paid_at is None, "Payment VOIDED không được có paid_at"
