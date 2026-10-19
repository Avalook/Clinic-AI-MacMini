"""Bảo đảm nhật ký giới hạn theo ngày Việt Nam và bao trọn ngày đó."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.audit_log_service import AuditLogService, _day_bounds_vn


def test_day_bounds_use_vietnam_date_when_utc_is_previous_day() -> None:
    now = datetime(2026, 10, 18, 17, 30, tzinfo=timezone.utc)

    start, end = _day_bounds_vn(now)

    assert start.isoformat() == "2026-10-19T00:00:00+07:00"
    assert end == start + timedelta(days=1)


def test_day_bounds_accept_explicit_vietnam_day() -> None:
    start, end = _day_bounds_vn(date(2026, 10, 18))

    assert start.isoformat() == "2026-10-18T00:00:00+07:00"
    assert end.isoformat() == "2026-10-19T00:00:00+07:00"


@pytest.mark.asyncio
async def test_events_keeps_more_than_two_hundred_rows_for_the_day() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": f"event-{index}",
            "occurred_at": now,
            "event_type": "patient.updated",
            "aggregate_type": "patient",
            "aggregate_id": None,
            "payload": None,
            "actor_name": "Nhân viên",
            "actor_role": "CSKH",
            "actor_staff_id": "11111111-1111-4111-8111-111111111111",
            "nguon_thao_tac": "api:patient",
            "subject_name": None,
            "subject_code": None,
            "subject_kind": None,
            "subject_ref_name": None,
        }
        for index in range(250)
    ]
    pool = SimpleNamespace(fetch=AsyncMock(return_value=rows))
    identity = StaffIdentity(
        staff_id="11111111-1111-4111-8111-111111111111",
        auth_user_id="22222222-2222-4222-8222-222222222222",
        full_name="Nhân viên test",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )

    result = await AuditLogService(pool).events(identity=identity)

    assert len(result["items"]) == 250
    args = pool.fetch.await_args.args
    assert len(args) == 4
    assert args[1] == identity.clinic_id
    assert args[3] - args[2] == timedelta(days=1)
    assert args[2].tzinfo is not None

    query = args[0].upper()
    assert "LIMIT" not in query
    assert "OFFSET" not in query
