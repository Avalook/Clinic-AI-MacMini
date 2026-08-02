"""Capacity quote service — CAP-01 budget + slot usage (Phase 4, cluster #1).

Ported from ``src/dashboard/lib/capacity.ts`` and ``src/dashboard/app/api/
appointments/quote/route.ts`` so the budget/usage calculation lives in ONE
place (backend) instead of being duplicated/spoofable in TSX.

The rule (Decision Doc v2): each doctor × hour has a *budget* (thanh_min,
sono_min, online_quota, walkin_quota, new_cap, max_total). The quote endpoint
returns the budget + current usage per hour so the UI can colour cells; it
does NOT decide whether a booking is allowed — that is the DB trigger + the
pre-check in BookingService.

Pure functions (``resolve_budget``, ``usage_of``, ``cell_state``) are exported
for unit testing; ``CapacityService.quote`` does the I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

import asyncpg
import structlog

logger = structlog.get_logger()

CLINIC_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

FALLBACK_THANH_MIN = 12  # V2#9 — conservative default for legacy NULL thanh_min


@dataclass(frozen=True)
class BudgetRow:
    location_id: str
    doctor_id: str | None
    weekday: int | None
    hour_start: int
    thanh_budget_min: int
    sono_budget_min: int
    online_quota_min: int
    walkin_quota_min: int
    buffer_min: int
    new_cap: int
    max_total: int


@dataclass(frozen=True)
class ApptLite:
    patient_kind: str | None
    thanh_min: int | None
    booking_channel: str | None


@dataclass(frozen=True)
class Usage:
    thanh: int
    online: int
    walkin: int
    new_count: int
    total: int


CellState = Literal[
    "free",
    "few",
    "return_only",
    "full_thanh",
    "walkin_hold",
    "locked",
]


def is_walkin(channel: str | None) -> bool:
    return (channel or "").strip().upper() == "WALK_IN"


def load_of_appt(a: ApptLite) -> int:
    """Thanh load of one appointment; COALESCE NULL → fallback (V2#9)."""
    return a.thanh_min if a.thanh_min is not None else FALLBACK_THANH_MIN


def is_new_explicit(a: ApptLite) -> bool:
    """Only count ca with patient_kind === 'NEW' toward new_cap."""
    return a.patient_kind == "NEW"


def usage_of(existing: list[ApptLite]) -> Usage:
    """Aggregate current load of one hour-block."""
    thanh = 0
    online = 0
    walkin = 0
    new_count = 0
    for a in existing:
        load = load_of_appt(a)
        thanh += load
        if is_walkin(a.booking_channel):
            walkin += load
        else:
            online += load
        if is_new_explicit(a):
            new_count += 1
    return Usage(
        thanh=thanh,
        online=online,
        walkin=walkin,
        new_count=new_count,
        total=len(existing),
    )


def cell_state(budget: BudgetRow, u: Usage) -> CellState:
    """Display state for a cell — NOT the booking decision."""
    if u.total >= budget.max_total:
        return "locked"
    if u.thanh >= budget.thanh_budget_min:
        return "full_thanh"
    if u.new_count >= budget.new_cap:
        return "return_only"
    if u.online >= budget.online_quota_min and u.walkin < budget.walkin_quota_min:
        return "walkin_hold"
    if u.thanh >= budget.thanh_budget_min - 10:
        return "few"
    return "free"


def resolve_budget(
    rows: list[BudgetRow],
    key: dict[str, Any],
) -> BudgetRow | None:
    """DEC-8 — pick the most-specific budget row; None ⇒ fail-open.

    Specificity decreases: doctor+weekday > doctor > location+weekday > location.
    """
    at_loc = [
        r
        for r in rows
        if r.location_id == key["location_id"] and r.hour_start == key["hour_start"]
    ]

    def pick(doc_match: bool, wd_match: bool) -> BudgetRow | None:
        for r in at_loc:
            if doc_match:
                if r.doctor_id != key["doctor_id"]:
                    continue
            else:
                if r.doctor_id is not None:
                    continue
            if wd_match:
                if r.weekday != key["weekday"]:
                    continue
            else:
                if r.weekday is not None:
                    continue
            return r
        return None

    if key["doctor_id"]:
        return (
            pick(True, True)
            or pick(True, False)
            or pick(False, True)
            or pick(False, False)
        )
    return pick(False, True) or pick(False, False)


def vn_block_of(slot_start_iso: str) -> dict[str, int]:
    """VN weekday + hour of a UTC ISO timestamp.

    weekday: 0=CN .. 6=T7 (matches block_budget.weekday).
    """
    d = datetime.fromisoformat(slot_start_iso.replace("Z", "+00:00"))
    # Format in VN timezone
    vn = d.astimezone(CLINIC_TZ)
    # Python weekday(): Mon=0..Sun=6 → convert to 0=CN..6=T7
    weekday = (vn.weekday() + 1) % 7  # Mon=0 → 1, Sun=6 → 0
    return {"weekday": weekday, "hour_start": vn.hour}


class CapacityService:
    """Read-only capacity quote for the slot picker UI."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def quote(
        self,
        *,
        date: str,
        location_id: str,
        doctor_id: str | None,
        clinic_id: str,
    ) -> dict[str, Any]:
        """Return budget + usage per hour for a date/location[/doctor].

        ``date`` is a VN date string ``YYYY-MM-DD``.
        """
        # VN weekday of the date (midday to avoid edge offset issues)
        midday_iso = f"{date}T12:00:00+07:00"
        block = vn_block_of(midday_iso)
        weekday = block["weekday"]

        start_of_day = f"{date}T00:00:00+07:00"
        end_of_day = f"{date}T23:59:59+07:00"

        async with self._pool.acquire() as conn:
            # Read block_budget rows for this location (tenant-scoped).
            budget_rows_raw = await conn.fetch(
                """
                SELECT location_id, doctor_id, weekday, hour_start,
                       thanh_budget_min, sono_budget_min, online_quota_min,
                       walkin_quota_min, buffer_min, new_cap, max_total
                  FROM block_budget
                 WHERE location_id = $1::uuid
                   AND clinic_id = $2::uuid
                """,
                location_id,
                clinic_id,
            )

            # Read appointments for this location on this date.
            if doctor_id:
                appt_rows = await conn.fetch(
                    """
                    SELECT slot_start, patient_kind, thanh_min, booking_channel
                      FROM appointment
                     WHERE clinic_id = $3::uuid
                       AND location_id = $1::uuid
                       AND doctor_id = $2::uuid
                       AND slot_start >= $4
                       AND slot_start <= $5
                       AND status NOT IN ('CANCELLED', 'NO_SHOW')
                    """,
                    location_id,
                    doctor_id,
                    clinic_id,
                    start_of_day,
                    end_of_day,
                )
            else:
                appt_rows = await conn.fetch(
                    """
                    SELECT slot_start, patient_kind, thanh_min, booking_channel
                      FROM appointment
                     WHERE clinic_id = $2::uuid
                       AND location_id = $1::uuid
                       AND slot_start >= $3
                       AND slot_start <= $4
                       AND status NOT IN ('CANCELLED', 'NO_SHOW')
                    """,
                    location_id,
                    clinic_id,
                    start_of_day,
                    end_of_day,
                )

        # Parse budget rows
        budget_rows: list[BudgetRow] = [
            BudgetRow(
                location_id=str(r["location_id"]),
                doctor_id=str(r["doctor_id"]) if r["doctor_id"] else None,
                weekday=r["weekday"],
                hour_start=r["hour_start"],
                thanh_budget_min=r["thanh_budget_min"],
                sono_budget_min=r["sono_budget_min"],
                online_quota_min=r["online_quota_min"],
                walkin_quota_min=r["walkin_quota_min"],
                buffer_min=r["buffer_min"],
                new_cap=r["new_cap"],
                max_total=r["max_total"],
            )
            for r in budget_rows_raw
        ]

        # Group appointments by VN hour
        by_hour: dict[int, list[ApptLite]] = {}
        for r in appt_rows:
            slot_iso = (
                r["slot_start"].isoformat()
                if hasattr(r["slot_start"], "isoformat")
                else str(r["slot_start"])
            )
            block = vn_block_of(slot_iso)
            hour = block["hour_start"]
            arr = by_hour.get(hour, [])
            arr.append(
                ApptLite(
                    patient_kind=r["patient_kind"],
                    thanh_min=r["thanh_min"],
                    booking_channel=r["booking_channel"],
                )
            )
            by_hour[hour] = arr

        # Return every hour_start that has a budget config at this location
        hours = sorted(set(r.hour_start for r in budget_rows))
        blocks_out = []
        for hour_start in hours:
            budget = resolve_budget(
                budget_rows,
                {
                    "location_id": location_id,
                    "doctor_id": doctor_id,
                    "weekday": weekday,
                    "hour_start": hour_start,
                },
            )
            existing = by_hour.get(hour_start, [])
            u = usage_of(existing)
            blocks_out.append(
                {
                    "hour_start": hour_start,
                    "budget": _budget_to_dict(budget) if budget else None,
                    "usage": _usage_to_dict(u),
                    "state": cell_state(budget, u) if budget else "free",
                }
            )

        return {
            "date": date,
            "location_id": location_id,
            "doctor_id": doctor_id,
            "weekday": weekday,
            "blocks": blocks_out,
        }


def _budget_to_dict(b: BudgetRow) -> dict[str, Any]:
    return {
        "location_id": b.location_id,
        "doctor_id": b.doctor_id,
        "weekday": b.weekday,
        "hour_start": b.hour_start,
        "thanh_budget_min": b.thanh_budget_min,
        "sono_budget_min": b.sono_budget_min,
        "online_quota_min": b.online_quota_min,
        "walkin_quota_min": b.walkin_quota_min,
        "buffer_min": b.buffer_min,
        "new_cap": b.new_cap,
        "max_total": b.max_total,
    }


def _usage_to_dict(u: Usage) -> dict[str, Any]:
    return {
        "thanh": u.thanh,
        "online": u.online,
        "walkin": u.walkin,
        "new_count": u.new_count,
        "total": u.total,
    }
