"""Event Service for managing and persisting outbox events."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

if TYPE_CHECKING:
    import asyncpg

    from clinicai.event_bus.publisher import IEventPublisher
    from clinicai.schemas.events import InteractionEvent

logger = structlog.get_logger()


class EventService:
    """Service to record events in the outbox table and publish them to MQ."""

    def __init__(self, pool: asyncpg.Pool, publisher: IEventPublisher) -> None:
        self.pool = pool
        self.publisher = publisher

    async def record_and_publish(
        self,
        event: InteractionEvent,
        topic: str,
    ) -> UUID:
        """Record event to event_log, publish it, and mark it as published.

        Outbox pattern:
        1. INSERT event_log (event_published=FALSE) in transaction
        2. COMMIT
        3. publish() via publisher (outside transaction)
        4. UPDATE event_published=TRUE (outside transaction)
        Returns: event_id
        """
        # Step 1+2: INSERT + COMMIT
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # We map entity_type -> aggregate_type and entity_id -> aggregate_id
                # trace_id is stored inside metadata JSONB.
                event_id = await conn.fetchval(
                    """
                    INSERT INTO event_log
                      (event_type, aggregate_type, aggregate_id, payload,
                       metadata, source, event_published)
                    VALUES ($1, $2, $3, $4, $5, $6, FALSE)
                    RETURNING event_id
                    """,
                    event.event_type,
                    event.entity_type,
                    event.entity_id,
                    json.dumps(event.payload),
                    json.dumps({"trace_id": str(event.trace_id)}),
                    event.source_channel,
                )

        # Step 3: publish (outside transaction — fire and forget MVP)
        try:
            await self.publisher.publish(topic, event)
            # Step 4: mark published
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE event_log SET event_published = TRUE WHERE event_id = $1",
                    event_id,
                )
        except NotImplementedError:
            # RabbitMQ stub — acceptable in dev, log warning
            logger.warning(
                "event_publish_skipped",
                event_id=str(event_id),
                reason="publisher_not_implemented",
                trace_id=str(event.trace_id),
            )
        except Exception as e:
            logger.error(
                "event_publish_failed",
                event_id=str(event_id),
                error=str(e),
                trace_id=str(event.trace_id),
            )
            # DO NOT raise — event is safe in DB and can be retried later
        return event_id

    async def get_unpublished(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get events that have not been published yet — for future relay worker."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT event_id, event_type, aggregate_id, payload,
                       metadata, source, occurred_at
                FROM event_log
                WHERE event_published = FALSE
                ORDER BY occurred_at ASC
                LIMIT $1
                """,
                limit,
            )

        results = []
        for r in rows:
            payload = r["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)

            metadata = r["metadata"]
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            elif metadata is None:
                metadata = {}

            trace_id_str = metadata.get("trace_id")
            trace_id = UUID(trace_id_str) if trace_id_str else None

            results.append(
                {
                    "event_id": r["event_id"],
                    "event_type": r["event_type"],
                    "entity_id": r["aggregate_id"],
                    "payload": payload,
                    "trace_id": trace_id,
                    "source_channel": r["source"],
                    "occurred_at": r["occurred_at"],
                }
            )
        return results
