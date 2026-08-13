"""A wide per-person request ceiling whose job is to SHOW a bug, not block a person.

WHY THIS IS NOT JUST ANOTHER RATE LIMITER. ``rate_limit.InMemoryRateLimiter``
protects things that cost money or CPU per call — the LLM endpoints, voice
transcription. Thirty calls a minute is a real budget there, and 429 is the
right answer.

The business endpoints are a different problem wearing the same clothes. They sit
on an internal network behind authentication, used by about thirty-five people
who each touch a screen a few times a minute. A human being cannot generate a
hundred requests a minute. Something that does is a *bug* — almost always a
``useEffect`` that re-fires on a dependency it also sets, or a retry loop with no
backoff.

COUNTS READS TOO, ON PURPOSE. The runaway loop this exists to expose is far more
often a refetch than a save; watching only writes would miss the common case
entirely, which is precisely the case that made the clinic feel slow.

That distinction decides the design:

  * A tight limit would CONCEAL such a bug. The loop keeps running, the server
    quietly refuses most of it, the screen half-works, and nobody investigates
    because nothing looks broken enough. The clinic just feels slow.

  * So the ceiling is deliberately far above human use — nobody working normally
    will ever meet it — and crossing it is treated as evidence, not as abuse.
    The first crossing logs at WARNING with the route and the staff id, and lands
    in the ops telemetry feed where somebody reads it.

WHAT IT STILL BLOCKS. Past the ceiling it does return 429, because a runaway
client that is left running will exhaust the connection pool and take the clinic
down with it. The point is that by then the warning has already been recorded, so
the 429 is the second thing that happens rather than the only thing.

PROCESS-LOCAL, LIKE THE OTHER ONE. One API process on one Mac. The day this runs
on several replicas the ceiling is per-replica and this file needs replacing with
something shared — that limitation is in ``rate_limit`` too, and it is stated
rather than discovered.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from threading import Lock

import structlog
from fastapi import Depends, HTTPException, Request, status

from clinicai.api.identity import (
    StaffIdentity,
    _resolve_identity,
    get_current_identity,
)
from clinicai.core.telemetry import route_template

logger = structlog.get_logger(__name__)

Clock = Callable[[], float]

# Far above human use, far below what breaks the pool.
#
# A busy receptionist moving between screens does perhaps 20 requests a minute.
# The warning still fires at HALF the ceiling, so a loop is recorded long before
# anyone is refused.
#
# ĐO LẠI 10/08/2026 — TRẦN CŨ 120 CHẶN NGƯỜI THẬT. Quang bấm các nút dưới bước
# check-in và nhận "lỗi 429" giữa chừng; log staging đếm được 28 lượt bị từ chối
# trong 40 phút, riêng lúc 09:43:13 có BẢY lời gọi `/api/v1/me` trong 0,4 giây.
#
# Sai lầm của con số cũ nằm ở tiền đề "một người làm 20 request/phút". Nó đúng
# với NGƯỜI, không đúng với MÀN HÌNH: mỗi cú bấm ở màn CSKH ghi một dòng rồi gọi
# `router.refresh()`, và một lượt dựng lại cây server component kéo theo `/me`,
# `/appointments/policy`, `/cskh/recall-jobs`, `/appointments/week`,
# `/visits/progress`… Một thao tác của người hoá ra sáu bảy lượt gọi. Nhân với
# một người đang thử nhanh là chạm trần mà không có vòng lặp nào cả.
#
# 400 giữ nguyên mục đích của cái trần này: một vòng lặp thật sinh HÀNG NGHÌN
# lượt một phút và vẫn bị bắt, trong khi người dùng nhanh tay thì không. Nếu vẫn
# gặp 429 trong lúc dùng bình thường thì ĐỪNG nâng tiếp — lúc ấy đúng là có một
# vòng lặp, và dòng cảnh báo ở nửa trần đã ghi sẵn tên đường dẫn gây ra nó.
DEFAULT_CEILING = 400
DEFAULT_WINDOW_SECONDS = 60

# Once per actor per window is enough to investigate. Without this, the runaway
# loop that triggered the warning also floods the log with warnings about itself,
# and the log becomes as unreadable as the thing it was meant to report.
_WARN_EVERY_SECONDS = 60.0


class RunawayRequestGuard:
    """Per-staff request ceiling. Warns first, refuses only past the ceiling."""

    def __init__(
        self,
        *,
        ceiling: int = DEFAULT_CEILING,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_buckets: int = 4_096,
        clock: Clock = time.monotonic,
    ) -> None:
        if ceiling <= 0 or window_seconds <= 0 or max_buckets <= 0:
            raise ValueError("runaway-guard values must be positive")
        self.ceiling = ceiling
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._last_warned: dict[str, float] = {}
        self._lock = Lock()

    @property
    def bucket_count(self) -> int:
        with self._lock:
            return len(self._hits)

    def reset(self) -> None:
        """Deterministic tests and operator-controlled resets only."""
        with self._lock:
            self._hits.clear()
            self._last_warned.clear()

    async def __call__(
        self,
        request: Request,
        identity: StaffIdentity = Depends(get_current_identity),
    ) -> None:
        now = self._clock()
        key = f"{identity.clinic_id}:{identity.staff_id}"
        count, should_warn = self._record(key, now)

        if should_warn:
            # Route TEMPLATE, never the filled-in path — the same rule the
            # telemetry buffer follows, and for the same reason: a patient id in
            # an operations log is still a patient id.
            logger.warning(
                "request_rate_unusually_high",
                route=route_template(request),
                method=request.method,
                clinic_staff_id=identity.staff_id,
                clinic_role=identity.role.value,
                requests_in_window=count,
                window_seconds=self.window_seconds,
                ceiling=self.ceiling,
                hint=(
                    "A person cannot click this fast. Look for a client-side "
                    "loop (useEffect re-firing, retry without backoff) before "
                    "raising the ceiling."
                ),
            )

        if count > self.ceiling:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Quá nhiều yêu cầu trong một phút — nhiều khả năng màn hình "
                    "đang lặp. Tải lại trang; nếu vẫn vậy, báo kỹ thuật."
                ),
                headers={"Retry-After": str(self.window_seconds)},
            )

    def _record(self, key: str, now: float) -> tuple[int, bool]:
        """Count this request and say whether it deserves a warning line."""
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                if len(self._hits) >= self.max_buckets:
                    # Drop what has aged out before giving up on capacity; a
                    # clinic has tens of staff, so a full table means stale
                    # buckets, not thousands of live actors.
                    self._evict_expired(cutoff)
                if len(self._hits) >= self.max_buckets:
                    # Fail OPEN. This guard exists to surface a bug, not to stand
                    # between a nurse and a patient record — refusing a clinical
                    # request because a bookkeeping table is full would be a worse
                    # outage than the one it prevents. (rate_limit.py fails CLOSED
                    # for the opposite and equally correct reason: there, letting
                    # requests through costs real money on every call.)
                    logger.error("runaway_guard_capacity_exhausted")
                    return 0, False
                bucket = deque()
                self._hits[key] = bucket

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            bucket.append(now)
            count = len(bucket)

            # Warn at HALF the ceiling: by the time a loop reaches the ceiling it
            # is already being refused, and the useful moment to notice was
            # earlier — while the writes were still landing.
            should_warn = False
            if count >= self.ceiling // 2:
                last = self._last_warned.get(key, float("-inf"))
                if now - last >= _WARN_EVERY_SECONDS:
                    self._last_warned[key] = now
                    should_warn = True

            return count, should_warn

    def _evict_expired(self, cutoff: float) -> None:
        stale = [k for k, b in self._hits.items() if not b or b[-1] <= cutoff]
        for k in stale:
            self._hits.pop(k, None)
            self._last_warned.pop(k, None)


# One shared instance: the ceiling is per PERSON, so every guarded route has to
# count into the same buckets. A per-router instance would give one runaway loop
# a fresh allowance on each endpoint it happened to hit.
_guard = RunawayRequestGuard()


# THE DEPENDENCY IS THIS FUNCTION, NOT THE INSTANCE, AND THAT MATTERS.
#
# `Depends(_guard)` looks equivalent and is not. This module has
# `from __future__ import annotations`, so every annotation is a string at
# runtime. To resolve them FastAPI needs the defining module's globals, which it
# reaches through `call.__globals__` — an attribute a class *instance* does not
# have. The `request: Request` annotation therefore stayed the string "Request",
# FastAPI could not recognise it as the ASGI request, and treated it as a QUERY
# PARAMETER. Every guarded endpoint answered:
#
#     422 {"detail":[{"loc":["query","request"],"msg":"Field required"}]}
#
# api.identity.RoleGuard is an instance dependency and survives this only because
# its single parameter carries an explicit `Depends(...)` default, which FastAPI
# routes without needing the type at all.
#
# A module-level function has `__globals__`, so the annotations resolve. Keeping
# the state in `_guard` and the signature here also means the ceiling stays
# adjustable in one object while the wiring stays a plain function.
async def runaway_guard(
    request: Request,
    identity: StaffIdentity = Depends(get_current_identity),
) -> None:
    """Count this request against the caller's per-minute ceiling."""
    await _guard(request, identity)


