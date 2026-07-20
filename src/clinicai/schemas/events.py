"""Pydantic schemas for Event Bus and outbox events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class InteractionEvent(BaseModel):
    """Event model representing an interaction inside the clinic system."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str  # e.g., "interaction.walkin", "zalo.message", "lab.result"
    entity_type: str  # e.g., "patient", "appointment"
    entity_id: UUID
    payload: dict[str, Any]  # Raw normalized data
    trace_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_channel: str  # e.g., "zalo", "pancake", "walkin", "system"
