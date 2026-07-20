from typing import Any, Literal, NotRequired, TypedDict

SchedulingStep = Literal["ask_date", "ask_time", "find_doctor", "confirm", "done"]
SchedulingIntent = Literal["new", "modify", "cancel", "unknown"]


class SchedulingState(TypedDict, total=False):
    user_message: str
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
