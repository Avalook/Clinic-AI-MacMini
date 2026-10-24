"""Synthetic reproduction: routing and room-service configuration race.

The test pauses a real route assignment immediately after its production
eligibility check, applies the same clinic_room_service mapping change used by
ClinicConfigService.set_service_rooms, then resumes the assignment. All data is
created in the disposable DB provided by scripts/test-nhanh.sh.
"""

from __future__ import annotations

import asyncio

import pytest

from clinicai.services import service_routing_service as sr
from tests.services.test_service_routing_db import RB, _assign, _cd, rb

pytestmark = [pytest.mark.db, pytest.mark.asyncio]
pytest_plugins = ["tests.services.test_luot_kham_service_db"]


async def test_room_service_mapping_can_change_after_route_validates_room(
    rb: RB, monkeypatch: pytest.MonkeyPatch
) -> None:
    oid = await _cd(rb)
    service_code = await rb.pool.fetchval(
        "SELECT service_code FROM service_order WHERE id = $1::uuid", oid
    )
    checked = asyncio.Event()
    resume = asyncio.Event()
    original = sr.ServiceRoutingService._kiem_phong

    async def pause_after_eligibility_check(conn, cid, rid, order, location=None):
        await original(conn, cid, rid, order, location)
        checked.set()
        await resume.wait()

    monkeypatch.setattr(
        sr.ServiceRoutingService, "_kiem_phong", staticmethod(pause_after_eligibility_check)
    )
    assign_task = asyncio.create_task(_assign(rb, oid, rb.sa1, 0))
    try:
        await asyncio.wait_for(checked.wait(), timeout=5)

        # set_service_rooms narrows this service to sa2. It locks service_price,
        # then changes clinic_room_service; it does not lock the route's room.
        async with rb.pool.acquire() as writer, writer.transaction():
            await writer.fetchval(
                "SELECT id FROM service_price WHERE clinic_id = $1::uuid"
                " AND service_code = $2 AND \"group\" = 'dich_vu' FOR UPDATE",
                rb.truong_ca.clinic_id,
                service_code,
            )
            await writer.execute(
                "INSERT INTO clinic_room_service (clinic_id, room_id, service_code)"
                " VALUES ($1::uuid, $2::uuid, $3)",
                rb.truong_ca.clinic_id,
                rb.sa2,
                service_code,
            )

        still_eligible = await rb.pool.fetchval(
            "SELECT phong_lam_duoc($1::uuid, $2::uuid, $3, $4)",
            rb.truong_ca.clinic_id,
            rb.sa1,
            "DICHVU-SIEUAM",
            service_code,
        )
        assert still_eligible is False
    finally:
        resume.set()

    result = await asyncio.wait_for(assign_task, timeout=5)
    assert result["room_id"] == rb.sa1
    assert result["routing_status"] == "ASSIGNED"