async def runaway_guard_cho_ca_man_hinh(
    request: Request,
    identity: StaffIdentity = Depends(_resolve_identity),
) -> None:
    """Như trên, nhưng KHÔNG chặn vai DISPLAY.

    VÌ SAO PHẢI CÓ BẢN THỨ HAI. `runaway_guard` nhận danh tính qua
    `get_current_identity`, và hàm đó TỪ CHỐI vai DISPLAY (tài khoản màn hình
    TV). Vì bộ đếm được gắn ở TẦNG ROUTER (`_GUARDED` trong main.py), nó chạy
    trước mọi endpoint — nên `/api/v1/me` trả 403 cho cái tivi dù chính endpoint
    đó đã khai `get_display_identity`.

    Rất khó lần ra: nhìn vào mã của endpoint không thấy gì sai, thứ từ chối nằm
    ở tham số mặc định của một dependency khai ở file khác.

    Bản này dựng danh tính bằng `_resolve_identity` — đủ để ĐẾM (bộ đếm hỏi "ai
    đang gọi", không hỏi "ai được phép"), và để phần phân quyền cho endpoint tự
    lo. Vai DISPLAY vẫn bị tính vào hạn mức như mọi tài khoản khác.

    Chỉ dùng cho router nào có endpoint mở cho màn hình. Đừng đổi
    `runaway_guard` gốc: hàng chục bài kiểm ghi đè `get_current_identity` và sẽ
    ngừng có tác dụng.
    """
    await _guard(request, identity)
