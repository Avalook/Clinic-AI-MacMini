"""Task Manager sub-graph builder.

Flow:
    START
      → create_task    (conditional: skipped when state.task_input is None)
      → query_tasks    (always runs; pass-through when no filter / no recent create)
      → check_sla      (always runs; pass-through when no queried_tasks)
      → update_task_status (conditional: skipped when state.update_input is None)
      → END

The graph is intentionally linear with node-level no-op fallthrough rather
than runtime branching for two reasons:
  (a) Each node already encodes its own "skip when input missing" rule,
      keeping the routing surface tiny;
  (b) Tests can drive any subset (create-only / query-only / full) without
      knowing internal step names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from clinicai.graphs.task_manager.nodes import (
    make_check_sla_node,
    make_create_task_node,
    make_query_tasks_node,
    make_update_task_status_node,
)
from clinicai.graphs.task_manager.state import TaskManagerState

if TYPE_CHECKING:
    import asyncpg


def build_task_manager_subgraph(pool: "asyncpg.Pool") -> Any:
    """Compile the task_manager sub-graph with a closure-injected pool."""
    sg = StateGraph(TaskManagerState)

    sg.add_node("create_task", make_create_task_node(pool))
    sg.add_node("query_tasks", make_query_tasks_node(pool))
    sg.add_node("check_sla", make_check_sla_node(pool))
    sg.add_node("update_task_status", make_update_task_status_node(pool))

    sg.add_edge(START, "create_task")
    sg.add_edge("create_task", "query_tasks")
    sg.add_edge("query_tasks", "check_sla")
    sg.add_edge("check_sla", "update_task_status")
    sg.add_edge("update_task_status", END)

    return sg.compile()
