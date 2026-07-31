"""In-process request telemetry: what is slow, and what is failing.

Nothing in this system recorded how long a request took. `/ops` reports whether
containers are up, which answers "is it running" and not "is it working" — a
front desk waiting eight seconds for a queue to load has a healthy container.

WHY IN MEMORY, NOT A TABLE. The obvious alternative is a request_log table, and
it is the wrong one here: it puts an unbounded write on the clinical database's
hot path, it grows forever, and it means every slow request makes the database
slower. This is a bounded ring buffer in the API process. The cost is honest and
worth stating — the numbers reset when the API restarts and describe one
process, not a cluster. For a single Mac mini serving one clinic that is the
right trade; the day this runs on several replicas it needs a real metrics sink,
and that is a different piece of work rather than a bigger buffer.

WHAT IS NEVER RECORDED. Route TEMPLATES only — `/api/v1/patients/{patient_id}`,
never the filled-in path. No query strings, no bodies, no headers, no request
IDs beyond the ones already in the logs. A patient's identifier in a debugging
tool is still a patient's identifier, and this endpoint is read by a wider
audience than the clinical screens are.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, cast

# ~4k requests is a busy clinic afternoon and a few MB at most. Old entries fall
# off the back; this is a window on recent behaviour, not an archive.
MAX_SAMPLES = 4096
MAX_ERRORS = 200

# A request slower than this is worth a clinician noticing, not just a graph.
SLOW_REQUEST_MS = 1000.0


@dataclass(frozen=True, slots=True)
class Sample:
    route: str
    method: str
    status: int
    duration_ms: float
    at: float


@dataclass(frozen=True, slots=True)
class ErrorEntry:
    route: str
    method: str
    status: int
    at: float
    request_id: str | None
    kind: str
    detail: str


class Telemetry:
    """Thread-safe ring buffers for recent requests and recent failures."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._samples: deque[Sample] = deque(maxlen=MAX_SAMPLES)
        self._errors: deque[ErrorEntry] = deque(maxlen=MAX_ERRORS)
        self._started = time.time()

    def record(
        self,
        *,
        route: str,
        method: str,
        status: int,
        duration_ms: float,
        request_id: str | None = None,
        kind: str = "",
        detail: str = "",
    ) -> None:
        now = time.time()
        with self._lock:
            self._samples.append(
                Sample(
                    route=route,
                    method=method,
                    status=status,
                    duration_ms=duration_ms,
                    at=now,
                )
            )
            # 4xx is the client being told no — an expected part of a guarded
            # API, not a fault. Only 5xx lands in the error feed, or the feed
            # fills with correct refusals and nobody reads it.
            if status >= 500:
                self._errors.append(
                    ErrorEntry(
                        route=route,
                        method=method,
                        status=status,
                        at=now,
                        request_id=request_id,
                        kind=kind or "HTTPError",
                        detail=detail[:300],
                    )
                )

    def snapshot(self, window_s: float | None = None) -> dict[str, Any]:
        """Summarise the buffer. `window_s` limits it to the recent past."""
        cutoff = time.time() - window_s if window_s else 0.0
        with self._lock:
            samples = [s for s in self._samples if s.at >= cutoff]
            errors = list(self._errors)
            started = self._started

        by_route: dict[tuple[str, str], list[float]] = {}
        statuses: dict[str, int] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
        for s in samples:
            by_route.setdefault((s.method, s.route), []).append(s.duration_ms)
            bucket = f"{s.status // 100}xx"
            if bucket in statuses:
                statuses[bucket] += 1

        routes: list[dict[str, Any]] = [
            {
                "method": method,
                "route": route,
                "count": len(times),
                "p50_ms": round(percentile(times, 50), 1),
                "p95_ms": round(percentile(times, 95), 1),
                "max_ms": round(max(times), 1),
            }
            for (method, route), times in by_route.items()
        ]
        # Slowest at p95 first: the question this screen answers is "what should
        # I fix", and that is the tail, not the average.
        routes.sort(key=lambda r: float(cast(float, r["p95_ms"])), reverse=True)

        all_times = [s.duration_ms for s in samples]
        return {
            "since": started,
            "window_s": window_s,
            "total": len(samples),
            "statuses": statuses,
            "p50_ms": round(percentile(all_times, 50), 1) if all_times else 0.0,
            "p95_ms": round(percentile(all_times, 95), 1) if all_times else 0.0,
            "p99_ms": round(percentile(all_times, 99), 1) if all_times else 0.0,
            "slow_count": sum(1 for t in all_times if t >= SLOW_REQUEST_MS),
            "routes": routes[:40],
            "errors": [
                {
                    "route": e.route,
                    "method": e.method,
                    "status": e.status,
                    "at": e.at,
                    "request_id": e.request_id,
                    "kind": e.kind,
                    "detail": e.detail,
                }
                for e in reversed(errors)
            ][:50],
        }


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile: the smallest value at or above pct of the sample.

    ceil(pct/100 * n), 1-indexed. An earlier round()-based version returned the
    96th of 100 for p95 — one rank high, which flatters nothing but is wrong in
    the direction that hides a slow tail. Small samples are the norm here, so
    there is no interpolation.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, math.ceil(pct / 100.0 * len(ordered)) - 1))
    return ordered[k]


def route_template(request: Any) -> str:
    """The matched route pattern, never the filled-in path.

    `/api/v1/patients/3f2b…` identifies a patient; `/api/v1/patients/{id}` does
    not, and groups usefully besides. Falls back to the literal path only when
    nothing matched — a 404 has no template, and an unmatched path cannot carry
    an id that means anything to this system.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return "<unmatched>"


telemetry = Telemetry()
