"""GoldenRecordEngine — process InteractionEvents into canonical patient state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

if TYPE_CHECKING:
    import asyncpg

    from clinicai.schemas.events import InteractionEvent
    from clinicai.services.event_service import EventService

logger = structlog.get_logger()

GOLDEN_RECORD_PROCESSED_TOPIC = "golden_record.processed"


class GoldenRecordEngine:
    """Apply InteractionEvent to the golden patient record.

    MVP flow:
      1. resolve identity (stub — Phase 5 wires MPI)
      2. write to domain tables (stub)
      3. record + publish a downstream "golden_record.processed" event

    The engine is intentionally thin: it owns orchestration, not business
    logic. Real resolution + domain writes land in later phases.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        event_service: EventService,
    ) -> None:
        self.pool = pool
        self.event_service = event_service

    async def process(self, event: InteractionEvent) -> dict[str, Any]:
        """Process a single InteractionEvent.

        Returns:
            {"status": "queued"} if identity could not be resolved
            {"status": "processed", "patient_id": "<uuid>"} on success
        """
        logger.info(
            "golden_record_received",
            event_id=str(event.event_id),
            event_type=event.event_type,
            trace_id=str(event.trace_id),
        )

        patient_id = await self._resolve_identity(event)
        if patient_id is None:
            logger.info(
                "identity_unresolved",
                event_id=str(event.event_id),
                trace_id=str(event.trace_id),
            )
            return {"status": "queued"}

        await self._write_domain(patient_id, event)

        await self.event_service.record_and_publish(
            event, GOLDEN_RECORD_PROCESSED_TOPIC
        )

        logger.info(
            "golden_record_processed",
            event_id=str(event.event_id),
            patient_id=str(patient_id),
            trace_id=str(event.trace_id),
        )
        return {"status": "processed", "patient_id": str(patient_id)}

    async def _resolve_identity(self, event: InteractionEvent) -> UUID | None:
        """STUB — always returns None until MPI integration lands (Phase 5)."""
        logger.info(
            "identity_resolution_stub",
            event_id=str(event.event_id),
            trace_id=str(event.trace_id),
        )
        return None

    async def _write_domain(self, patient_id: UUID, event: InteractionEvent) -> None:
        """STUB — domain table writes wired in Phase 5."""
        logger.info(
            "domain_write_stub",
            patient_id=str(patient_id),
            event_id=str(event.event_id),
            trace_id=str(event.trace_id),
        )
