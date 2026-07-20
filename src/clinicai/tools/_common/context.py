"""TraceContext — carries trace_id + actor info across tool invocations."""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

ActorType = Literal["staff", "system", "patient"]


class TraceContext(BaseModel):
    """Per-invocation context propagated through every tool call.

    `trace_id` ties together log lines, event_log rows, and downstream events
    so an investigator can reconstruct an end-to-end flow.
    """

    trace_id: UUID
    actor_id: UUID | None = None
    actor_type: ActorType = "system"
    source_channel: str = "system"
    session_id: UUID | None = None


def new_trace(
    *,
    actor_id: UUID | None = None,
    actor_type: ActorType = "system",
    source_channel: str = "system",
    session_id: UUID | None = None,
) -> TraceContext:
    """Create a fresh TraceContext with a random trace_id."""
    return TraceContext(
        trace_id=uuid4(),
        actor_id=actor_id,
        actor_type=actor_type,
        source_channel=source_channel,
        session_id=session_id,
    )


__all__ = ["ActorType", "TraceContext", "new_trace", "Field"]
