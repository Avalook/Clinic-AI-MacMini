"""Base Adapter for normalizing, persisting, and emitting interaction events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from clinicai.schemas.events import InteractionEvent

if TYPE_CHECKING:
    from clinicai.event_bus.publisher import IEventPublisher
    from clinicai.services.event_service import EventService


class BaseAdapter(ABC):
    """Abstract base adapter for ingestion channels."""

    def __init__(self, publisher: IEventPublisher, event_service: EventService) -> None:
        self.publisher = publisher
        self.event_service = event_service

    @abstractmethod
    async def normalize(self, raw: dict[str, Any]) -> InteractionEvent:
        """Normalize channel-specific payload into a standard InteractionEvent."""

    async def emit(self, raw: dict[str, Any]) -> InteractionEvent:
        """Normalize the raw payload, save to database outbox, and publish to queue."""
        event = await self.normalize(raw)
        topic = self._get_topic(event)
        await self.event_service.record_and_publish(event, topic)
        return event

    def _get_topic(self, event: InteractionEvent) -> str:
        """Map event_type → topic constant."""
        from clinicai.event_bus import topics

        event_type = event.event_type

        # Attempt to map to topic constants, fallback to event_type itself
        for attr in dir(topics):
            if not attr.startswith("_"):
                val = getattr(topics, attr)
                if val == event_type:
                    return val
        return event_type


class WalkinAdapter(BaseAdapter):
    """Placeholder adapter for Walk-in channel events."""

    async def normalize(self, raw: dict[str, Any]) -> InteractionEvent:
        """Normalize walk-in dictionary payload into InteractionEvent."""
        entity_id_raw = raw.get("entity_id")
        if entity_id_raw is None:
            msg = "Missing required entity_id"
            raise ValueError(msg)

        trace_id_raw = raw.get("trace_id")
        trace_id = UUID(trace_id_raw) if trace_id_raw else uuid4()

        return InteractionEvent(
            event_type="interaction.walkin",
            entity_type=raw.get("entity_type", "appointment"),
            entity_id=UUID(str(entity_id_raw)),
            payload=raw,
            trace_id=trace_id,
            source_channel="walkin",
        )
