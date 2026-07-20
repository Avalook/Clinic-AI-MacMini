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
from clinicai.api.v1.health import router as health_router
from clinicai.api.v1.patients import router as patients_router
from clinicai.api.v1.routers.brief import router as brief_router
from clinicai.api.v1.routers.lab import router as lab_router
from clinicai.api.v1.routers.orchestrator import router as orchestrator_router
from clinicai.api.v1.routers.scheduling import router as scheduling_router
from clinicai.api.v1.routers.staff import router as staff_router
from clinicai.api.v1.routers.tools import router as tools_router
from clinicai.api.v1.routers.voice import router as voice_router
from clinicai.core.database import close_pool, create_pool
from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.core.logging import setup_logging
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.checkpointer import make_checkpointer
from clinicai.orchestrator.service import OrchestratorService
from clinicai.voice.transcribe import PhoWhisperTranscriber

# Initialize structured JSON logging
setup_logging()

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

# Gate every non-health route on BACKEND_API_KEY (see api.auth).
app.middleware("http")(api_key_middleware)

app.include_router(health_router)
app.include_router(patients_router, prefix="/api/v1")
app.include_router(staff_router, prefix="/api/v1", tags=["staff"])
app.include_router(scheduling_router, prefix="/api/v1", tags=["scheduling"])
app.include_router(tools_router, prefix="/api/v1")
app.include_router(orchestrator_router, prefix="/api/v1")
app.include_router(brief_router, prefix="/api/v1")
app.include_router(lab_router, prefix="/api/v1")
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
