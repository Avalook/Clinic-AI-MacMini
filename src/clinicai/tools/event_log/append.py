"""Tool: event_log.append — thin wrapper around EventService.record_and_publish."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from pydantic import BaseModel

from clinicai.schemas.events import InteractionEvent
from clinicai.services.event_service import EventService
from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    import asyncpg

    from clinicai.event_bus.publisher import IEventPublisher

logger = structlog.get_logger()

EVENT_LOG_TOPIC = "system.event_log"


class AppendEventInput(BaseModel):
    """Input schema for the event_log.append tool."""

    event_type: str
    entity_type: str
    entity_id: UUID
    payload: dict[str, Any]
    ctx: TraceContext


class AppendEventOutput(BaseModel):
    """Returns the event_id written to event_log."""

    event_id: UUID
    trace_id: UUID


async def append_event(
    input: AppendEventInput,
    pool: asyncpg.Pool,
    publisher: IEventPublisher,
) -> AppendEventOutput:
    """Build an InteractionEvent and persist via EventService."""
    logger.info(
        "tool.event_log.append",
        event_type=input.event_type,
        entity_id=str(input.entity_id),
        trace_id=str(input.ctx.trace_id),
    )

    event = InteractionEvent(
        event_type=input.event_type,
        entity_type=input.entity_type,
        entity_id=input.entity_id,
        payload=input.payload,
        trace_id=input.ctx.trace_id,
        source_channel=input.ctx.source_channel,
    )

    service = EventService(pool, publisher)
    event_id = await service.record_and_publish(event, EVENT_LOG_TOPIC)

    return AppendEventOutput(
        event_id=event_id,
        trace_id=input.ctx.trace_id,
    )
