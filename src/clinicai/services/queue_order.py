"""Authoritative CALL-order ranking for the clinic queue (Phase 4, cluster #5).

Ported from the frontend lib/queue.ts so the ranking rule lives in ONE place
(backend) instead of being duplicated/spoofable in TSX. Pure functions — no I/O.

Rule (Model ②, chốt 2026-06-26): the ticket number identifies a patient but does
NOT decide call order. Order tiers:
  -2  ƯT (người quen — priority ticket "ƯT1"…)   by ticket num
  -1  B3-ready (labs/ultrasound back → re-enter)   by arrival
   0  booked & arrived on time (≤ appt + 10' grace) by APPOINTMENT time
   1  walk-in / arrived late                        by ARRIVAL time
(pre-check-in rows fall back to plain ticket order.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

LATE_GRACE_MS = 10 * 60_000  # 10 minutes

_UT_RE = re.compile(r"(?:Ư|U)\s*T\s*0*(\d*)", re.IGNORECASE)
_INT_RE = re.compile(r"[+-]?\d+")


def _ms(d: datetime) -> int:
    return int(d.timestamp() * 1000)


def _iso(d: datetime | None) -> str:
    return d.isoformat() if d else ""


def _ut_num(queue_number: str | None) -> int | None:
    """ƯT ticket → its number (0 if bare 'ƯT'); None if not a ƯT ticket."""
    s = (queue_number or "").strip()
    m = _UT_RE.match(s)
    if m:
        return int(m.group(1)) if m.group(1) else 0
    return None


def queue_rank(queue_number: str | None, slot_iso: str) -> tuple[int, int, str]:
    """Plain ticket ordering: ƯT first, then numeric tickets, then the rest."""
    n = _ut_num(queue_number)
    if n is not None:
        return (0, n, slot_iso)
    m = _INT_RE.match((queue_number or "").strip())
    if m:
        return (1, int(m.group()), slot_iso)
    return (2, 0, slot_iso)


@dataclass(frozen=True)
class QueueEntry:
    appointment_id: str
    doctor_id: str | None
    queue_number: str | None
    slot_start: datetime
    checked_in_at: datetime | None
    booking_channel: str | None
    b3_ready: bool = False
    visit_status: str | None = None


def call_rank(e: QueueEntry) -> tuple[int, float, str]:
    """Sort key for a CHECKED-IN patient (lower = called sooner)."""
    slot_iso = _iso(e.slot_start)

    # -1: labs/ultrasound came back → re-enter ahead of the fresh queue.
    if e.b3_ready:
        in_ms = _ms(e.checked_in_at) if e.checked_in_at else _ms(e.slot_start)
        return (-1, in_ms, _iso(e.checked_in_at) or slot_iso)

    # Pre-check-in row with no channel/arrival → plain ticket order.
    if e.booking_channel is None and e.checked_in_at is None:
        return queue_rank(e.queue_number, slot_iso)

    # -2: ƯT (người quen).
    n = _ut_num(e.queue_number)
    if n is not None:
        return (-2, n, slot_iso)

    slot_ms = _ms(e.slot_start)
    is_booked = bool(e.booking_channel) and e.booking_channel != "WALK_IN"

    # 0: booked and arrived on time → ordered by appointment time.
    if is_booked and e.checked_in_at is not None:
        in_ms = _ms(e.checked_in_at)
        if in_ms <= slot_ms + LATE_GRACE_MS:
            return (0, float(slot_ms), _iso(e.checked_in_at))

    # 1: walk-in or late → ordered by arrival time.
    arrive_ms = _ms(e.checked_in_at) if e.checked_in_at else slot_ms
    return (1, float(arrive_ms), _iso(e.checked_in_at) or slot_iso)


def order_queue(entries: list[QueueEntry]) -> list[QueueEntry]:
    """Return entries sorted by call order (stable)."""
    return sorted(entries, key=call_rank)


def b3_ready_appt_ids(labs: list[dict[str, object]]) -> set[str]:
    """Appointment ids with ≥1 resulted lab and 0 pending (ready to re-enter).

    A lab is 'resulted' when it has a result_value or an external_ref.
    """
    resulted: dict[str, int] = {}
    pending: dict[str, int] = {}
    for lab in labs:
        appt = str(lab.get("appointment_id") or "")
        if not appt:
            continue
        has_result = bool(str(lab.get("result_value") or "").strip()) or bool(
            str(lab.get("external_ref") or "").strip()
        )
        (resulted if has_result else pending)[appt] = (
            (resulted if has_result else pending).get(appt, 0) + 1
        )
    return {
        appt
        for appt, n in resulted.items()
        if n > 0 and pending.get(appt, 0) == 0
    }
