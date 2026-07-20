"""Nodes for task_manager sub-graph.

Closure-factory pattern: each node binds an asyncpg pool at build time and
returns an async function that operates on TaskManagerState. Nodes are
deliberately small — every business decision lives in the tool layer
(`clinicai.tools.task.*`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from clinicai.graphs.task_manager.state import TaskManagerState
from clinicai.tools._common.context import new_trace
from clinicai.tools.task.check_sla import (
    SlaCheckResult,
    check_task_sla,
)
from clinicai.tools.task.check_sla import (
    TaskNotFoundError as SlaTaskNotFoundError,
)
from clinicai.tools.task.create_task import create_task
from clinicai.tools.task.query_tasks import QueryTasksFilter, query_tasks
from clinicai.tools.task.update_task_status import (
    TaskNotFoundError,
    update_task_status,
)

if TYPE_CHECKING:
    import asyncpg

logger = structlog.get_logger(__name__)


def make_create_task_node(pool: "asyncpg.Pool"):
    """Build a node that inserts state.task_input via the create_task tool.

    No-op (pass-through) when state.task_input is None.
    """

    async def create_task_node(state: TaskManagerState) -> dict[str, Any]:
        if state.task_input is None:
            logger.debug("task_manager.create_task.skip")
            return {"turn_count": state.turn_count + 1}

        trace = new_trace()
        logger.info(
            "task_manager.create_task",
            task_type=state.task_input.task_type,
            priority=state.task_input.priority,
            trace_id=str(trace.trace_id),
        )

        created = await create_task(pool, state.task_input, trace)
        return {
            "created_task": created,
            "turn_count": state.turn_count + 1,
        }

    return create_task_node


def make_query_tasks_node(pool: "asyncpg.Pool"):
    """Build a node that runs query_tasks with state.query_filter.

    When `state.query_filter` is absent but `state.created_task` exists,
    the node falls back to filtering by that task's `source_type` /
    `source_id` so callers can chain create → query → check_sla in one
    invocation. Without either input, the node returns an empty list.
    """

    async def query_tasks_node(state: TaskManagerState) -> dict[str, Any]:
        filters: QueryTasksFilter | None = (
            state.query_filter
            if isinstance(state.query_filter, QueryTasksFilter)
            else None
        )

        if filters is None and state.created_task is not None:
            filters = QueryTasksFilter(
                source_type=state.created_task.source_type,
                source_id=state.created_task.source_id,
            )

        if filters is None:
            logger.debug("task_manager.query_tasks.skip")
            return {
                "queried_tasks": [],
                "turn_count": state.turn_count + 1,
            }

        trace = new_trace()
        logger.info(
            "task_manager.query_tasks",
            limit=filters.limit,
            overdue_only=filters.overdue_only,
            trace_id=str(trace.trace_id),
        )

        rows = await query_tasks(pool, filters, trace)
        return {
            "queried_tasks": rows,
            "turn_count": state.turn_count + 1,
        }

    return query_tasks_node


def make_check_sla_node(pool: "asyncpg.Pool"):
    """Build a node that calls check_task_sla for every queried_task.

    No-op when state.queried_tasks is empty.
    """

    async def check_sla_node(state: TaskManagerState) -> dict[str, Any]:
        if not state.queried_tasks:
            return {"turn_count": state.turn_count + 1}

        trace = new_trace()
        results: list[SlaCheckResult] = []
        for task in state.queried_tasks:
            try:
                results.append(await check_task_sla(pool, task.task_id, trace))
            except SlaTaskNotFoundError:
                # Race: task vanished between query and SLA check. Skip rather
                # than fail the whole loop.
                logger.warning(
                    "task_manager.check_sla.task_vanished",
                    task_id=str(task.task_id),
                )
                continue

        logger.info(
            "task_manager.check_sla",
            checked=len(results),
            overdue=sum(1 for r in results if r.is_overdue),
            trace_id=str(trace.trace_id),
        )
        return {
            "sla_results": results,
            "turn_count": state.turn_count + 1,
        }

    return check_sla_node


def make_update_task_status_node(pool: "asyncpg.Pool"):
    """Build a node that applies state.update_input via update_task_status.

    No-op when state.update_input is None. TaskNotFoundError is caught and
    surfaced via state.error rather than propagated, so a partial workflow
    (e.g. create succeeded, update target missing) still terminates.
    """

    async def update_task_status_node(state: TaskManagerState) -> dict[str, Any]:
        if state.update_input is None:
            return {"turn_count": state.turn_count + 1}

        trace = new_trace()
        logger.info(
            "task_manager.update_task_status",
            task_id=str(state.update_input.task_id),
            new_status=state.update_input.status,
            trace_id=str(trace.trace_id),
        )

        try:
            updated = await update_task_status(pool, state.update_input, trace)
        except TaskNotFoundError as exc:
            logger.warning(
                "task_manager.update_task_status.not_found",
                task_id=str(state.update_input.task_id),
                error=str(exc),
            )
            return {
                "error": f"task_not_found:{state.update_input.task_id}",
                "turn_count": state.turn_count + 1,
            }

        return {
            "updated_task": updated,
            "turn_count": state.turn_count + 1,
        }

    return update_task_status_node
