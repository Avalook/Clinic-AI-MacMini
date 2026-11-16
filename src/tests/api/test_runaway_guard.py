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


# --- Đo prod 13–16/11/2026: người thật làm việc bình thường lên tới 443 lượt/phút ---
#
# Không phải vòng lặp: mỗi lượt ghi ở bất kỳ đâu làm MỌI tab đang mở hỏi lại
# (layout 7 lời gọi + ~10 hook `useNgheBang` ở bàn khám). Trần 400 trả 1.834 lượt
# 429 cho nhân viên trong 2,6 ngày. Tuyền chốt 16/11: chặn ở 1000, cảnh báo ở 200.


class _Route:
    def __init__(self, path: str) -> None:
        self.path = path


class _RequestAt:
    """Request đã khớp một route — bộ canh đọc `scope["route"].path`."""

    method = "GET"

    def __init__(self, path: str | None) -> None:
        self.scope: dict[str, object] = {} if path is None else {"route": _Route(path)}


class _Recorder:
    """Thay `logger` của module: bắt cảnh báo, không phụ thuộc cấu hình structlog."""

    def __init__(self) -> None:
        self.warnings: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kw: object) -> None:
        self.warnings.append((event, kw))

    def error(self, event: str, **kw: object) -> None:
        pass


async def _goi(
    guard: RunawayRequestGuard, ident: StaffIdentity, path: str | None, times: int
) -> int:
    refused = 0
    for _ in range(times):
        try:
            await guard(_RequestAt(path), ident)  # type: ignore[arg-type]
        except HTTPException as exc:
            assert exc.status_code == 429
            refused += 1
    return refused


@pytest.mark.asyncio
async def test_default_ceiling_admits_the_measured_human_peak() -> None:
    """443/phút là đỉnh đo được của người thật — không bị 429. Chặn từ lượt 1001."""
    from clinicai.api.runaway_guard import DEFAULT_CEILING

    assert DEFAULT_CEILING == 1000
    guard = RunawayRequestGuard(clock=_Clock())
    assert await _hit(guard, _identity(), 1000) == 0
    assert await _hit(guard, _identity(), 1) == 1


@pytest.mark.asyncio
async def test_default_guard_warns_at_200_not_at_half_the_ceiling() -> None:
    """Nâng trần không được làm cảnh báo im đi: vẫn báo ở 200, không đợi tới 500."""
    clock = _Clock()
    guard = RunawayRequestGuard(clock=clock)
    warned_at = None
    for i in range(1, 600):
        if guard._record("k", clock())[1] and warned_at is None:
            warned_at = i
    assert warned_at == 200


def test_warn_at_must_be_positive() -> None:
    with pytest.raises(ValueError):
        RunawayRequestGuard(warn_at=0)


@pytest.mark.asyncio
async def test_warning_names_the_routes_that_filled_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dòng cảnh báo phải kể route nào LẤP cửa sổ, không chỉ route thứ 200.

    Log 13–16/11 ghi `route=/phan-quyen/toi` 60 lần và người đọc tưởng route đó
    lặp — thật ra nó chỉ là lời gọi tình cờ chạm ngưỡng.
    """
    import clinicai.api.runaway_guard as mod

    rec = _Recorder()
    monkeypatch.setattr(mod, "logger", rec)
    clock = _Clock()
    guard = RunawayRequestGuard(ceiling=100, warn_at=10, clock=clock)
    me = _identity("me")
    await _goi(guard, me, "/api/v1/luot-kham/hang-cho", 5)
    await _goi(guard, me, "/api/v1/me", 3)
    await _goi(guard, me, "/api/v1/feature-mode", 1)
    # Người khác gọi dồn — không được lọt vào tóm tắt của "me".
    await _goi(guard, _identity("other"), "/api/v1/khac", 9)
    await _goi(guard, me, "/api/v1/hoa-don/cong-ty/khach/{clinic_patient_id}", 1)

    mine = [kw for _, kw in rec.warnings if kw["clinic_staff_id"] == "me"]
    assert len(mine) == 1
    kw = mine[0]
    assert kw["route"] == "/api/v1/hoa-don/cong-ty/khach/{clinic_patient_id}"
    assert kw["requests_in_window"] == 10
    assert kw["top_routes"] == [
        {"route": "/api/v1/luot-kham/hang-cho", "n": 5},
        {"route": "/api/v1/me", "n": 3},
        {"route": "/api/v1/feature-mode", "n": 1},
        {"route": "/api/v1/hoa-don/cong-ty/khach/{clinic_patient_id}", "n": 1},
    ]


@pytest.mark.asyncio
async def test_top_routes_keeps_five_and_forgets_what_aged_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import clinicai.api.runaway_guard as mod

    rec = _Recorder()
    monkeypatch.setattr(mod, "logger", rec)
    clock = _Clock()
    guard = RunawayRequestGuard(ceiling=100, warn_at=21, clock=clock)
    me = _identity("me")
    await _goi(guard, me, "/api/v1/cu", 20)  # trôi khỏi cửa sổ trước lúc báo
    clock.now += 61
    for i in range(6):
        await _goi(guard, me, f"/api/v1/r{i}", 6 - i)  # 6,5,4,3,2,1 = 21 lượt
    (kw,) = [kw for _, kw in rec.warnings]
    assert kw["requests_in_window"] == 21
    assert kw["top_routes"] == [
        {"route": f"/api/v1/r{i}", "n": 6 - i} for i in range(5)
    ]


@pytest.mark.asyncio
async def test_unmatched_request_is_counted_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import clinicai.api.runaway_guard as mod

    rec = _Recorder()
    monkeypatch.setattr(mod, "logger", rec)
    guard = RunawayRequestGuard(ceiling=10, warn_at=2, clock=_Clock())
    assert await _goi(guard, _identity(), None, 3) == 0
    (kw,) = [kw for _, kw in rec.warnings]
    assert kw["top_routes"] == [{"route": "<unmatched>", "n": 2}]
