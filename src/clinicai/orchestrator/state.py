from typing import Any, Literal, NotRequired, Optional, TypedDict
from uuid import UUID

RouteType = Literal[
    "scheduling",
    "lab",
    "communication",
    "task",
    "previsit",
    "general",
    "unknown",
]


class OrchestratorState(TypedDict, total=False):
    """Shared state across orchestrator + sub-graph nodes.

    Scheduling-specific fields are declared here (NotRequired) so the parent
    state can share keys with SchedulingState when the compiled scheduling
    sub-graph is added as a node. Without these fields LangGraph filters them
    out at the sub-graph boundary and the slot-filling conversation loses
    context across turns.
    """

    trace_id: UUID
    user_message: str
    patient_id: Optional[UUID]
    route: RouteType
    response: str
    error: Optional[str]
    handled_by: NotRequired[str | None]
    # ----- scheduling sub-graph fields (mirror SchedulingState) -----
    step: NotRequired[str]
    turn_count: NotRequired[int]
    preferred_date: NotRequired[str | None]
    preferred_time: NotRequired[str | None]
    preferred_doctor: NotRequired[str | None]
    candidate_doctors: NotRequired[list[dict[str, Any]]]
    confirmed: NotRequired[bool]
    # ----- lab_triage sub-graph hand-off fields -----
    # Set by upstream caller (worker / event handler) when a specific lab
    # result needs triaging. When absent the lab branch returns a generic
    # acknowledgement instead of invoking the real sub-graph.
    lab_result_id: NotRequired[UUID | None]
    triage_group: NotRequired[str | None]
    requires_doctor_review: NotRequired[bool]
    escalation_note: NotRequired[str | None]
    # ----- event-driven routing fields -----
    event_type: NotRequired[str | None]
    # Upstream caller set khi dispatch từ RabbitMQ event
    # (vd: "lab_result_received", "appointment_created")
    # Orchestrator dùng để ưu tiên route trước classify_intent.

    work_session_id: NotRequired[UUID | None]
    # Ca trực hiện tại — dùng để scope task assignment
    # và pre-visit brief cho đúng session.
