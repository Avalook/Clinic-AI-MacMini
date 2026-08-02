"""ClinicAI FastAPI application entry point."""

import os
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

import asyncpg.exceptions
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from clinicai.api.auth import api_key_middleware
from clinicai.api.middleware import (
    DbErrorMiddleware,
    RequestIdMiddleware,
    TimingMiddleware,
)
from clinicai.api.v1.health import router as health_router
from clinicai.api.v1.patients import router as patients_router
from clinicai.api.v1.routers.booking import router as booking_router
from clinicai.api.v1.routers.brief import router as brief_router
from clinicai.api.v1.routers.catalog import router as catalog_router
from clinicai.api.v1.routers.clinical_forms import router as clinical_forms_router
from clinicai.api.v1.routers.clinical_records import (
    router as clinical_records_router,
)
from clinicai.api.v1.routers.config import router as config_router
from clinicai.api.v1.routers.console import router as console_router
from clinicai.api.v1.routers.cskh import router as cskh_router
from clinicai.api.v1.routers.episodes import router as episodes_router
from clinicai.api.v1.routers.identity import router as identity_router
from clinicai.api.v1.routers.lab import router as lab_router
from clinicai.api.v1.routers.ops import router as ops_router
from clinicai.api.v1.routers.orchestrator import router as orchestrator_router
from clinicai.api.v1.routers.payment import router as payment_router
from clinicai.api.v1.routers.pharmacy import router as pharmacy_router
from clinicai.api.v1.routers.queue import router as queue_router
from clinicai.api.v1.routers.scheduling import router as scheduling_router
from clinicai.api.v1.routers.service_log import router as service_log_router
from clinicai.api.v1.routers.staff import router as staff_router
from clinicai.api.v1.routers.tools import router as tools_router
from clinicai.api.v1.routers.ultrasound import router as ultrasound_router
from clinicai.api.v1.routers.visit_progress import (
    router as visit_progress_router,
)
from clinicai.api.v1.routers.voice import router as voice_router
from clinicai.api.v1.routers.work_items import router as work_items_router
from clinicai.core.database import close_pool, create_pool
from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.core.logging import setup_logging
from clinicai.core.sentry import init_sentry
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.checkpointer import make_checkpointer
from clinicai.orchestrator.service import OrchestratorService
from clinicai.voice.transcribe import PhoWhisperTranscriber

