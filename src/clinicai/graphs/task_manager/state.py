"""State for task_manager sub-graph."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from clinicai.tools.task.check_sla import SlaCheckResult
from clinicai.tools.task.create_task import CreateTaskInput, TaskRow
from clinicai.tools.task.update_task_status import UpdateTaskStatusInput


class TaskManagerState(BaseModel):
    """State passed through task_manager sub-graph nodes.

    All input slots are optional — the routing layer skips nodes whose
    corresponding input is absent, so a single state object can drive
    pure-create, pure-query, query+SLA, or query+update flows.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input: create
    task_input: Optional[CreateTaskInput] = None

    # Input: query (filters live on task_input/query_filter; query node also
    # has its own filter slot for callers that only want to query)
    query_filter: Optional[object] = None  # QueryTasksFilter (loose typing to
    # avoid circular import at module load).

    # Input: update
    update_input: Optional[UpdateTaskStatusInput] = None

    # Outputs populated by nodes
    created_task: Optional[TaskRow] = None
    queried_tasks: list[TaskRow] = Field(default_factory=list)
    sla_results: list[SlaCheckResult] = Field(default_factory=list)
    updated_task: Optional[TaskRow] = None

    # Flow observability
    turn_count: int = 0
    error: Optional[str] = None
