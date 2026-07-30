"""Small process-local rate limiter for expensive authenticated operations.

The self-hosted deployment runs one API process today, so an in-memory sliding
window provides a useful first line of defence without adding another service.
The bucket key includes both clinic and staff identity: one tenant cannot spend
another tenant's allowance, and a shared clinic NAT does not penalise everyone.

The bucket map is bounded. If its capacity is exhausted, new actors are denied
instead of bypassing the guard or growing memory without limit. A future
multi-process deployment must replace this with a shared Redis/database-backed
limiter before increasing the worker count.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable
from threading import Lock

import structlog
from fastapi import Depends, HTTPException, status

from clinicai.api.identity import StaffIdentity, get_current_identity

logger = structlog.get_logger(__name__)

Clock = Callable[[], float]


class InMemoryRateLimiter:
    """Per-staff, per-clinic sliding-window request limiter."""

    def __init__(
        self,
        *,
        scope: str,
        limit: int,
        window_seconds: int,
        max_buckets: int = 10_000,
        clock: Clock = time.monotonic,
    ) -> None:
        if not scope:
            raise ValueError("scope must not be empty")
        if limit <= 0 or window_seconds <= 0 or max_buckets <= 0:
            raise ValueError("rate-limit values must be positive")
        self.scope = scope
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._clock = clock
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    @property
    def bucket_count(self) -> int:
        """Number of actor buckets currently retained (primarily observability)."""
        with self._lock:
            return len(self._buckets)

    def reset(self) -> None:
        """Clear all counters.

        Production does not call this; it exists for deterministic application
        tests and explicit operator-controlled process resets.
        """
        with self._lock:
            self._buckets.clear()

    async def __call__(
        self,
        identity: StaffIdentity = Depends(get_current_identity),
    ) -> None:
        """Consume one request allowance or reject before costly work begins."""
        try:
            now = self._clock()
            if not math.isfinite(now):
                raise RuntimeError("rate-limit clock returned a non-finite value")
            retry_after = self._consume(identity=identity, now=now)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "rate_limit_internal_failure",
                scope=self.scope,
                error_type=type(exc).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter unavailable",
            ) from exc

        if retry_after is not None:
            logger.warning("rate_limit_exceeded", scope=self.scope)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {self.scope}",
                headers={"Retry-After": str(retry_after)},
            )

    def _consume(self, *, identity: StaffIdentity, now: float) -> int | None:
        key = f"{identity.clinic_id}:{identity.staff_id}"
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                self._drop_expired_buckets(cutoff=cutoff)
                if len(self._buckets) >= self.max_buckets:
                    logger.error(
                        "rate_limit_capacity_exhausted",
                        scope=self.scope,
                        max_buckets=self.max_buckets,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limiter capacity exhausted for {self.scope}",
                        headers={"Retry-After": str(self.window_seconds)},
                    )
                bucket = deque()
                self._buckets[key] = bucket

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                seconds = bucket[0] + self.window_seconds - now
                return max(1, math.ceil(seconds))

            bucket.append(now)
            return None

    def _drop_expired_buckets(self, *, cutoff: float) -> None:
        expired = [
            key
            for key, bucket in self._buckets.items()
            if not bucket or bucket[-1] <= cutoff
        ]
        for key in expired:
            del self._buckets[key]
