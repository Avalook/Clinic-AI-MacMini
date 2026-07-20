"""Tool: task.check_sla — compute SLA overdue / remaining for one task."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

_SECONDS_PER_HOUR = 3600.0

_FETCH_SQL = """
    SELECT task_id, status, due_at
      FROM staff_task
     WHERE task_id = $1
     LIMIT 1
"""

_TERMINAL_STATUSES = frozenset({"DONE", "CANCELLED"})


class SlaCheckResult(BaseModel):
    """Output of check_task_sla."""

    task_id: UUID
    is_overdue: bool
    hours_remaining: float | None
    hours_overdue: float | None
    status: str


class TaskNotFoundError(LookupError):
    """Raised when the target task_id does not exist."""


def _to_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (assume UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def check_task_sla(
    pool: asyncpg.Pool,
    task_id: UUID,
    trace: TraceContext,
) -> SlaCheckResult:
    """Check SLA for a single task.

    A task is overdue when `due_at < NOW()` AND status NOT IN
    ('DONE', 'CANCELLED'). Terminal statuses (DONE / CANCELLED) and tasks
    without `due_at` return is_overdue=False with both hour fields None.

    Args:
        pool: asyncpg connection pool.
        task_id: UUID of the task to inspect.
        trace: per-invocation TraceContext.

    Returns:
        SlaCheckResult.

    Raises:
        TaskNotFoundError: if the task does not exist.
        asyncpg errors propagate unchanged.
    """
    logger.debug(
        "tool.task.check_sla",
        extra={
            "trace_id": str(trace.trace_id),
            "task_id": str(task_id),
        },
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(_FETCH_SQL, task_id)

    if row is None:
        raise TaskNotFoundError(f"staff_task not found: task_id={task_id}")

    status: str = row["status"]
    due_at: datetime | None = row["due_at"]

    # Terminal status or no due date → no SLA window to evaluate.
    if status in _TERMINAL_STATUSES or due_at is None:
        return SlaCheckResult(
            task_id=task_id,
            is_overdue=False,
            hours_remaining=None,
            hours_overdue=None,
            status=status,
        )

    now = datetime.now(tz=timezone.utc)
    due_aware = _to_aware(due_at)
    delta_seconds = (due_aware - now).total_seconds()

    if delta_seconds < 0:
        return SlaCheckResult(
            task_id=task_id,
            is_overdue=True,
            hours_remaining=None,
            hours_overdue=abs(delta_seconds) / _SECONDS_PER_HOUR,
            status=status,
        )

    return SlaCheckResult(
        task_id=task_id,
        is_overdue=False,
        hours_remaining=delta_seconds / _SECONDS_PER_HOUR,
        hours_overdue=None,
        status=status,
    )
