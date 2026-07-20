"""Unit tests for EventService with mock asyncpg pool and MockPublisher."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from clinicai.event_bus.publisher import MockEventPublisher, RabbitMQPublisher
from clinicai.schemas.events import InteractionEvent
from clinicai.services.event_service import EventService


@pytest.fixture
def mock_db() -> tuple[MagicMock, AsyncMock]:
    """Fixture that returns a mocked asyncpg Pool and Connection."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.transaction = MagicMock()

    # Configure pool.acquire() to return the connection async context manager
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx

    # Configure conn.transaction() to return an async context manager
    transaction_ctx = AsyncMock()
    conn.transaction.return_value = transaction_ctx

    return pool, conn


@pytest.fixture
def mock_publisher() -> MockEventPublisher:
    """Fixture that returns a MockEventPublisher."""
    return MockEventPublisher()


@pytest.fixture
def sample_event() -> InteractionEvent:
    """Fixture that returns a sample InteractionEvent."""
    return InteractionEvent(
        event_type="interaction.walkin",
        entity_type="appointment",
        entity_id=uuid4(),
        payload={"status": "scheduled"},
        trace_id=uuid4(),
        source_channel="walkin",
    )


@pytest.mark.asyncio
async def test_event_service__record_and_publish__inserts_event_log(
    mock_db: tuple[MagicMock, AsyncMock],
    mock_publisher: MockEventPublisher,
    sample_event: InteractionEvent,
) -> None:
    """Verify record_and_publish inserts the event into the database."""
    pool, conn = mock_db
    fake_id = uuid4()
    conn.fetchval.return_value = fake_id

    svc = EventService(pool, mock_publisher)
    await svc.record_and_publish(sample_event, "interaction.walkin")

    conn.fetchval.assert_awaited_once()
    sql_arg = conn.fetchval.call_args[0][0]
    assert "INSERT INTO event_log" in sql_arg

    # Verify query parameters
    args = conn.fetchval.call_args[0][1:]
    assert args[0] == sample_event.event_type
    assert args[1] == sample_event.entity_type
    assert args[2] == sample_event.entity_id
    assert json.loads(args[3]) == sample_event.payload
    assert json.loads(args[4]) == {"trace_id": str(sample_event.trace_id)}
    assert args[5] == sample_event.source_channel


@pytest.mark.asyncio
async def test_event_service__record_and_publish__returns_event_id(
    mock_db: tuple[MagicMock, AsyncMock],
    mock_publisher: MockEventPublisher,
    sample_event: InteractionEvent,
) -> None:
    """Verify that record_and_publish returns the inserted UUID."""
    pool, conn = mock_db
    fake_id = uuid4()
    conn.fetchval.return_value = fake_id

    svc = EventService(pool, mock_publisher)
    event_id = await svc.record_and_publish(sample_event, "interaction.walkin")

    assert event_id == fake_id
    assert isinstance(event_id, UUID)


@pytest.mark.asyncio
async def test_event_service__record_and_publish__publishes_correct_topic(
    mock_db: tuple[MagicMock, AsyncMock],
    mock_publisher: MockEventPublisher,
    sample_event: InteractionEvent,
) -> None:
    """Verify that the publisher is called with the correct topic and event."""
    pool, conn = mock_db
    fake_id = uuid4()
    conn.fetchval.return_value = fake_id

    svc = EventService(pool, mock_publisher)
    await svc.record_and_publish(sample_event, "interaction.walkin")

    assert mock_publisher.count() == 1
    topic, published_event = mock_publisher.last()
    assert topic == "interaction.walkin"
    assert published_event.event_id == sample_event.event_id


@pytest.mark.asyncio
async def test_event_service__record_and_publish__marks_published_on_success(
    mock_db: tuple[MagicMock, AsyncMock],
    mock_publisher: MockEventPublisher,
    sample_event: InteractionEvent,
) -> None:
    """Verify that event_published is updated to TRUE after successful publish."""
    pool, conn = mock_db
    fake_id = uuid4()
    conn.fetchval.return_value = fake_id

    svc = EventService(pool, mock_publisher)
    await svc.record_and_publish(sample_event, "interaction.walkin")

    conn.execute.assert_awaited_once_with(
        "UPDATE event_log SET event_published = TRUE WHERE event_id = $1",
        fake_id,
    )


@pytest.mark.asyncio
async def test_event_service__record_and_publish_not_implemented__no_exception(
    mock_db: tuple[MagicMock, AsyncMock],
    sample_event: InteractionEvent,
) -> None:
    """Verify that NotImplementedError (RabbitMQ stub) does not crash the service."""
    pool, conn = mock_db
    fake_id = uuid4()
    conn.fetchval.return_value = fake_id

    stub_publisher = RabbitMQPublisher()
    svc = EventService(pool, stub_publisher)

    # Should not raise exception
    event_id = await svc.record_and_publish(sample_event, "interaction.walkin")
    assert event_id == fake_id

    # Update should not be called since publishing raised NotImplementedError
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_service__record_and_publish_failure__no_exception(
    mock_db: tuple[MagicMock, AsyncMock],
    sample_event: InteractionEvent,
) -> None:
    """Verify a publisher exception does not propagate and crash the service."""
    pool, conn = mock_db
    fake_id = uuid4()
    conn.fetchval.return_value = fake_id

    bad_publisher = MagicMock()
    bad_publisher.publish = AsyncMock(side_effect=RuntimeError("Broker down"))

    svc = EventService(pool, bad_publisher)

    # Should not raise exception
    event_id = await svc.record_and_publish(sample_event, "interaction.walkin")
    assert event_id == fake_id

    # Update should not be called
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_service__get_unpublished__returns_pending_events(
    mock_db: tuple[MagicMock, AsyncMock],
    mock_publisher: MockEventPublisher,
) -> None:
    """Verify get_unpublished queries the database and formats results correctly."""
    pool, conn = mock_db
    fake_time = datetime.now(timezone.utc)
    mock_rows = [
        {
            "event_id": uuid4(),
            "event_type": "interaction.walkin",
            "aggregate_id": uuid4(),
            "payload": '{"status": "scheduled"}',
            "metadata": json.dumps({"trace_id": str(uuid4())}),
            "source": "walkin",
            "occurred_at": fake_time,
        },
        {
            "event_id": uuid4(),
            "event_type": "interaction.walkin",
            "aggregate_id": uuid4(),
            "payload": {"status": "checked_in"},
            "metadata": {"trace_id": str(uuid4())},
            "source": "walkin",
            "occurred_at": fake_time,
        },
    ]
    conn.fetch.return_value = mock_rows

    svc = EventService(pool, mock_publisher)
    results = await svc.get_unpublished(limit=10)

    assert len(results) == 2
    assert results[0]["event_type"] == "interaction.walkin"
    assert results[0]["payload"] == {"status": "scheduled"}
    assert isinstance(results[0]["trace_id"], UUID)
    assert results[1]["payload"] == {"status": "checked_in"}
    assert isinstance(results[1]["trace_id"], UUID)


def test_event_service__interaction_event_validation__raises_validation_error() -> None:
    """Verify that schema validation fails when required fields are missing."""
    with pytest.raises(ValidationError):
        # Missing entity_id
        InteractionEvent(
            event_type="interaction.walkin",
            entity_type="appointment",
            payload={"status": "scheduled"},
            trace_id=uuid4(),
            source_channel="walkin",
        )
