"""Idempotency-key support for POST endpoints (Phase 2, Bài 14).

Prevents double-submit: if a caller sends the same ``Idempotency-Key`` header
for the same endpoint, the second request returns the cached response from the
first without re-executing the handler.

Usage in a router::

    @router.post("/appointments", ...)
    async def create_appointment(
        data: ...,
        pool: asyncpg.Pool = Depends(get_db_pool),
        idem: IdempotencyGuard = Depends(idempotency_guard),
    ):
        idem = await idem.acquire(pool, actor_id=verified_actor_id)
        if idem.is_replay:
            return idem.cached_response
        # ... create appointment ...
        result = {"id": "..."}
        await idem.save(pool, result, status_code=201)
        return result

The ``Idempotency-Key`` header is OPTIONAL — if absent, the request proceeds
normally (no caching). Keys expire after 24 hours.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any

import asyncpg
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from clinicai.api.exceptions import ConflictError

logger = structlog.get_logger()

HEADER_NAME = "Idempotency-Key"
KEY_TTL_HOURS = 24
PROCESSING_TTL_MINUTES = 5
MAX_KEY_LENGTH = 200


@dataclass(frozen=True)
class IdempotencyGuard:
    """Holds the idempotency key for the current request.

    If ``cached_response`` is set, the handler should return it immediately.
    Otherwise the handler runs normally and calls ``save()`` at the end.
    """

    key: str | None = None
    endpoint: str = ""
    actor_id: str = ""
    cached_response: JSONResponse | None = None
    _acquired: bool = field(default=False, repr=False)

    @property
    def is_replay(self) -> bool:
        """True if this request is a replay of a previous one."""
        return self.cached_response is not None

    async def acquire(
        self,
        pool: asyncpg.Pool,
        *,
        actor_id: str | None = None,
    ) -> IdempotencyGuard:
        """Atomically reserve this key, or load its completed response.

        The identity is part of the uniqueness scope. Endpoints without a
        verified end-user identity use the empty server scope, while protected
        endpoints should pass the verified auth/staff id. A concurrent request
        that sees a live ``PROCESSING`` reservation receives 409 instead of
        executing the side effect a second time.
        """
        if not self.key or self._acquired or self.cached_response is not None:
            return self

        actor_scope = actor_id or ""
        inserted = await pool.fetchrow(
            """
            INSERT INTO idempotency_key (
                key, endpoint, actor_id, response, status_code, state
            )
            VALUES ($1, $2, $3, NULL, 200, 'PROCESSING')
            ON CONFLICT (key, endpoint, actor_id) DO NOTHING
            RETURNING key
            """,
            self.key,
            self.endpoint,
            actor_scope,
        )
        if inserted is not None:
            return replace(self, actor_id=actor_scope, _acquired=True)

        # Recover a crashed reservation after a short processing lease, or an
        # expired completed cache after the normal 24-hour retention window.
        reclaimed = await pool.fetchrow(
            f"""
            UPDATE idempotency_key
            SET response = NULL,
                status_code = 200,
                state = 'PROCESSING',
                created_at = now(),
                updated_at = now()
            WHERE key = $1 AND endpoint = $2 AND actor_id = $3
              AND (
                (state = 'PROCESSING'
                 AND updated_at < now() - interval '{PROCESSING_TTL_MINUTES} minutes')
                OR
                (state = 'COMPLETED'
                 AND created_at < now() - interval '{KEY_TTL_HOURS} hours')
              )
            RETURNING key
            """,
            self.key,
            self.endpoint,
            actor_scope,
        )
        if reclaimed is not None:
            return replace(self, actor_id=actor_scope, _acquired=True)

        row = await pool.fetchrow(
            """
            SELECT response, status_code, state
            FROM idempotency_key
            WHERE key = $1 AND endpoint = $2 AND actor_id = $3
            """,
            self.key,
            self.endpoint,
            actor_scope,
        )
        if row is not None and row["state"] == "COMPLETED":
            raw_response = row["response"]
            content = (
                json.loads(raw_response)
                if isinstance(raw_response, str)
                else raw_response
            )
            logger.info(
                "idempotency_replay",
                key=self.key,
                endpoint=self.endpoint,
                actor_id=actor_scope or None,
            )
            return replace(
                self,
                actor_id=actor_scope,
                cached_response=JSONResponse(
                    content=content,
                    status_code=row["status_code"],
                ),
            )

        raise ConflictError(
            "Yêu cầu với Idempotency-Key này đang được xử lý; vui lòng thử lại."
        )

    async def save(
        self,
        pool: asyncpg.Pool,
        response_body: dict[str, Any],
        status_code: int = 200,
    ) -> None:
        """Persist the response for this key (call once, after successful handler)."""
        if not self.key:
            return
        if not self._acquired:
            raise RuntimeError("IdempotencyGuard.save() called before acquire()")
        result = await pool.execute(
            """
            UPDATE idempotency_key
            SET response = $1::jsonb,
                status_code = $2,
                state = 'COMPLETED',
                updated_at = now()
            WHERE key = $3 AND endpoint = $4 AND actor_id = $5
              AND state = 'PROCESSING'
            """,
            json.dumps(response_body),
            status_code,
            self.key,
            self.endpoint,
            self.actor_id,
        )
        if result != "UPDATE 1":
            raise RuntimeError("Idempotency reservation was not completed")


async def idempotency_guard(
    request: Request,
) -> IdempotencyGuard:
    """Create a request guard; the endpoint binds actor scope via ``acquire``."""
    key = request.headers.get(HEADER_NAME)
    endpoint = f"{request.method} {request.url.path}"

    if not key:
        return IdempotencyGuard(key=None, endpoint=endpoint)
    if len(key) > MAX_KEY_LENGTH:
        raise ConflictError(
            f"Idempotency-Key must be at most {MAX_KEY_LENGTH} characters"
        )
    return IdempotencyGuard(key=key, endpoint=endpoint)
