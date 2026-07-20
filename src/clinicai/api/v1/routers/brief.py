"""Pre-visit brief API (P9.5).

POST /brief/{clinic_patient_id} → BS-facing structured brief + markdown.

On-demand only at this phase. The future cron / event-driven path is
intentionally deferred to P13 (see comment in orchestrator/stubs.py).
"""

from __future__ import annotations

import time
from typing import Annotated
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from clinicai.core.database import get_db_pool
from clinicai.graphs.pre_visit_brief import (
    PreVisitBriefState,
    build_pre_visit_brief_subgraph,
)
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.tools.brief.generate_brief import PreVisitBrief

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/brief", tags=["brief"])


def get_llm_client(request: Request) -> AnthropicClient:
    """FastAPI dependency: yields the application's AnthropicClient singleton."""
    return request.app.state.llm_client


class BriefResponse(BaseModel):
    """API response wrapper: structured brief + rendered markdown + timing."""

    brief: PreVisitBrief
    markdown: str
    elapsed_ms: int


@router.post("/{clinic_patient_id}", response_model=BriefResponse)
async def generate_pre_visit_brief(
    clinic_patient_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
    llm_client: Annotated[AnthropicClient, Depends(get_llm_client)],
) -> BriefResponse:
    """Generate a pre-visit brief for the given patient.

    Returns 404 when the patient does not exist, 502 when the LLM fails
    to produce a valid brief.
    """
    start = time.monotonic()

    graph = build_pre_visit_brief_subgraph(pool=pool, llm_client=llm_client)
    state = PreVisitBriefState(clinic_patient_id=clinic_patient_id)
    result = await graph.ainvoke(state)

    error = result.get("error") if isinstance(result, dict) else None
    if error:
        logger.warning(
            "api.brief.error",
            clinic_patient_id=str(clinic_patient_id),
            error=error,
        )
        if error.startswith("patient_not_found"):
            raise HTTPException(status_code=404, detail=error)
        # LLM / parse failures bubble up as 502 (upstream service error).
        raise HTTPException(status_code=502, detail=error)

    brief = result.get("brief")
    markdown = result.get("brief_markdown")
    if brief is None or markdown is None:
        # Defensive: should not happen if no error was set.
        raise HTTPException(status_code=500, detail="brief assembly incomplete")

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return BriefResponse(
        brief=brief,
        markdown=markdown,
        elapsed_ms=elapsed_ms,
    )
