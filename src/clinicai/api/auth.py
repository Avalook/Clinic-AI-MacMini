"""API-key middleware — gates the FastAPI app from anonymous callers.

PACKET-2 (SEC-API-01). Before real PII (~6.4k patients from the Notion clone)
is pushed into Supabase, the backend cannot stay wide-open. This is the
minimal "hard NO for unauthenticated callers" layer; per-staff RBAC is the
proper P11 work — see CURRENT_PROGRESS 26/5 ("Backend KHÔNG có auth (mở
hoàn toàn)") which this packet closes.

Contract
--------
- Middleware reads ``BACKEND_API_KEY`` from the environment at *request* time.
- Routes under :data:`EXEMPT_PATHS` are always reachable (health/probe).
- If ``BACKEND_API_KEY`` is unset in an explicitly named development/test
  environment → request passes through with a structured warning log.
- In production, staging, or an unknown/unset environment → protected routes
  return 503. A deployment mistake must never silently turn authentication off.
- If the variable is set:
    * missing ``X-API-Key`` header → 401 Unauthorized
    * header present but != configured value → 403 Forbidden
    * header == configured value → request proceeds

Design notes
------------
The check uses ``hmac.compare_digest`` for constant-time comparison so the key
cannot be probed timing-side. The middleware runs ahead of the route handlers
but after FastAPI's request parsing, so handler-level dependencies still see
the same request as before.
"""

from __future__ import annotations

import hmac
import os
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger()

# Health / readiness probes never need an API key — load balancers, Docker
# healthchecks, and k8s liveness checks call these without secrets.
EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/health/db",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)

API_KEY_HEADER = "X-API-Key"
ENV_VAR_NAME = "BACKEND_API_KEY"
APP_ENV_VAR_NAME = "APP_ENV"
UNPROTECTED_DEV_ENVIRONMENTS = frozenset(
    {"dev", "development", "local", "test", "testing"}
)


def _is_exempt(path: str) -> bool:
    """``/health`` and ``/openapi.json`` always; anything under ``/docs/...``
    too (Swagger fetches assets from sub-paths)."""
    if path in EXEMPT_PATHS:
        return True
    return path.startswith("/docs/") or path.startswith("/redoc/")


async def api_key_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[JSONResponse]],
) -> JSONResponse:
    """Gate every non-exempt route on the ``X-API-Key`` header."""
    if _is_exempt(request.url.path):
        return await call_next(request)

    expected = os.environ.get(ENV_VAR_NAME)
    if not expected:
        app_env = os.environ.get(APP_ENV_VAR_NAME, "").strip().lower()
        if app_env not in UNPROTECTED_DEV_ENVIRONMENTS:
            logger.error(
                "auth_middleware_misconfigured",
                reason=f"{ENV_VAR_NAME} not set in {app_env or 'unknown environment'}",
                path=request.url.path,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "SERVER_MISCONFIGURED",
                    "message": "API authentication is not configured",
                },
            )

        # Explicit dev/test fallback. Non-production environments stay
        # frictionless without weakening the production failure mode.
        logger.warning(
            "auth_middleware_disabled",
            reason=(
                f"{ENV_VAR_NAME} not set in {app_env}; allowing request without API key"
            ),
            path=request.url.path,
        )
        return await call_next(request)

    presented = request.headers.get(API_KEY_HEADER)
    if not presented:
        logger.info("auth_missing_key", path=request.url.path, method=request.method)
        return JSONResponse(
            status_code=401,
            content={
                "error": "UNAUTHORIZED",
                "message": f"Missing {API_KEY_HEADER} header",
            },
        )

    if not hmac.compare_digest(presented, expected):
        logger.info("auth_wrong_key", path=request.url.path, method=request.method)
        return JSONResponse(
            status_code=403,
            content={"error": "FORBIDDEN", "message": "Invalid API key"},
        )

    return await call_next(request)
