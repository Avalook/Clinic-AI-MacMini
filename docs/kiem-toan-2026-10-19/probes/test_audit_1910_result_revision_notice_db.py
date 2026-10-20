"""Audit: a later result correction must survive hiding an earlier notice."""

# ruff: noqa: F811 -- imported fixture follows the repository convention.

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import asyncpg
import pytest

from clinicai.events.consumers.chuong import bao_chuong
from clinicai.events.worker import SuKienDaNhan
from clinicai.services.thong_bao_service import ThongBaoService
from tests.services.test_phieu_kham_db import _chuan_bi, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_new_correction_remains_visible_after_previous_notice_hidden(
    pool: asyncpg.Pool,
) -> None:
    doctor, visit = await _chuan_bi(pool)
    await pool.execute(
        "UPDATE visit SET attending_doctor_id=$1::uuid WHERE visit_id=$2::uuid",
        doctor.staff_id,
        visit["visit"],
    )
    result = str(uuid.uuid4())
    event = SuKienDaNhan(
        event_id=str(uuid.uuid4()),
        event_type="result.corrected",
        clinic_id=doctor.clinic_id,
        aggregate_id=result,
        aggregate_version=2,
        occurred_at=datetime.now(UTC),
        seq=1,
        actor_type="HUMAN",
        actor_staff_id=doctor.staff_id,
        payload={
            "visit_id": visit["visit"],
            "service_order_id": str(uuid.uuid4()),
            "form_id": "AUDIT",
            "form_version": 1,
            "ban_thu": 2,
        },
        replay_id=None,
        attempts=0,
    )
    async with pool.acquire() as conn, conn.transaction():
        await bao_chuong(conn, event)
    notices = ThongBaoService(pool)
    first = await notices.cua_toi(identity=doctor)
    assert first, "Initial correction notice must be present"
    await notices.an_tat_ca_cua_toi(identity=doctor)
    assert not await notices.cua_toi(identity=doctor)
    later = replace(
        event,
        event_id=str(uuid.uuid4()),
        aggregate_version=3,
        seq=2,
        payload={**event.payload, "ban_thu": 3},
    )
    async with pool.acquire() as conn, conn.transaction():
        await bao_chuong(conn, later)
    current = await notices.cua_toi(identity=doctor)
    assert current, (
        "A different result revision was deduplicated into a hidden notice"
    )
