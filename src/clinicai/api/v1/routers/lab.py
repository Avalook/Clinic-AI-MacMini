"""Lab triage API (T-P9.4).

POST /lab/triage/{lab_result_id} → runs the lab_triage sub-graph and
enforces the API-layer safety gate:

    triage_group == 'GROUP_C' AND reviewed_at IS NULL
        → raise SafetyGateError (HTTP 403)

The graph itself remains graceful (no raise) — it always terminates and
records the GROUP_C state on `escalation_note` + creates a LAB_REVIEW
URGENT task. This router enforces the hard medical safety gate at the
boundary: a patient-facing caller must not receive any answer until BS
has reviewed. Once reviewed_at is populated the gate releases.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.graphs.lab_triage import build_lab_triage_subgraph
from clinicai.graphs.lab_triage.state import LabTriageState
from clinicai.llm.anthropic_client import AnthropicClient

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/lab", tags=["lab"])


def get_llm_client(request: Request) -> AnthropicClient:
    """FastAPI dependency: yields the application's AnthropicClient singleton."""
    return request.app.state.llm_client


class LabTriageResponse(BaseModel):
    """Patient-facing safe response surface for a triaged lab result."""

    lab_result_id: UUID
    triage_group: str | None
    requires_doctor_review: bool
    response_to_patient: str | None
    escalation_note: str | None
    task_ids: list[UUID]
    error: str | None


def _reviewed_at_of(result: dict[str, Any]) -> Any:
    """Pull `reviewed_at` off the LabResultRow inside graph output, if any."""
    row = result.get("lab_result_row")
    return getattr(row, "reviewed_at", None) if row is not None else None


@router.post("/triage/{lab_result_id}", response_model=LabTriageResponse)
async def triage_lab_result(
    lab_result_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
    llm_client: Annotated[AnthropicClient, Depends(get_llm_client)],
) -> LabTriageResponse:
    """Run lab_triage on a single lab_result_id, enforcing the GROUP_C gate.

    Returns the triage outcome. Raises SafetyGateError (HTTP 403) when
    the result is GROUP_C and not yet reviewed by a doctor.
    """
    graph = build_lab_triage_subgraph(pool=pool, llm_client=llm_client)
    state = LabTriageState(lab_result_id=lab_result_id)
    result = await graph.ainvoke(state)

    triage_group = result.get("triage_group")
    reviewed_at = _reviewed_at_of(result)

    if triage_group == "GROUP_C" and reviewed_at is None:
        logger.warning(
            "api.lab.triage.safety_gate_blocked",
            lab_result_id=str(lab_result_id),
            triage_group=triage_group,
        )
        raise SafetyGateError(
            f"GROUP_C lab_result {lab_result_id} chưa được BS review — "
            "không thể trả kết quả cho BN."
        )

    return LabTriageResponse(
        lab_result_id=lab_result_id,
        triage_group=triage_group,
        requires_doctor_review=bool(result.get("requires_doctor_review", False)),
        response_to_patient=result.get("response_to_patient"),
        escalation_note=result.get("escalation_note"),
        task_ids=list(result.get("task_ids") or []),
        error=result.get("error"),
    )
