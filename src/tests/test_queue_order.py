"""Unit tests for the authoritative queue call-order (Phase 4, cluster #5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from clinicai.services.queue_order import (
    QueueEntry,
    b3_ready_appt_ids,
    call_rank,
    order_queue,
    queue_rank,
)

UTC = timezone.utc
SLOT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def _e(
    appt: str,
    *,
    qn: str | None = None,
    checked_in: datetime | None = None,
    channel: str | None = None,
    b3: bool = False,
    slot: datetime = SLOT,
) -> QueueEntry:
    return QueueEntry(
        appointment_id=appt,
        doctor_id="d1",
        queue_number=qn,
        slot_start=slot,
        checked_in_at=checked_in,
        booking_channel=channel,
        b3_ready=b3,
    )


# --------------------------- queue_rank --------------------------- #
def test_queue_rank_ut_numeric_other() -> None:
    assert queue_rank("ƯT1", "s")[:2] == (0, 1)
    assert queue_rank("ƯT", "s")[:2] == (0, 0)
    assert queue_rank("12", "s")[:2] == (1, 12)
    assert queue_rank("abc", "s")[:2] == (2, 0)
    assert queue_rank(None, "s")[:2] == (2, 0)


# --------------------------- call_rank tiers --------------------------- #
def test_ut_is_top_priority_tier_minus2() -> None:
    e = _e("a", qn="ƯT2", channel="HOTLINE", checked_in=SLOT)
    assert call_rank(e)[0] == -2
    assert call_rank(e)[1] == 2


def test_b3_ready_tier_minus1() -> None:
    e = _e("a", channel="HOTLINE", checked_in=SLOT, b3=True)
    assert call_rank(e)[0] == -1


def test_booked_on_time_tier0_by_appt() -> None:
    e = _e("a", channel="ZALO", checked_in=SLOT + timedelta(minutes=8))
    r = call_rank(e)
    assert r[0] == 0
    assert r[1] == SLOT.timestamp() * 1000  # ordered by APPOINTMENT time


def test_booked_late_falls_to_tier1_by_arrival() -> None:
    arrive = SLOT + timedelta(minutes=20)  # > 10' grace
    e = _e("a", channel="ZALO", checked_in=arrive)
    r = call_rank(e)
    assert r[0] == 1
    assert r[1] == arrive.timestamp() * 1000


def test_walkin_tier1_by_arrival() -> None:
    arrive = SLOT + timedelta(minutes=5)
    e = _e("a", channel="WALK_IN", checked_in=arrive)
    r = call_rank(e)
    assert r[0] == 1
    assert r[1] == arrive.timestamp() * 1000


def test_pre_checkin_falls_back_to_ticket_order() -> None:
    e = _e("a", qn="7", channel=None, checked_in=None)
    assert call_rank(e)[:2] == (1, 7)


# --------------------------- full ordering --------------------------- #
def test_order_queue_priority_sequence() -> None:
    ut = _e("ut", qn="ƯT1", channel="HOTLINE", checked_in=SLOT)
    b3 = _e("b3", channel="ZALO", checked_in=SLOT, b3=True)
    booked = _e("bk", channel="ZALO", checked_in=SLOT + timedelta(minutes=5))
    walkin = _e("wk", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=2))
    late = _e("lt", channel="ZALO", checked_in=SLOT + timedelta(minutes=30))
    order = [e.appointment_id for e in order_queue([late, walkin, booked, b3, ut])]
    # ƯT(-2) < b3(-1) < booked(0) < walk-in/late(1, by arrival: walkin 9:02 < late 9:30)
    assert order == ["ut", "b3", "bk", "wk", "lt"]


# --------------------------- b3_ready_appt_ids --------------------------- #
def test_b3_ready_requires_all_resulted() -> None:
    labs: list[dict[str, object]] = [
        {"appointment_id": "a", "result_value": "5.2", "external_ref": None},
        {"appointment_id": "a", "result_value": None, "external_ref": "LIS-9"},
        {"appointment_id": "b", "result_value": "1", "external_ref": None},
        {"appointment_id": "b", "result_value": "  ", "external_ref": None},  # pending
        {"appointment_id": "c", "result_value": None, "external_ref": None},  # pending
    ]
    ready = b3_ready_appt_ids(labs)
    assert ready == {"a"}  # a: all resulted; b: 1 pending; c: none resulted
