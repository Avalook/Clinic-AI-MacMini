"""Tool: task.query_tasks — filtered read of the staff_task table.

Pure read-only. Composes a dynamic WHERE clause from optional filters and
a whitelisted ORDER BY. All values flow through asyncpg parameters; no
user input is concatenated into the SQL string.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from clinicai.tools._common.context import TraceContext
from clinicai.tools.task.create_task import TaskRow

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

OrderBy = Literal["due_asc", "created_desc"]

_ORDER_BY_MAP: dict[str, str] = {
    "due_asc": "due_at ASC NULLS LAST",
    "created_desc": "created_at DESC",
}

_SELECT_COLUMNS = (
    "task_id, location_id, task_type, priority, status, "
    "assigned_to, source_type, source_id, title, description, "
    "due_at, sla_hours, completed_at, created_at, updated_at"
)


class QueryTasksFilter(BaseModel):
    """Filter set for query_tasks. All fields optional except limit/order_by."""

    location_id: UUID | None = None
    assigned_to: UUID | None = None
    status: str | None = None
    task_type: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    overdue_only: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    order_by: OrderBy = "due_asc"


async def query_tasks(
    pool: asyncpg.Pool,
    filters: QueryTasksFilter,
    trace: TraceContext,
) -> list[TaskRow]:
    """Query staff_task with optional filters.

    `overdue_only=True` adds `due_at < NOW() AND status = 'PENDING'`.
    ORDER BY is whitelisted via `_ORDER_BY_MAP`.

    Args:
        pool: asyncpg connection pool.
        filters: validated filter set.
        trace: per-invocation TraceContext.

    Returns:
        List of TaskRow matching the filters, possibly empty.

    Raises:
        asyncpg errors propagate unchanged.
    """
    where_clauses: list[str] = []
    params: list[object] = []
    idx = 1

    if filters.location_id is not None:
        where_clauses.append(f"location_id = ${idx}")
        params.append(filters.location_id)
        idx += 1

    if filters.assigned_to is not None:
        where_clauses.append(f"assigned_to = ${idx}")
        params.append(filters.assigned_to)
        idx += 1

    if filters.status is not None:
        where_clauses.append(f"status = ${idx}")
        params.append(filters.status)
        idx += 1

    if filters.task_type is not None:
        where_clauses.append(f"task_type = ${idx}")
        params.append(filters.task_type)
        idx += 1

    if filters.source_type is not None:
        where_clauses.append(f"source_type = ${idx}")
        params.append(filters.source_type)
        idx += 1

    if filters.source_id is not None:
        where_clauses.append(f"source_id = ${idx}")
        params.append(filters.source_id)
        idx += 1

    if filters.overdue_only:
        where_clauses.append("due_at < NOW() AND status = 'PENDING'")

    where_sql = f"WHERE {' AND '.join(where_clauses)} " if where_clauses else ""
    order_by_sql = _ORDER_BY_MAP[filters.order_by]
    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM staff_task "
        f"{where_sql}"
        f"ORDER BY {order_by_sql} "
        f"LIMIT ${idx}"
    )
    params.append(filters.limit)

    logger.debug(
        "tool.task.query_tasks",
        extra={
            "trace_id": str(trace.trace_id),
            "filter_count": len(where_clauses),
            "limit": filters.limit,
            "overdue_only": filters.overdue_only,
        },
    )

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [TaskRow.model_validate(dict(row)) for row in rows]
