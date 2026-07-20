"""Unit tests for BaseAdapter and WalkinAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clinicai.event_bus.adapters.base import WalkinAdapter
from clinicai.event_bus.publisher import MockEventPublisher
from clinicai.schemas.events import InteractionEvent


@pytest.fixture
def mock_publisher() -> MockEventPublisher:
    """Fixture that returns a MockEventPublisher."""
    return MockEventPublisher()


@pytest.fixture
def mock_event_service() -> MagicMock:
    """Fixture that returns a mocked EventService."""
    svc = MagicMock()
    svc.record_and_publish = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_walkin_adapter__normalize__returns_correct_fields(
    mock_publisher: MockEventPublisher,
    mock_event_service: MagicMock,
) -> None:
    """Verify that normalize transforms raw input into an InteractionEvent."""
    adapter = WalkinAdapter(mock_publisher, mock_event_service)
    entity_id = uuid4()
    trace_id = uuid4()
    raw = {
        "entity_type": "appointment",
        "entity_id": str(entity_id),
        "trace_id": str(trace_id),
        "data": "some_payload",
    }

    event = await adapter.normalize(raw)

    assert event.event_type == "interaction.walkin"
    assert event.entity_type == "appointment"
    assert event.entity_id == entity_id
    assert event.trace_id == trace_id
    assert event.source_channel == "walkin"
    assert event.payload == raw


@pytest.mark.asyncio
async def test_walkin_adapter__normalize_missing_trace_id__generates_uuid(
    mock_publisher: MockEventPublisher,
    mock_event_service: MagicMock,
) -> None:
    """Verify that a trace_id is generated when it is missing from the raw payload."""
    adapter = WalkinAdapter(mock_publisher, mock_event_service)
    entity_id = uuid4()
    raw = {
        "entity_type": "appointment",
        "entity_id": str(entity_id),
        "data": "some_payload",
    }

    event = await adapter.normalize(raw)

    assert event.trace_id is not None
    assert isinstance(event.trace_id, UUID)


@pytest.mark.asyncio
async def test_base_adapter__emit__calls_record_and_publish(
    mock_publisher: MockEventPublisher,
    mock_event_service: MagicMock,
) -> None:
    """Verify that emit calls record_and_publish with the correct topic."""
    adapter = WalkinAdapter(mock_publisher, mock_event_service)
    entity_id = uuid4()
    raw = {
        "entity_id": str(entity_id),
        "data": "val",
    }

    event = await adapter.emit(raw)

    mock_event_service.record_and_publish.assert_awaited_once_with(
        event, "interaction.walkin"
    )


@pytest.mark.asyncio
async def test_base_adapter__emit__returns_normalized_event(
    mock_publisher: MockEventPublisher,
    mock_event_service: MagicMock,
) -> None:
    """Verify that emit returns the normalized InteractionEvent object."""
    adapter = WalkinAdapter(mock_publisher, mock_event_service)
    entity_id = uuid4()
    raw = {
        "entity_id": str(entity_id),
        "data": "val",
    }

    event = await adapter.emit(raw)

    assert isinstance(event, InteractionEvent)
    assert event.entity_id == entity_id