# Initialize structured JSON logging
setup_logging()
# Initialize Sentry APM (reads SENTRY_DSN; no-op if unset)
init_sentry()

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the asyncpg pool + LangGraph checkpointer over the app lifetime."""
    app.state.db_pool = await create_pool()
    try:
        async with AsyncExitStack() as stack:
            checkpointer = await stack.enter_async_context(make_checkpointer())

            llm_client = AnthropicClient()
            stack.push_async_callback(llm_client.close)
            app.state.llm_client = llm_client

            # Voice transcriber (on-prem PhoWhisper). Construction nhẹ — model nạp
            # lazy ở lần transcribe đầu, nên app boot được kể cả khi chưa cài model.
            app.state.voice_transcriber = PhoWhisperTranscriber()

            default_location_id_env = os.environ.get("DEFAULT_LOCATION_ID")
            scheduling_location_id: UUID | None = (
                UUID(default_location_id_env) if default_location_id_env else None
            )

            app.state.orchestrator_service = OrchestratorService(
                checkpointer=checkpointer,
                llm_client=llm_client,
                scheduling_pool=app.state.db_pool,
                scheduling_location_id=scheduling_location_id,
                lab_triage_pool=app.state.db_pool,
                task_manager_pool=app.state.db_pool,
            )

            logger.info("app_startup_complete")
            yield
            logger.info("app_shutdown_starting")
    finally:
        await close_pool(app.state.db_pool)


app = FastAPI(
    title="ClinicAI",
    description="AI-powered clinic management for Dr4women",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware stack (outermost → innermost) ---
# 1. Request-ID: assign/reuse X-Request-ID, bind to structlog context.
app.add_middleware(RequestIdMiddleware)
# 2. API-key gate: reject unauthenticated callers (see api.auth).
# 2. Timing: outside the API-key gate so rejected floods are visible too.
app.add_middleware(TimingMiddleware)

app.middleware("http")(api_key_middleware)
# 3. DB-error guard: catch transient connection errors → 503 (no crash loop).
app.add_middleware(DbErrorMiddleware)

app.include_router(health_router)
app.include_router(identity_router, prefix="/api/v1", tags=["identity"])
app.include_router(queue_router, prefix="/api/v1", tags=["queue"])
# Bảng điều khiển chủ sản phẩm — router tự từ chối khi APP_ENV=production.
app.include_router(console_router, prefix="/api/v1", tags=["console"])
app.include_router(patients_router, prefix="/api/v1")
app.include_router(staff_router, prefix="/api/v1", tags=["staff"])
app.include_router(scheduling_router, prefix="/api/v1", tags=["scheduling"])
app.include_router(payment_router, prefix="/api/v1", tags=["payment"])
app.include_router(pharmacy_router, prefix="/api/v1", tags=["pharmacy"])
app.include_router(episodes_router, prefix="/api/v1", tags=["episodes"])
app.include_router(work_items_router, prefix="/api/v1", tags=["work-items"])
app.include_router(tools_router, prefix="/api/v1")
app.include_router(orchestrator_router, prefix="/api/v1")
app.include_router(brief_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(ops_router, prefix="/api/v1", tags=["ops"])
app.include_router(lab_router, prefix="/api/v1")
app.include_router(ultrasound_router, prefix="/api/v1", tags=["ultrasound"])
app.include_router(clinical_forms_router, prefix="/api/v1", tags=["clinical-forms"])
app.include_router(clinical_records_router, prefix="/api/v1", tags=["clinical-records"])
app.include_router(cskh_router, prefix="/api/v1", tags=["cskh"])
app.include_router(booking_router, prefix="/api/v1", tags=["booking"])
app.include_router(config_router, prefix="/api/v1", tags=["config"])
app.include_router(service_log_router, prefix="/api/v1", tags=["service-log"])
app.include_router(visit_progress_router, prefix="/api/v1", tags=["visit-progress"])
app.include_router(voice_router, prefix="/api/v1")


@app.exception_handler(asyncpg.exceptions.ExclusionViolationError)
async def exclusion_violation_handler(
    request: Request, exc: asyncpg.exceptions.ExclusionViolationError
) -> JSONResponse:
    """Global handler for database exclusion violation errors (HTTP 409)."""
    logger.warning(
        "exclusion_violation",
        message="Lịch hẹn xung đột khung giờ với appointment khác",
    )
    return JSONResponse(
        status_code=409,
        content={
            "error": "CONFLICT_ERROR",
            "message": "Lịch hẹn xung đột khung giờ với appointment khác",
        },
    )


@app.exception_handler(asyncpg.exceptions.UniqueViolationError)
async def unique_violation_handler(
    request: Request, exc: asyncpg.exceptions.UniqueViolationError
) -> JSONResponse:
    """Global handler for database unique constraint violations (HTTP 409)."""
    logger.warning(
        "unique_violation",
        message="Resource already exists",
    )
    return JSONResponse(
        status_code=409,
        content={
            "error": "CONFLICT_ERROR",
            "message": "Resource already exists",
        },
    )


@app.exception_handler(ClinicAIBaseException)
async def clinicai_exception_handler(
    request: Request, exc: ClinicAIBaseException
) -> JSONResponse:
    """Global handler for all custom ClinicAI exceptions."""
    logger.warning(
        "clinicai_exception",
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": exc.message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global handler for all unhandled exceptions."""
    # Capture full stack trace in structured JSON logs without leaking it to clients
    logger.exception(
        "unhandled_exception",
        message=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred.",
        },
    )
