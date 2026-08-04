"""Cross-cutting HTTP middleware for observability and resilience.

Phase 1 of the System Design completion plan.

Middleware order (outermost → innermost):
  1. RequestIdMiddleware  — assign X-Request-ID, bind to structlog
  2. TimingMiddleware     — record duration + status into the ring buffer
  3. api_key_middleware   — gate on BACKEND_API_KEY (existing)
  4. DbErrorMiddleware    — catch transient DB errors → 503

Timing sits OUTSIDE the API-key gate on purpose: a flood of rejected requests is
exactly the kind of thing you want to see on the telemetry screen, and a probe
that never reaches a route still costs the server time.

HOW THAT ORDER IS ACTUALLY PRODUCED, because it is the opposite of how it reads.
``Starlette.add_middleware`` does ``user_middleware.insert(0, …)`` — the LAST
one added ends up OUTERMOST. For three months main.py added them in the order
written above and got the exact reverse at runtime:

    DbErrorMiddleware → api_key → Timing → RequestId → routes

which quietly cost both things the comments promised. Timing sat *inside* the
API-key gate, so the rejected flood it exists to show was the one thing it could
not see; and RequestId sat innermost, so every 401/403/503 went out with no
``X-Request-ID`` header and every auth log line had no ``request_id`` bound.
``main.py`` now registers them in reverse and ``test_middleware_order`` asserts
the resulting stack, so the next person to add one finds out from a red test
rather than from a debugging session.

WHY DbError IS INNERMOST rather than outermost. It converts a dead connection
into a 503 *response*. Innermost, Timing then sees status=503 and records it.
Outermost, the exception would still be flying when Timing's ``finally`` ran and
the buffer would say 500 for something the client received as 503.
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar

import asyncpg
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from clinicai.core.telemetry import route_template, telemetry

logger = structlog.get_logger()

REQUEST_ID_HEADER = "X-Request-ID"

# The id for the request being served, readable by any middleware inside
# RequestIdMiddleware.
#
# Telemetry used to read ``request.headers.get("X-Request-ID")`` instead, which
# is only ever set when an upstream proxy happens to send one. Locally and
# behind Caddy nothing does, so every entry in the error feed carried
# request_id=None — and the ops screen printed "dùng mã này để tra trong log"
# next to a value it never had. A generated id cannot be put back into
# ``request.headers`` (immutable), so it travels here. BaseHTTPMiddleware runs
# the downstream app in a child task, which inherits contextvars, so an inner
# middleware sees what an outer one set.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """The X-Request-ID of the request being served, if one has been assigned."""
    return request_id_ctx.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a unique request ID to every request.

    * If the caller already sends ``X-Request-ID`` (e.g. Caddy, Cloudflare),
      reuse it; otherwise generate a UUID4.
    * Bind the ID into structlog context so every log line in the request
      automatically includes ``request_id``.
    * Echo the ID back in the response header for client-side correlation.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Bind to structlog context for the duration of this request.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        token = request_id_ctx.set(request_id)

        try:
            response = await call_next(request)
        finally:
            # An unhandled exception must not leave the id bound for whatever
            # this worker task serves next.
            request_id_ctx.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class DbErrorMiddleware(BaseHTTPMiddleware):
    """Catch transient database connection errors and return 503.

    Without this, a temporary Supabase outage causes the container health
    check to see 500 → Docker restarts it → crash loop. With this, the
    container stays up, returns 503 (retriable), and self-heals when the
    connection recovers.

    Only catches *connection-level* errors (network, pool exhaustion),
    NOT query/logic errors (those surface as 400/409/500 as usual).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except (
            asyncpg.PostgresConnectionError,
            asyncpg.InterfaceError,
            OSError,  # covers socket-level failures
        ) as exc:
            logger.error(
                "db_connection_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=503,
                content={
                    "error": "SERVICE_UNAVAILABLE",
                    "message": "Database temporarily unavailable. Please retry.",
                },
                headers={"Retry-After": "5"},
            )


class TimingMiddleware(BaseHTTPMiddleware):
    """Record how long each request took, and what it returned.

    Only the route template is stored — see core/telemetry for why an actual
    path must never end up in a debugging buffer.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        started = time.perf_counter()
        status = 500
        kind = ""
        detail = ""
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception as exc:  # noqa: BLE001 - re-raised immediately below
            # An unhandled exception is the single most important thing this
            # buffer can hold, and it would otherwise never be recorded: the
            # response never gets built, so the normal path above never runs.
            kind = type(exc).__name__
            detail = str(exc)
            raise
        finally:
            telemetry.record(
                route=route_template(request),
                method=request.method,
                status=status,
                duration_ms=(time.perf_counter() - started) * 1000.0,
                request_id=current_request_id(),
                kind=kind,
                detail=detail,
            )
