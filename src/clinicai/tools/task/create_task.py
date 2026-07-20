"""Tool: task.create_task — insert a single staff_task row.

Pure write-only helper used by the task_manager sub-graph (P9.3) and the
lab_triage hard_block path (P9.3) to enqueue work for clinic staff. The
function is parameterized end-to-end (no f-string SQL value interpolation).

Note: `location_id` replaces the spec's earlier `clinic_id` because the
codebase has no `clinic` table — `clinic_location` is the smallest tenancy
unit. See migration 016.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

TaskPriority = Literal["URGENT", "HIGH", "NORMAL"]
TaskStatus = Literal["PENDING", "IN_PROGRESS", "DONE", "CANCELLED"]

_INSERT_SQL = """
    INSERT INTO staff_task (
        location_id, task_type, priority, assigned_to,
        source_type, source_id, title, description,
        due_at, sla_hours
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    RETURNING task_id, location_id, task_type, priority, status,
              assigned_to, source_type, source_id, title, description,
              due_at, sla_hours, completed_at, created_at, updated_at
"""


class CreateTaskInput(BaseModel):
    """Input schema for create_task."""

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


class TaskRow(BaseModel):
    """Thin projection of a staff_task row.

    Mirrors the columns declared in migration 016.
    """

    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    location_id: UUID | None
    task_type: str
    priority: str
    status: str
    assigned_to: UUID | None
    source_type: str | None
    source_id: UUID | None
    title: str
    description: str | None
    due_at: datetime | None
    sla_hours: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


async def create_task(
    pool: asyncpg.Pool,
    input: CreateTaskInput,
    trace: TraceContext,
) -> TaskRow:
    """Insert a single staff_task row and return it.

    Pure write. No LLM, no event emission — callers compose those side-
    effects separately. asyncpg errors propagate unchanged.

    Args:
        pool: asyncpg connection pool (caller-managed lifecycle).
        input: validated task fields.
        trace: per-invocation TraceContext for observability.

    Returns:
        The inserted row as TaskRow, with DB-populated defaults
        (task_id, status, created_at, updated_at).
    """
    logger.debug(
        "tool.task.create_task",
        extra={
            "trace_id": str(trace.trace_id),
            "task_type": input.task_type,
            "priority": input.priority,
            "source_type": input.source_type,
        },
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _INSERT_SQL,
            input.location_id,
            input.task_type,
            input.priority,
            input.assigned_to,
            input.source_type,
            input.source_id,
            input.title,
            input.description,
            input.due_at,
            input.sla_hours,
        )

    return TaskRow.model_validate(dict(row))
