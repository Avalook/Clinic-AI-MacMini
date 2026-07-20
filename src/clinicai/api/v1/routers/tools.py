"""FastAPI router mounting the tools layer for OpenAPI documentation.

These endpoints are NOT production-grade orchestration. They exist so graph
developers can read OpenAPI /docs and exercise each tool with curl. Real
clients of the tools layer call the Python functions directly.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request

from clinicai.core.database import get_db_pool
from clinicai.event_bus.publisher import IEventPublisher, MockEventPublisher
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.tools._common.context import new_trace
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
    TaskRow,
    create_task,
)
from clinicai.tools.task.query_tasks import QueryTasksFilter, query_tasks
from clinicai.tools.task.update_task_status import (
    UpdateTaskStatusInput,
    update_task_status,
)

router = APIRouter(prefix="/tools", tags=["tools"])

# Module-level publisher used by /tools/event-log/append. MockEventPublisher
# is intentional: this router is a dev/doc surface, not the production hot
# path — real publishing is wired in worker entrypoints.
_PUBLISHER: IEventPublisher = MockEventPublisher()


def get_event_publisher() -> IEventPublisher:
    """FastAPI dependency: yields the dev-mode publisher."""
    return _PUBLISHER


def get_llm_client(request: Request) -> AnthropicClient:
    """FastAPI dependency: yields the application's AnthropicClient singleton."""
    return request.app.state.llm_client


@router.post("/patient/get-summary", response_model=PatientSummaryOutput)
async def _patient_get_summary(
    input: GetPatientSummaryInput,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PatientSummaryOutput:
    return await get_patient_summary(input, pool)


@router.post("/scheduling/find-oncall", response_model=OncallStaffOutput)
async def _scheduling_find_oncall(
    input: FindOncallInput,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> OncallStaffOutput:
    return await find_oncall_staff(input, pool)


@router.post("/event-log/append", response_model=AppendEventOutput)
async def _event_log_append(
    input: AppendEventInput,
    pool: asyncpg.Pool = Depends(get_db_pool),
    publisher: IEventPublisher = Depends(get_event_publisher),
) -> AppendEventOutput:
    return await append_event(input, pool, publisher)


@router.post("/kb/read-policy", response_model=PolicyOutput)
async def _kb_read_policy(
    input: ReadPolicyInput,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PolicyOutput:
    return await read_policy(input, pool)


@router.post("/communication/send-zalo", response_model=SendZaloOutput)
async def _communication_send_zalo(input: SendZaloInput) -> SendZaloOutput:
    return await send_zalo_message(input)


@router.post("/lab/classify", response_model=ClassifyResult)
async def _lab_classify(
    row: LabResultRow,
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
    input: CreateTaskInput,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> TaskRow:
    return await create_task(pool, input, new_trace())


@router.post("/task/query", response_model=list[TaskRow])
async def _task_query(
    filters: QueryTasksFilter,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[TaskRow]:
    return await query_tasks(pool, filters, new_trace())


@router.post("/task/update-status", response_model=TaskRow)
async def _task_update_status(
    input: UpdateTaskStatusInput,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> TaskRow:
    return await update_task_status(pool, input, new_trace())


@router.get("/task/check-sla/{task_id}", response_model=SlaCheckResult)
async def _task_check_sla(
    task_id: UUID,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> SlaCheckResult:
    return await check_task_sla(pool, task_id, new_trace())
