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

from typing import Annotated, Any, cast
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES,
    DOCTOR_ROLES,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.graphs.lab_triage import build_lab_triage_subgraph
from clinicai.graphs.lab_triage.state import LabTriageState
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.services.lab_order_service import LabOrderService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/lab", tags=["lab"])

# Ordering a test is a doctor's decision (W5, ADR-0012).
_ORDER_GUARD = require_role(*DOCTOR_ROLES)
# Entering a result is clinical work: doctors, nurses and the medical secretary.
# Reception and management are deliberately excluded.
_RESULT_GUARD = require_role(*CLINICAL_WRITE_ROLES)


class LabOrderRequest(BaseModel):
    """Order a lab test for a patient."""

    clinic_patient_id: UUID
    test_name: str = Field(min_length=1, max_length=200)
    appointment_id: UUID | None = None


class LabResultEntryRequest(BaseModel):
    """Attach a summary and/or the provider's document to a pending result."""

    result_value: str | None = Field(default=None, max_length=4000)
    result_link: str | None = Field(default=None, max_length=2000)
    lab_provider: str | None = Field(default=None, max_length=200)


@router.post("/orders", status_code=201)
async def order_lab_test(
    body: LabOrderRequest,
    identity: StaffIdentity = Depends(_ORDER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Create a PENDING lab_result — the doctor has asked for a test."""
    lab_result_id = await LabOrderService(pool).order_test(
        clinic_patient_id=str(body.clinic_patient_id),
        test_name=body.test_name,
        appointment_id=str(body.appointment_id) if body.appointment_id else None,
        identity=identity,
    )
    return {"ok": True, "lab_result_id": lab_result_id}


@router.patch("/results/{lab_result_id}")
async def enter_lab_result(
    lab_result_id: UUID,
    body: LabResultEntryRequest,
    identity: StaffIdentity = Depends(_RESULT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Record what came back. Never finalises — that is a separate gate."""
    await LabOrderService(pool).enter_result(
        lab_result_id=str(lab_result_id),
        result_value=body.result_value,
        result_link=body.result_link,
        lab_provider=body.lab_provider,
        identity=identity,
    )
    return {"ok": True}


def get_llm_client(request: Request) -> AnthropicClient:
    """FastAPI dependency: yields the application's AnthropicClient singleton."""
    return cast(AnthropicClient, request.app.state.llm_client)


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
    identity: Annotated[StaffIdentity, Depends(get_current_identity)],
    llm_client: Annotated[AnthropicClient, Depends(get_llm_client)],
) -> LabTriageResponse:
    """Run lab_triage on a single lab_result_id, enforcing the GROUP_C gate.

    Returns the triage outcome. Raises SafetyGateError (HTTP 403) when
    the result is GROUP_C and not yet reviewed by a doctor.
    """
    graph = build_lab_triage_subgraph(pool=pool, llm_client=llm_client)
    state = LabTriageState(
        lab_result_id=lab_result_id,
        clinic_id=UUID(identity.clinic_id) if identity.clinic_id else None,
    )
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
