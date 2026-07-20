"""Scheduling-domain tools.

Each tool lives in its own submodule with the same name as the function
(e.g. find_work_sessions.find_work_sessions). To avoid shadowing the submodule
on the package namespace, we DO NOT re-export the function symbols at the
package level — import them from the submodule directly:

    from clinicai.tools.scheduling.find_work_sessions import find_work_sessions

The Pydantic input/output schemas are re-exported here for ergonomic typing
because there's no naming collision with submodules.
"""

from clinicai.tools.scheduling.cancel_appointment import (
    CancelAppointmentInput,
    CancelAppointmentOutput,
)
from clinicai.tools.scheduling.confirm_appointment import (
    ConfirmAppointmentInput,
    ConfirmAppointmentOutput,
)
from clinicai.tools.scheduling.create_appointment import (
    AppointmentConflictError,
    CreateAppointmentInput,
    CreateAppointmentOutput,
)
from clinicai.tools.scheduling.find_oncall import (
    FindOncallInput,
    OncallStaffOutput,
)
from clinicai.tools.scheduling.find_work_sessions import (
    FindWorkSessionsInput,
    FindWorkSessionsOutput,
    WorkSessionResult,
)

__all__ = [
    "AppointmentConflictError",
    "CancelAppointmentInput",
    "CancelAppointmentOutput",
    "ConfirmAppointmentInput",
    "ConfirmAppointmentOutput",
    "CreateAppointmentInput",
    "CreateAppointmentOutput",
    "FindOncallInput",
    "FindWorkSessionsInput",
    "FindWorkSessionsOutput",
    "OncallStaffOutput",
    "WorkSessionResult",
]


def _register() -> None:
    """Self-register scheduling tools into the global REGISTRY.

    Functions are imported locally so they are NOT bound on the package
    namespace (which would shadow the same-named submodules).
    """
    from clinicai.tools.registry import REGISTRY, ToolMeta
    from clinicai.tools.scheduling.cancel_appointment import cancel_appointment
    from clinicai.tools.scheduling.confirm_appointment import confirm_appointment
    from clinicai.tools.scheduling.create_appointment import create_appointment
    from clinicai.tools.scheduling.find_oncall import find_oncall_staff
    from clinicai.tools.scheduling.find_work_sessions import find_work_sessions

    REGISTRY.register(
        ToolMeta(
            name="scheduling.create_appointment",
            toolset="scheduling",
            fn=create_appointment,
            input_schema=CreateAppointmentInput,
            output_schema=CreateAppointmentOutput,
            description="Đặt lịch hẹn mới cho bệnh nhân; chặn trùng khung giờ bác sĩ.",
        )
    )
    REGISTRY.register(
        ToolMeta(
            name="scheduling.cancel_appointment",
            toolset="scheduling",
            fn=cancel_appointment,
            input_schema=CancelAppointmentInput,
            output_schema=CancelAppointmentOutput,
            description="Huỷ một lịch hẹn theo appointment_id.",
        )
    )
    REGISTRY.register(
        ToolMeta(
            name="scheduling.confirm_appointment",
            toolset="scheduling",
            fn=confirm_appointment,
            input_schema=ConfirmAppointmentInput,
            output_schema=ConfirmAppointmentOutput,
            description="Xác nhận một lịch hẹn (SCHEDULED → CONFIRMED).",
        )
    )
    REGISTRY.register(
        ToolMeta(
            name="scheduling.find_oncall_staff",
            toolset="scheduling",
            fn=find_oncall_staff,
            input_schema=FindOncallInput,
            output_schema=OncallStaffOutput,
            description="Tìm bác sĩ/nhân sự đang trực theo thời điểm và địa điểm.",
        )
    )
    REGISTRY.register(
        ToolMeta(
            name="scheduling.find_work_sessions",
            toolset="scheduling",
            fn=find_work_sessions,
            input_schema=FindWorkSessionsInput,
            output_schema=FindWorkSessionsOutput,
            description="Tìm ca làm khả dụng theo bộ lọc (ngày, location, dịch vụ).",
        )
    )


_register()
