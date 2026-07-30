"""Pre-visit brief API (P9.5).

POST /brief/{clinic_patient_id} → BS-facing structured brief + markdown.

On-demand only at this phase. The future cron / event-driven path is
intentionally deferred to P13 (see comment in orchestrator/stubs.py).
"""

from __future__ import annotations

import time
from typing import Annotated, cast
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from clinicai.api.identity import (
    DOCTOR_ROLES,
    ClinicRole,
    StaffIdentity,
    require_role,
)
from clinicai.api.rate_limit import InMemoryRateLimiter
from clinicai.core.database import get_db_pool
from clinicai.graphs.pre_visit_brief import (
    PreVisitBriefState,
    build_pre_visit_brief_subgraph,
)
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.tools.brief.generate_brief import PreVisitBrief

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/brief", tags=["brief"])
_BRIEF_GUARD = require_role(*DOCTOR_ROLES, ClinicRole.TKYK)
BRIEF_RATE_LIMIT = InMemoryRateLimiter(
    scope="pre-visit-brief",
    limit=20,
    window_seconds=60,
)


async def _can_generate_brief(
    pool: asyncpg.Pool,
    *,
    clinic_patient_id: UUID,
    identity: StaffIdentity,
) -> bool:
    """Keep direct API callers inside the same patient relationship as the UI."""
    if identity.role is ClinicRole.TKYK:
        return bool(
            await pool.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                      FROM patient p
                     WHERE p.clinic_patient_id = $1
                       AND p.clinic_id = $2::uuid
                       AND p.is_active
                )
                """,
                clinic_patient_id,
                identity.clinic_id,
            )
        )
    return bool(
        await pool.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM appointment a
                  JOIN patient p
                    ON p.clinic_patient_id = a.clinic_patient_id
                   AND p.clinic_id = a.clinic_id
                 WHERE a.clinic_patient_id = $1
                   AND a.clinic_id = $2::uuid
                   AND a.doctor_id = $3::uuid
                   AND p.is_active
            )
            """,
            clinic_patient_id,
            identity.clinic_id,
            identity.staff_id,
        )
    )


def get_llm_client(request: Request) -> AnthropicClient:
    """FastAPI dependency: yields the application's AnthropicClient singleton."""
    return cast(AnthropicClient, request.app.state.llm_client)


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
    identity: Annotated[StaffIdentity, Depends(_BRIEF_GUARD)],
    _rate_limit: Annotated[None, Depends(BRIEF_RATE_LIMIT)],
) -> BriefResponse:
    """Generate a pre-visit brief for the given patient.

    Returns 404 when the patient does not exist, 502 when the LLM fails
    to produce a valid brief.
    """
    start = time.monotonic()
    if not await _can_generate_brief(
        pool,
        clinic_patient_id=clinic_patient_id,
        identity=identity,
    ):
        # Do not reveal whether the patient exists in another clinic or belongs
        # to another doctor's list.
        raise HTTPException(
            status_code=404,
            detail="patient_not_found_or_not_assigned",
        )

    graph = build_pre_visit_brief_subgraph(pool=pool, llm_client=llm_client)
    state = PreVisitBriefState(
        clinic_patient_id=clinic_patient_id,
        clinic_id=UUID(identity.clinic_id),
    )
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
