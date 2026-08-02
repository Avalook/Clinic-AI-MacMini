"""FastAPI router mounting the tools layer for OpenAPI documentation.

These endpoints are NOT production-grade orchestration. They exist so graph
developers can read OpenAPI /docs and exercise each tool with curl. Real
clients of the tools layer call the Python functions directly.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, cast
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.event_bus.publisher import IEventPublisher, MockEventPublisher
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.tools._common.context import TraceContext, new_trace
from clinicai.tools.communication.send_zalo import (
    SendZaloInput,
    SendZaloOutput,
    send_zalo_message,
)
from clinicai.tools.event_log.append import (
    AppendEventInput,
    AppendEventOutput,
    append_event,
)
from clinicai.tools.kb.read_policy import (
    PolicyOutput,
    ReadPolicyInput,
    read_policy,
)
from clinicai.tools.lab.classify import (
    ClassifyResult,
    classify_lab_result,
)
from clinicai.tools.lab.query_lab_result import LabResultRow
from clinicai.tools.patient.get_summary import (
    GetPatientSummaryInput,
    PatientSummaryOutput,
    get_patient_summary,
)
from clinicai.tools.scheduling.find_oncall import (
    FindOncallInput,
    OncallStaffOutput,
    find_oncall_staff,
)
from clinicai.tools.task.check_sla import SlaCheckResult, check_task_sla
from clinicai.tools.task.create_task import (
    CreateTaskInput,
    TaskPriority,
    TaskRow,
    create_task,
)
from clinicai.tools.task.query_tasks import (
    OrderBy,
    QueryTasksFilter,
    query_tasks,
)
from clinicai.tools.task.update_task_status import (
    UpdateTaskStatusInput,
    update_task_status,
)

router = APIRouter(prefix="/tools", tags=["tools"])

# Module-level publisher used by /tools/event-log/append. MockEventPublisher
# is intentional: this router is a dev/doc surface, not the production hot
# path — real publishing is wired in worker entrypoints.
_PUBLISHER: IEventPublisher = MockEventPublisher()
_TOOLS_MANAGEMENT_GUARD = require_role(ClinicRole.MANAGEMENT)
_TOOLS_HTTP_ENVIRONMENTS = frozenset({"dev", "development", "local", "test", "testing"})


class _TenantlessRequest(BaseModel):
    """HTTP input whose tenant can only come from the verified identity."""

    model_config = ConfigDict(extra="forbid")


class PatientSummaryRequest(_TenantlessRequest):
    patient_id: UUID
    ctx: TraceContext


class FindOncallRequest(_TenantlessRequest):
    work_session_id: UUID
    ctx: TraceContext


class AppendEventRequest(_TenantlessRequest):
    event_type: str
    entity_type: str
    entity_id: UUID
    payload: dict[str, Any]
    ctx: TraceContext


class CreateTaskRequest(_TenantlessRequest):
    location_id: UUID | None = None
    task_type: str
    priority: TaskPriority = "NORMAL"
    assigned_to: UUID | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    title: str
    description: str | None = None
    due_at: datetime | None = None
    sla_hours: int = 24


class QueryTasksRequest(_TenantlessRequest):
    location_id: UUID | None = None
    assigned_to: UUID | None = None
    status: str | None = None
    task_type: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    overdue_only: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    order_by: OrderBy = "due_asc"


def _clinic_uuid(identity: StaffIdentity) -> UUID:
    """Return the tenant chosen by verified JWT/membership lookup."""
    return UUID(identity.clinic_id)


def _require_tools_access(
    identity: StaffIdentity = Depends(_TOOLS_MANAGEMENT_GUARD),
) -> StaffIdentity:
    """Keep this dev/doc-only HTTP surface out of staging and production."""
    app_env = os.environ.get("APP_ENV", "").strip().lower()
    if app_env not in _TOOLS_HTTP_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    return identity


def get_event_publisher() -> IEventPublisher:
    """FastAPI dependency: yields the dev-mode publisher."""
    return _PUBLISHER


def get_llm_client(request: Request) -> AnthropicClient:
    """FastAPI dependency: yields the application's AnthropicClient singleton."""
    return cast(AnthropicClient, request.app.state.llm_client)


