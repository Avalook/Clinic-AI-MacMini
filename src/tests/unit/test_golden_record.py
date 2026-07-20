"""Unit tests for GoldenRecordEngine using MockEventPublisher + mocked asyncpg."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from clinicai.event_bus.publisher import MockEventPublisher
from clinicai.golden_record.engine import (
    GOLDEN_RECORD_PROCESSED_TOPIC,
    GoldenRecordEngine,
)
from clinicai.schemas.events import InteractionEvent
from clinicai.services.event_service import EventService


@pytest.fixture
def mock_pool() -> MagicMock:
    """Mocked asyncpg Pool — engine itself does not query in MVP."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.transaction = MagicMock()
    transaction_ctx = AsyncMock()
    conn.transaction.return_value = transaction_ctx

    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool


@pytest.fixture
def sample_event() -> InteractionEvent:
    """Sample InteractionEvent fixture."""
    return InteractionEvent(
        event_type="interaction.walkin",
        entity_type="appointment",
        entity_id=uuid4(),
        payload={"status": "scheduled"},
        trace_id=uuid4(),
        source_channel="walkin",
    )


@pytest.mark.asyncio
async def test_process_unresolved_returns_queued(
    mock_pool: MagicMock, sample_event: InteractionEvent
) -> None:
    """When _resolve_identity returns None, engine should return queued."""
    publisher = MockEventPublisher()
    event_service = EventService(mock_pool, publisher)
    engine = GoldenRecordEngine(mock_pool, event_service)

    result = await engine.process(sample_event)

    assert result == {"status": "queued"}
    # No downstream event should have been published
    assert publisher.count() == 0


@pytest.mark.asyncio
async def test_process_logs_trace_id(
    mock_pool: MagicMock, sample_event: InteractionEvent
) -> None:
    """Engine must include the event's trace_id in its log entries."""
    publisher = MockEventPublisher()
    event_service = EventService(mock_pool, publisher)
    engine = GoldenRecordEngine(mock_pool, event_service)

    with capture_logs() as logs:
        await engine.process(sample_event)

    trace_ids = {log.get("trace_id") for log in logs}
    assert str(sample_event.trace_id) in trace_ids


@pytest.mark.asyncio
async def test_process_resolved_returns_processed(
    mock_pool: MagicMock, sample_event: InteractionEvent
) -> None:
    """When identity resolves to a UUID, engine should return processed."""
    publisher = MockEventPublisher()
    event_service = EventService(mock_pool, publisher)
    # event_service.record_and_publish will INSERT via fetchval — give it a UUID
    conn = mock_pool.acquire.return_value.__aenter__.return_value
    conn.fetchval.return_value = uuid4()

    engine = GoldenRecordEngine(mock_pool, event_service)
    resolved_id = uuid4()

    with patch.object(engine, "_resolve_identity", AsyncMock(return_value=resolved_id)):
        result = await engine.process(sample_event)

    assert result == {"status": "processed", "patient_id": str(resolved_id)}


@pytest.mark.asyncio
async def test_process_calls_event_service(
    mock_pool: MagicMock, sample_event: InteractionEvent
) -> None:
    """When identity resolves, record_and_publish should be invoked exactly once."""
    publisher = MockEventPublisher()
    event_service = EventService(mock_pool, publisher)
    record_spy = AsyncMock(return_value=uuid4())
    event_service.record_and_publish = record_spy  # type: ignore[method-assign]

    engine = GoldenRecordEngine(mock_pool, event_service)

    with patch.object(engine, "_resolve_identity", AsyncMock(return_value=uuid4())):
        await engine.process(sample_event)

    record_spy.assert_awaited_once_with(sample_event, GOLDEN_RECORD_PROCESSED_TOPIC)
