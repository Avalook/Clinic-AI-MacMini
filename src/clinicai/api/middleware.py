"""Cross-cutting HTTP middleware for observability and resilience.

Phase 1 of the System Design completion plan.

Middleware order (outermost → innermost):
  1. request_id_middleware  — assign X-Request-ID, bind to structlog
  2. api_key_middleware     — gate on BACKEND_API_KEY (existing)
  3. db_error_middleware    — catch transient DB errors → 503
"""

from __future__ import annotations

import uuid

import asyncpg
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger()

REQUEST_ID_HEADER = "X-Request-ID"


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

        response = await call_next(request)
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
