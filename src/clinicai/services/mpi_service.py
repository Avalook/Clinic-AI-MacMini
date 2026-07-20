"""MPI (Master Patient Index) deduplication engine.

Scores candidate patients against each other using weighted matching
and auto-queues high-confidence duplicates for human review.
"""

from __future__ import annotations

import difflib
from uuid import UUID

import asyncpg
import structlog

from clinicai.schemas.patient import PatientCreateDTO, PatientDTO

logger = structlog.get_logger()

# TODO: move to config / env var
MPI_THRESHOLD = 70.0

# Scoring weights
_PHONE_WEIGHT = 50.0
_NATIONAL_ID_WEIGHT = 40.0
_NAME_WEIGHT = 10.0


class MPIService:
    """Master Patient Index deduplication scoring and queue management."""

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def score(candidate: PatientDTO, existing: PatientDTO) -> float:
        """Return a similarity score (0.0–100.0) between two patients.

        Weighted components:
          - phone_primary exact match:          50 pts
          - national_id_number exact (non-null): 40 pts
          - full_name fuzzy (SequenceMatcher):   0–10 pts
        """
        total = 0.0

        # Phone match
        if (
            candidate.phone_primary
            and existing.phone_primary
            and candidate.phone_primary == existing.phone_primary
        ):
            total += _PHONE_WEIGHT

        # National ID match (both must be non-null)
        if (
            candidate.national_id_number
            and existing.national_id_number
            and candidate.national_id_number == existing.national_id_number
        ):
            total += _NATIONAL_ID_WEIGHT

        # Name fuzzy match
        name_ratio = difflib.SequenceMatcher(
            None,
            candidate.full_name.lower(),
            existing.full_name.lower(),
        ).ratio()
        total += name_ratio * _NAME_WEIGHT

        return min(total, 100.0)

    # ------------------------------------------------------------------
    # Candidate lookup
    # ------------------------------------------------------------------

    @staticmethod
    async def find_candidates(
        pool: asyncpg.Pool,
        data: PatientCreateDTO,
    ) -> list[PatientDTO]:
        """Find existing patients that may match the incoming data.

        Searches by phone_primary OR national_id_number (if provided).
        """
        conditions: list[str] = []
        params: list[object] = []
        idx = 1

        if data.phone_primary:
            conditions.append(f"phone_primary = ${idx}")
            params.append(data.phone_primary)
            idx += 1

        if data.national_id_number:
            conditions.append(f"national_id_number = ${idx}")
            params.append(data.national_id_number)
            idx += 1

        if not conditions:
            return []

        where = " OR ".join(conditions)
        query = f"SELECT * FROM patient WHERE {where};"  # noqa: S608

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [PatientDTO.model_validate(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Auto-queue
    # ------------------------------------------------------------------

    async def auto_queue_if_needed(
        self,
        pool: asyncpg.Pool,
        new_patient_id: UUID,
        candidates: list[PatientDTO],
    ) -> list[UUID]:
        """Insert into mpi_merge_queue for each candidate scoring >= threshold.

        Returns list of newly created queue entry IDs.
        """
        queue_ids: list[UUID] = []

        query = """
            INSERT INTO mpi_merge_queue (
                patient_id_a, patient_id_b, score, status
            )
            VALUES ($1, $2, $3, 'PENDING')
            RETURNING id;
        """

        async with pool.acquire() as conn:
            for candidate in candidates:
                if candidate.clinic_patient_id == new_patient_id:
                    continue

                # Build a temporary DTO for the new patient to score
                # We need the new patient's data — fetch it
                new_row = await conn.fetchrow(
                    "SELECT * FROM patient WHERE clinic_patient_id = $1;",
                    new_patient_id,
                )
                if new_row is None:
                    continue

                new_dto = PatientDTO.model_validate(dict(new_row))
                match_score = self.score(new_dto, candidate)

                if match_score < MPI_THRESHOLD:
                    logger.debug(
                        "mpi_below_threshold",
                        new_patient_id=str(new_patient_id),
                        candidate_id=str(candidate.clinic_patient_id),
                        score=match_score,
                    )
                    continue

                row = await conn.fetchrow(
                    query,
                    new_patient_id,
                    candidate.clinic_patient_id,
                    round(match_score, 2),
                )
                queue_id = row["id"]
                queue_ids.append(queue_id)

                logger.info(
                    "mpi_queued",
                    queue_id=str(queue_id),
                    patient_id_a=str(new_patient_id),
                    patient_id_b=str(candidate.clinic_patient_id),
                    score=match_score,
                )

        return queue_ids

    # ------------------------------------------------------------------
    # Queue retrieval
    # ------------------------------------------------------------------

    @staticmethod
    async def get_pending_queue(
        pool: asyncpg.Pool,
        limit: int = 20,
    ) -> list[dict]:
        """Fetch pending MPI merge queue entries sorted by score DESC."""
        query = """
            SELECT * FROM mpi_merge_queue
            WHERE status = 'PENDING'
            ORDER BY score DESC
            LIMIT $1;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
        return [dict(r) for r in rows]
