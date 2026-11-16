"""A wide per-person request ceiling whose job is to SHOW a bug, not block a person.

WHY THIS IS NOT JUST ANOTHER RATE LIMITER. ``rate_limit.InMemoryRateLimiter``
protects things that cost money or CPU per call — the LLM endpoints, voice
transcription. Thirty calls a minute is a real budget there, and 429 is the
right answer.

The business endpoints are a different problem wearing the same clothes. They sit
on an internal network behind authentication, used by about thirty-five people
who each touch a screen a few times a minute. A *person* cannot click a thousand
times a minute; a *screen* can easily ask a few hundred times, because live
updates make every open tab refetch (see the measurements at DEFAULT_CEILING).
Past the ceiling it is a *bug* — almost always a ``useEffect`` that re-fires on a
dependency it also sets, or a retry loop with no backoff.

THE COUNT IS PER PERSON, ACROSS ALL ROUTES. The warning's ``route`` is just the
request that crossed the line; ``top_routes`` says which routes filled the window.

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
from collections import Counter, deque
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
# NGƯỜI ≠ MÀN HÌNH. Một lượt người bấm hiếm khi là một request: `router.refresh()`
# dựng lại layout (7 lời gọi) và mỗi lượt GHI ở bất kỳ đâu trong phòng khám làm
# MỌI tab đang mở hỏi lại — tin SSE chỉ mang tên bảng, nên phiếu của khách B cũng
# hỏi lại khi lượt của khách A đổi. Hai lần đo:
#   * 10/08/2026: trần 120 chặn Quang lúc bấm dưới bước check-in → nâng 400.
#   * 13–16/11/2026 (log prod): người làm việc bình thường lên tới 443 lượt/phút,
#     25 nhân viên mọi vai; trần 400 trả 1.834 lượt 429 trong 2,6 ngày. Một lượt
#     ghi đứng riêng kéo theo ~15 GET trong 1,5 giây. Không có vòng lặp nào —
#     các đợt dài 1–6 phút, route chạm ngưỡng đổi liên tục.
#
# 1000 (Tuyền chốt 16/11) = ~2,25 lần đỉnh người thật; vòng lặp thật sinh HÀNG
# NGHÌN lượt một phút và vẫn bị chặn trước khi vét bể kết nối. Gặp 429 lúc dùng
# bình thường thì đọc `top_routes` trong dòng cảnh báo trước — đó là bằng chứng
# màn nào hỏi dày, sửa ở đó (tin SSE theo lượt, cache layout), đừng nâng mù.
DEFAULT_CEILING = 1000
DEFAULT_WINDOW_SECONDS = 60

# Cảnh báo ở ngưỡng CỐ ĐỊNH, không theo trần: trước đây báo ở nửa trần, nên nâng
# trần lên 1000 sẽ làm cảnh báo im tới 500 — mất đúng thứ cần nhìn. Trần nhỏ hơn
# (test) thì vẫn báo ở nửa trần, để cảnh báo luôn tới trước 429.
DEFAULT_WARN_AT = 200

# Bao nhiêu route kể trong dòng cảnh báo. Năm là đủ thấy màn nào gây ra: các
# route của một lượt dựng layout luôn đi thành cụm.
_TOP_ROUTES = 5

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
        warn_at: int = DEFAULT_WARN_AT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_buckets: int = 4_096,
        clock: Clock = time.monotonic,
    ) -> None:
        if min(ceiling, warn_at, window_seconds, max_buckets) <= 0:
            raise ValueError("runaway-guard values must be positive")
        self.ceiling = ceiling
        self.warn_at = min(warn_at, max(ceiling // 2, 1))
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._clock = clock
        # Mỗi lượt giữ kèm route TEMPLATE (không phải đường dẫn đã điền id), để
        # dòng cảnh báo kể được route nào lấp cửa sổ.
        self._hits: dict[str, deque[tuple[float, str]]] = {}
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
        # Route TEMPLATE, never the filled-in path — the same rule the telemetry
        # buffer follows, and for the same reason: a patient id in an operations
        # log is still a patient id.
        route = route_template(request)
        count, should_warn = self._record(key, now, route)

        if should_warn:
            logger.warning(
                "request_rate_unusually_high",
                # `route` chỉ là lượt TÌNH CỜ chạm ngưỡng, không phải thủ phạm —
                # bộ đếm gộp mọi route của một người. Đọc `top_routes`.
                route=route,
                top_routes=self._top_routes(key),
                method=request.method,
                clinic_staff_id=identity.staff_id,
                clinic_role=identity.role.value,
                requests_in_window=count,
                window_seconds=self.window_seconds,
                ceiling=self.ceiling,
                hint=(
                    "Counts every route of this person together; `route` is only "
                    "the request that crossed the line. Read `top_routes`: a few "
                    "routes repeating = a loop on that screen; a spread of layout "
                    "routes (/me, /phan-quyen/toi, /feature-mode…) = refresh "
                    "fan-out from live updates."
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

    def _record(
        self, key: str, now: float, route: str = "<unmatched>"
    ) -> tuple[int, bool]:
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

            while bucket and bucket[0][0] <= cutoff:
                bucket.popleft()
            bucket.append((now, route))
            count = len(bucket)

            # Warn well below the ceiling (`warn_at`): by the time a loop reaches
            # the ceiling it is already being refused, and the useful moment to
            # notice was earlier — while the writes were still landing.
            should_warn = False
            if count >= self.warn_at:
                last = self._last_warned.get(key, float("-inf"))
                if now - last >= _WARN_EVERY_SECONDS:
                    self._last_warned[key] = now
                    should_warn = True

            return count, should_warn

    def _top_routes(self, key: str) -> list[dict[str, object]]:
        """Các route lấp cửa sổ của người này, nhiều nhất trước (tối đa 5).

        Chỉ chạy khi cảnh báo — tối đa một lần một phút mỗi người — nên đếm lại
        cả cửa sổ (≤ trần) là rẻ, không cần giữ bộ đếm riêng theo route.
        """
        with self._lock:
            dem = Counter(route for _, route in self._hits.get(key, ()))
        return [{"route": r, "n": n} for r, n in dem.most_common(_TOP_ROUTES)]

    def _evict_expired(self, cutoff: float) -> None:
        stale = [k for k, b in self._hits.items() if not b or b[-1][0] <= cutoff]
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


async def runaway_guard_khong_chan_vai(
    request: Request,
    identity: StaffIdentity = Depends(_resolve_identity),
) -> None:
    """Như trên, nhưng CHỈ ĐẾM — không tự ý từ chối vai nào.

    VÌ SAO PHẢI CÓ BẢN THỨ HAI. `runaway_guard` nhận danh tính qua
    `get_current_identity`, và hàm đó TỪ CHỐI hai vai ngoài luồng làm việc:
    DISPLAY (cái tivi phòng chờ) và PARTNER (đối tác ngoài phòng khám). Vì bộ
    đếm được gắn ở TẦNG ROUTER (`_GUARDED` trong main.py), nó chạy TRƯỚC mọi
    endpoint — nên endpoint dù đã khai `get_display_identity` hay
    `get_partner_identity` vẫn trả 403.

    Rất khó lần ra: nhìn vào mã của endpoint không thấy gì sai, thứ từ chối nằm
    ở tham số mặc định của một dependency khai ở file khác. Đã cắn HAI LẦN —
    `/api/v1/me` với vai DISPLAY (09/2026), rồi `/doi-tac/viec` với vai PARTNER
    (16/09/2026), dù lần hai đã có sẵn chú thích này cảnh báo. Tên hàm cũ
    (`…_cho_ca_man_hinh`) là một phần lý do: nó nghe như chỉ dành cho cái tivi,
    nên người thêm router đối tác không nhận ra mình cần chính nó.

    Bản này dựng danh tính bằng `_resolve_identity` — đủ để ĐẾM (bộ đếm hỏi "ai
    đang gọi", không hỏi "ai được phép"), và để phần phân quyền cho endpoint tự
    lo. Cả hai vai vẫn bị tính vào hạn mức như mọi tài khoản khác.

    DÙNG CHO MỌI ROUTER CÓ ENDPOINT MỞ CHO VAI NGOÀI LUỒNG. Đừng đổi
    `runaway_guard` gốc: hàng chục bài kiểm ghi đè `get_current_identity` và sẽ
    ngừng có tác dụng.
    """
    await _guard(request, identity)
