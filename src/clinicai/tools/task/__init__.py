"""Task-domain tools (P9.3: real impl backed by `staff_task` table).

Modules:
- create_task — INSERT one row.
- query_tasks — filtered SELECT.
- update_task_status — UPDATE status + auto-set completed_at.
- check_sla — compute is_overdue / hours_remaining / hours_overdue.
"""

from clinicai.tools.task.check_sla import (
    SlaCheckResult,
    check_task_sla,
)
from clinicai.tools.task.check_sla import (
    TaskNotFoundError as SlaTaskNotFoundError,
)
from clinicai.tools.task.create_task import (
    CreateTaskInput,
    TaskPriority,
    TaskRow,
    TaskStatus,
    create_task,
)
from clinicai.tools.task.query_tasks import OrderBy, QueryTasksFilter, query_tasks
from clinicai.tools.task.update_task_status import (
    TaskNotFoundError,
    TaskStatusUpdate,
    UpdateTaskStatusInput,
    update_task_status,
)

__all__ = [
    "CreateTaskInput",
    "OrderBy",
    "QueryTasksFilter",
    "SlaCheckResult",
    "SlaTaskNotFoundError",
    "TaskNotFoundError",
    "TaskPriority",
    "TaskRow",
    "TaskStatus",
    "TaskStatusUpdate",
    "UpdateTaskStatusInput",
    "check_task_sla",
    "create_task",
    "query_tasks",
    "update_task_status",
]


def _register() -> None:
    """Self-register task tools into the global REGISTRY."""
    from clinicai.tools.registry import REGISTRY, ToolMeta

    REGISTRY.register(
        ToolMeta(
            name="task.check_task_sla",
            toolset="task",
            fn=check_task_sla,
            input_schema=None,  # takes a raw task_id: UUID, no input model
            output_schema=SlaCheckResult,
            description="Kiểm tra SLA của một công việc (quá hạn / thời gian còn lại).",
        )
    )
    REGISTRY.register(
        ToolMeta(
            name="task.create_task",
            toolset="task",
            fn=create_task,
            input_schema=CreateTaskInput,
            output_schema=TaskRow,
            description="Tạo một công việc nhân sự (staff_task).",
        )
    )
    REGISTRY.register(
        ToolMeta(
            name="task.query_tasks",
            toolset="task",
            fn=query_tasks,
            input_schema=QueryTasksFilter,
            output_schema=TaskRow,  # returns list[TaskRow]
            description="Truy vấn danh sách công việc theo bộ lọc.",
        )
    )
    REGISTRY.register(
        ToolMeta(
            name="task.update_task_status",
            toolset="task",
            fn=update_task_status,
            input_schema=UpdateTaskStatusInput,
            output_schema=TaskRow,
            description="Cập nhật trạng thái công việc; tự set completed_at khi DONE.",
        )
    )


_register()
