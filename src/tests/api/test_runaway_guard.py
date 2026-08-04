"""The runaway guard warns long before it refuses, and stays out of the way.

It exists to make a client-side loop VISIBLE, not to police staff. Everything
asserted here follows from that one intent:

  * a person working normally never meets it;
  * a loop is reported (WARNING) while its requests are still landing, not only
    once they start failing;
  * the report is not itself a flood;
  * and when its own bookkeeping runs out of room it lets requests THROUGH,
    because refusing a nurse a patient record to protect a counter would be a
    worse outage than the one being prevented.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.runaway_guard import RunawayRequestGuard


class _Clock:
    """Time under test control; the guard is a sliding window over it."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def _identity(staff_id: str = "s1") -> StaffIdentity:
    return StaffIdentity(
        staff_id=staff_id,
        auth_user_id=f"u-{staff_id}",
        full_name="Test",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _Request:
    """Minimal stand-in: the guard only reads `method` and the route scope."""

    method = "GET"
    scope: dict[str, object] = {}


async def _hit(guard: RunawayRequestGuard, ident: StaffIdentity, times: int) -> int:
    """Send `times` requests, return how many were refused with 429."""
    refused = 0
    for _ in range(times):
        try:
            await guard(_Request(), ident)  # type: ignore[arg-type]
        except HTTPException as exc:
            assert exc.status_code == 429
            refused += 1
    return refused


@pytest.mark.asyncio
async def test_normal_work_is_never_touched() -> None:
    """Twenty requests a minute is a busy receptionist. Nothing should happen."""
    clock = _Clock()
    guard = RunawayRequestGuard(ceiling=120, window_seconds=60, clock=clock)
    assert await _hit(guard, _identity(), 20) == 0


@pytest.mark.asyncio
async def test_it_refuses_only_past_the_ceiling() -> None:
    """The 121st request in the window is the first one refused."""
    clock = _Clock()
    guard = RunawayRequestGuard(ceiling=120, window_seconds=60, clock=clock)
    assert await _hit(guard, _identity(), 120) == 0
    assert await _hit(guard, _identity(), 1) == 1


@pytest.mark.asyncio
async def test_the_window_slides() -> None:
    """A loop that stops is forgiven; the ceiling is per minute, not per session."""
    clock = _Clock()
    guard = RunawayRequestGuard(ceiling=10, window_seconds=60, clock=clock)
    assert await _hit(guard, _identity(), 10) == 0
    assert await _hit(guard, _identity(), 1) == 1

    clock.now += 61  # the whole window has aged out
    assert await _hit(guard, _identity(), 10) == 0


@pytest.mark.asyncio
async def test_one_persons_loop_does_not_refuse_anybody_else() -> None:
    """Buckets are per staff member — a bug on one screen is not an outage."""
    clock = _Clock()
    guard = RunawayRequestGuard(ceiling=10, window_seconds=60, clock=clock)
    await _hit(guard, _identity("looping"), 20)
    assert await _hit(guard, _identity("working"), 10) == 0


@pytest.mark.asyncio
async def test_the_warning_fires_before_anything_is_refused() -> None:
    """Half the ceiling, so the loop is reported while its requests still land.

    Noticing at the ceiling would be too late: by then the client is already
    getting 429s, which is the symptom rather than the evidence.
    """
    clock = _Clock()
    guard = RunawayRequestGuard(ceiling=10, window_seconds=60, clock=clock)
    warned_at = None
    for i in range(1, 11):
        _, should_warn = guard._record("k", clock())
        if should_warn and warned_at is None:
            warned_at = i
    assert warned_at == 5  # ceiling // 2, and well below the 10 that refuses


@pytest.mark.asyncio
async def test_the_warning_is_not_itself_a_flood() -> None:
    """One line per actor per window.

    Without this the runaway loop that triggered the warning also writes a
    warning per request, and the log becomes as unreadable as the problem it was
    supposed to report.
    """
    clock = _Clock()
    guard = RunawayRequestGuard(ceiling=10, window_seconds=60, clock=clock)
    warnings = sum(guard._record("k", clock())[1] for _ in range(50))
    assert warnings == 1

    clock.now += 61
    assert sum(guard._record("k", clock())[1] for _ in range(50)) == 1


@pytest.mark.asyncio
async def test_it_fails_open_when_out_of_room() -> None:
    """Full bucket table lets requests THROUGH.

    The opposite choice belongs in rate_limit.py, where every admitted call costs
    real money. Here an admitted call costs nothing and a refused one may cost a
    patient their record.
    """
    clock = _Clock()
    guard = RunawayRequestGuard(
        ceiling=1, window_seconds=60, max_buckets=2, clock=clock
    )
    for i in range(5):
        guard._record(f"actor-{i}", clock())
    # Whatever happened to the table, a fresh actor is not refused.
    assert await _hit(guard, _identity("newcomer"), 1) == 0