@router.post("/patient/get-summary", response_model=PatientSummaryOutput)
async def _patient_get_summary(
    input: PatientSummaryRequest,
    identity: StaffIdentity = Depends(_require_tools_access),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PatientSummaryOutput:
    trusted_input = GetPatientSummaryInput(
        **input.model_dump(),
        clinic_id=_clinic_uuid(identity),
    )
    return await get_patient_summary(trusted_input, pool)


@router.post("/scheduling/find-oncall", response_model=OncallStaffOutput)
async def _scheduling_find_oncall(
    input: FindOncallRequest,
    identity: StaffIdentity = Depends(_require_tools_access),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> OncallStaffOutput:
    trusted_input = FindOncallInput(
        **input.model_dump(),
        clinic_id=_clinic_uuid(identity),
    )
    return await find_oncall_staff(trusted_input, pool)


@router.post("/event-log/append", response_model=AppendEventOutput)
async def _event_log_append(
    input: AppendEventRequest,
    identity: StaffIdentity = Depends(_require_tools_access),
    pool: asyncpg.Pool = Depends(get_db_pool),
    publisher: IEventPublisher = Depends(get_event_publisher),
) -> AppendEventOutput:
    trusted_input = AppendEventInput(
        **input.model_dump(),
        clinic_id=_clinic_uuid(identity),
        actor_staff_id=UUID(identity.staff_id),
    )
    return await append_event(trusted_input, pool, publisher)


@router.post("/kb/read-policy", response_model=PolicyOutput)
async def _kb_read_policy(
    input: ReadPolicyInput,
    _identity: StaffIdentity = Depends(_require_tools_access),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PolicyOutput:
    return await read_policy(input, pool)


@router.post("/communication/send-zalo", response_model=SendZaloOutput)
async def _communication_send_zalo(
    input: SendZaloInput,
    _identity: StaffIdentity = Depends(_require_tools_access),
) -> SendZaloOutput:
    return await send_zalo_message(input)


@router.post("/lab/classify", response_model=ClassifyResult)
async def _lab_classify(
    row: LabResultRow,
    _identity: StaffIdentity = Depends(_require_tools_access),
    llm_client: AnthropicClient = Depends(get_llm_client),
) -> ClassifyResult:
    """Classify a single lab result via rules + LLM fallback.

    Dev/doc surface: POST a fully-populated LabResultRow JSON; receive
    the ClassifyResult. Production callers invoke the Python function
    directly and don't go through this endpoint.
    """
    return await classify_lab_result(row, llm_client, new_trace())


@router.post("/task/create", response_model=TaskRow)
async def _task_create(
    input: CreateTaskRequest,
    identity: StaffIdentity = Depends(_require_tools_access),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> TaskRow:
    trusted_input = CreateTaskInput(
        **input.model_dump(),
        clinic_id=_clinic_uuid(identity),
    )
    return await create_task(pool, trusted_input, new_trace())


@router.post("/task/query", response_model=list[TaskRow])
async def _task_query(
    filters: QueryTasksRequest,
    identity: StaffIdentity = Depends(_require_tools_access),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[TaskRow]:
    trusted_filters = QueryTasksFilter(
        **filters.model_dump(),
        clinic_id=_clinic_uuid(identity),
    )
    return await query_tasks(pool, trusted_filters, new_trace())


@router.post("/task/update-status", response_model=TaskRow)
async def _task_update_status(
    input: UpdateTaskStatusInput,
    identity: StaffIdentity = Depends(_require_tools_access),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> TaskRow:
    return await update_task_status(pool, input, new_trace(), identity.clinic_id)


@router.get("/task/check-sla/{task_id}", response_model=SlaCheckResult)
async def _task_check_sla(
    task_id: UUID,
    identity: StaffIdentity = Depends(_require_tools_access),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> SlaCheckResult:
    return await check_task_sla(pool, task_id, new_trace(), identity.clinic_id)
