"""Unit tests for the event_log.append tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clinicai.event_bus.publisher import MockEventPublisher, RabbitMQPublisher
from clinicai.tools._common.context import new_trace
from clinicai.tools.event_log.append import (
    EVENT_LOG_TOPIC,
    AppendEventInput,
    AppendEventOutput,
    append_event,
)


@pytest.fixture
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Mocked asyncpg Pool + Connection (with transaction support)."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.transaction = MagicMock()
    transaction_ctx = AsyncMock()
    conn.transaction.return_value = transaction_ctx

    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx

    async def _return_inserted_event_id(
        _sql: str,
        event_id: UUID,
        *_args: object,
    ) -> UUID:
        return event_id

    conn.fetchval.side_effect = _return_inserted_event_id
    return pool, conn


def _input() -> AppendEventInput:
    return AppendEventInput(
        clinic_id=uuid4(),
        event_type="interaction.walkin",
        entity_type="appointment",
        entity_id=uuid4(),
        payload={"status": "scheduled"},
        ctx=new_trace(source_channel="walkin"),
    )


@pytest.mark.asyncio
async def test_append_event_happy_path(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """MockPublisher path: returns AppendEventOutput with a UUID event_id."""
    pool, conn = mock_pool

    publisher = MockEventPublisher()
    inp = _input()
    out = await append_event(inp, pool, publisher)

    assert isinstance(out, AppendEventOutput)
    assert isinstance(out.event_id, UUID)
    # Publisher saw exactly one event with our topic
    assert publisher.count() == 1
    topic, event = publisher.last()
    assert topic == EVENT_LOG_TOPIC
    assert event.clinic_id == inp.clinic_id
    assert event.entity_id == inp.entity_id
    assert event.source_channel == "walkin"


@pytest.mark.asyncio
async def test_append_event_carries_trace_id(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """Output trace_id must equal input ctx trace_id (propagation guarantee)."""
    pool, conn = mock_pool

    inp = _input()
    out = await append_event(inp, pool, MockEventPublisher())

    assert out.trace_id == inp.ctx.trace_id


@pytest.mark.asyncio
async def test_append_event_publisher_fail_no_crash(
    mock_pool: tuple[MagicMock, AsyncMock],
) -> None:
    """RabbitMQPublisher raises NotImplementedError — tool must NOT propagate."""
    pool, conn = mock_pool

    inp = _input()
    out = await append_event(inp, pool, RabbitMQPublisher())

    # No exception bubbled out; row still recorded (event_published=FALSE)
    assert out.event_id == conn.fetchval.await_args.args[1]
    # event_published UPDATE should NOT have been called when publish failed
    conn.execute.assert_not_awaited()
