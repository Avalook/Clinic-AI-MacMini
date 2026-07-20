"""Tool: task.update_task_status — transition a staff_task between statuses.

`status='DONE'` with `completed_at=None` is auto-completed by setting
`completed_at = NOW()` at the application layer (mirroring the CHECK
constraint in migration 016 that requires `completed_at` when DONE).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel

from clinicai.tools._common.context import TraceContext
from clinicai.tools.task.create_task import TaskRow

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

TaskStatusUpdate = Literal["PENDING", "IN_PROGRESS", "DONE", "CANCELLED"]

_UPDATE_SQL = """
    UPDATE staff_task
       SET status = $2,
           completed_at = $3
     WHERE task_id = $1
    RETURNING task_id, location_id, task_type, priority, status,
              assigned_to, source_type, source_id, title, description,
              due_at, sla_hours, completed_at, created_at, updated_at
"""


class UpdateTaskStatusInput(BaseModel):
    """Input schema for update_task_status."""

    task_id: UUID
    status: TaskStatusUpdate
    completed_at: datetime | None = None
    updated_by: UUID | None = None


class TaskNotFoundError(LookupError):
    """Raised when the target task_id does not exist."""


async def update_task_status(
    pool: asyncpg.Pool,
    input: UpdateTaskStatusInput,
    trace: TraceContext,
) -> TaskRow:
    """Update a staff_task's status; auto-populate completed_at for DONE.

    Args:
        pool: asyncpg connection pool.
        input: validated update fields. `updated_by` is logged but not
            persisted in this minimal schema.
        trace: per-invocation TraceContext.

    Returns:
        The updated TaskRow.

    Raises:
        TaskNotFoundError: if no row matches `input.task_id`.
        asyncpg errors propagate unchanged.
    """
    completed_at: datetime | None = input.completed_at
    if input.status == "DONE" and completed_at is None:
        completed_at = datetime.now()
    elif input.status != "DONE":
        # Clear completed_at when transitioning out of DONE (e.g. reopen)
        completed_at = None

    logger.debug(
        "tool.task.update_task_status",
        extra={
            "trace_id": str(trace.trace_id),
            "task_id": str(input.task_id),
            "status": input.status,
            "updated_by": str(input.updated_by) if input.updated_by else None,
        },
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _UPDATE_SQL,
            input.task_id,
            input.status,
            completed_at,
        )

    if row is None:
        raise TaskNotFoundError(f"staff_task not found: task_id={input.task_id}")

    return TaskRow.model_validate(dict(row))
