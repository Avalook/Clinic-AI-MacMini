from typing import Any, Literal, NotRequired, TypedDict
from uuid import UUID

SchedulingStep = Literal["ask_date", "ask_time", "find_doctor", "confirm", "done"]
SchedulingIntent = Literal["new", "modify", "cancel", "unknown"]


class SchedulingState(TypedDict, total=False):
    user_message: str
    # Tenant of the conversation, inherited from OrchestratorState. It belongs
    # in the state and not in the graph's construction: one process serves
    # every clinic, so binding a clinic when the graph is built would make the
    # rota lookup answer for whichever clinic happened to start the process.
    clinic_id: UUID
    turn_count: int
    step: SchedulingStep
    intent: NotRequired[SchedulingIntent | None]
    preferred_date: NotRequired[str | None]
    preferred_time: NotRequired[str | None]
    preferred_doctor: NotRequired[str | None]
    candidate_doctors: NotRequired[list[dict[str, Any]]]
    confirmed: NotRequired[bool]
    response: str
    handled_by: NotRequired[str | None]
