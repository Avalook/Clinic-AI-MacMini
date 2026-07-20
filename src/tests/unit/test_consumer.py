"""Unit tests for MockConsumer (and surface tests for RabbitMQConsumer wiring)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from clinicai.event_bus.consumer import MockConsumer
from clinicai.schemas.events import InteractionEvent


def _make_event() -> InteractionEvent:
    return InteractionEvent(
        event_type="interaction.walkin",
        entity_type="appointment",
        entity_id=uuid4(),
        payload={"status": "scheduled"},
        trace_id=uuid4(),
        source_channel="walkin",
    )


@pytest.mark.asyncio
async def test_mock_consumer_calls_handler_for_each_event() -> None:
    """MockConsumer.start should dispatch every queued event to handler."""
    events = [_make_event(), _make_event()]
    handler = AsyncMock()

    consumer = MockConsumer(events, handler)
    await consumer.start()

    assert handler.await_count == 2
    awaited_args = [call.args[0] for call in handler.await_args_list]
    assert awaited_args == events
    assert consumer.started is True


@pytest.mark.asyncio
async def test_mock_consumer_stop_is_noop() -> None:
    """MockConsumer.stop should flip the flag and not raise."""
    consumer = MockConsumer([], AsyncMock())

    await consumer.stop()

    assert consumer.stopped is True
