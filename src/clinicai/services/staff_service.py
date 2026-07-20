"""Staff CRUD service using asyncpg pool."""

from __future__ import annotations

import datetime
from uuid import UUID

import asyncpg
import structlog

from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.schemas.staff import (
    StaffCapabilityDTO,
    StaffCreateDTO,
    StaffDTO,
    StaffUpdateDTO,
)

logger = structlog.get_logger()


def _record_to_dto(record: asyncpg.Record) -> StaffDTO:
    """Convert an asyncpg Record into a StaffDTO."""
    return StaffDTO.model_validate(dict(record))


class StaffService:
    """CRUD operations for the staff table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_staff(self, data: StaffCreateDTO) -> StaffDTO:
        """Insert a new staff record and return the created DTO."""
        query = """
            INSERT INTO staff (
                full_name, short_name, primary_department,
                primary_location_id, employment_type,
                is_training, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *;
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                data.full_name,
                data.short_name,
                data.primary_department.value,
                data.primary_location_id,
                data.employment_type.value,
                data.is_training,
                data.is_active,
            )

        logger.info("staff_created", staff_id=str(row["id"]))
        return _record_to_dto(row)

    async def get_by_id(self, staff_id: UUID) -> StaffDTO | None:
        """Fetch a single staff member by primary key. Returns None if absent."""
        query = "SELECT * FROM staff WHERE id = $1;"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, staff_id)
        if row is None:
            return None
        return _record_to_dto(row)

    async def list_active(
        self,
        location_id: UUID | None = None,
    ) -> list[StaffDTO]:
        """Return all active staff, optionally filtered by location."""
        if location_id is not None:
            query = """
                SELECT * FROM staff
                WHERE is_active = TRUE AND primary_location_id = $1
                ORDER BY full_name;
            """
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, location_id)
        else:
            query = """
                SELECT * FROM staff
                WHERE is_active = TRUE
                ORDER BY full_name;
            """
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)
        return [_record_to_dto(r) for r in rows]

    async def list_assignable(self) -> list[StaffDTO]:
        """Return staff eligible for auto-assignment (D023 gate).

        Only staff who are:
          - is_active = TRUE
          - is_training = FALSE
        are returned.
        """
        query = """
            SELECT * FROM staff
            WHERE is_active = TRUE AND is_training = FALSE
            ORDER BY full_name;
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [_record_to_dto(r) for r in rows]

    async def update_staff(
        self,
        staff_id: UUID,
        data: StaffUpdateDTO,
    ) -> StaffDTO:
        """Partial-update a staff record. Only non-None fields are written."""
        updates = data.model_dump(exclude_none=True)
        if not updates:
            raise ValidationError("No fields to update")

        # Serialise enum values so asyncpg receives plain strings
        for key in ("primary_department", "employment_type"):
            if key in updates and hasattr(updates[key], "value"):
                updates[key] = updates[key].value

        set_parts: list[str] = []
        values: list[object] = []
        for idx, (col, val) in enumerate(updates.items(), start=1):
            set_parts.append(f"{col} = ${idx}")
            values.append(val)

        set_parts.append(f"updated_at = ${len(values) + 1}")
        values.append(datetime.datetime.now(tz=datetime.timezone.utc))

        values.append(staff_id)
        where_idx = len(values)

        query = (
            f"UPDATE staff SET {', '.join(set_parts)} "  # noqa: S608
            f"WHERE id = ${where_idx} "
            "RETURNING *;"
        )

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

        if row is None:
            raise ResourceNotFoundError(f"Staff {staff_id} not found")

        logger.info(
            "staff_updated",
            staff_id=str(staff_id),
            fields=list(updates.keys()),
        )
        return _record_to_dto(row)

    async def deactivate(self, staff_id: UUID) -> None:
        """Soft-delete: set is_active = FALSE on the given staff member."""
        query = """
            UPDATE staff
            SET is_active = FALSE, updated_at = $2
            WHERE id = $1
            RETURNING id;
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                staff_id,
                datetime.datetime.now(tz=datetime.timezone.utc),
            )

        if row is None:
            raise ResourceNotFoundError(f"Staff {staff_id} not found")

        logger.info("staff_deactivated", staff_id=str(staff_id))


# ---------------------------------------------------------------------------
# P9.6 — staff_capability helpers
# ---------------------------------------------------------------------------
#
# Two free functions sit alongside the StaffService class. They take the
# pool directly to match the rest of the new graph/tool layer (see
# tools/scheduling/find_work_sessions etc.) — service classes are kept for
# CRUD endpoints, but capability flows are graph-internal so the leaner
# function signature reads better at call sites.


_ADD_CAPABILITY_SQL = """
    INSERT INTO staff_capability (staff_id, capability, proficiency_level)
    VALUES ($1, $2, $3)
    ON CONFLICT (staff_id, capability) DO UPDATE
        SET proficiency_level = EXCLUDED.proficiency_level
    RETURNING id, staff_id, capability, proficiency_level, created_at
"""

_GET_BY_CAPABILITY_SQL = """
    SELECT
        s.id                  AS staff_id,
        s.full_name           AS full_name,
        s.short_name          AS short_name,
        s.primary_department  AS primary_department,
        sc.capability         AS capability,
        sc.proficiency_level  AS proficiency_level
    FROM staff s
    JOIN staff_capability sc ON sc.staff_id = s.id
    JOIN work_session_staff wss ON wss.staff_id = s.id
    JOIN work_session ws ON ws.id = wss.work_session_id
    WHERE sc.capability = $1
      AND ws.location_id = $2
      AND s.is_active = TRUE
      AND (NOT $3::boolean OR s.is_training = FALSE)
"""


async def add_capability(
    pool: asyncpg.Pool,
    staff_id: UUID,
    capability: str,
    proficiency_level: str = "COMPETENT",
) -> StaffCapabilityDTO:
    """Upsert a capability for a staff member.

    On the (staff_id, capability) conflict we update proficiency_level so
    callers can promote / demote without a separate code path. The
    `capability` value is enforced at the application layer
    (see clinicai.schemas.staff.Capability); the DB column is TEXT (D019).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _ADD_CAPABILITY_SQL, staff_id, capability, proficiency_level
        )

    logger.info(
        "staff_capability_upserted",
        staff_id=str(staff_id),
        capability=capability,
        proficiency_level=proficiency_level,
    )
    return StaffCapabilityDTO.model_validate(dict(row))


async def get_staff_by_capability(
    pool: asyncpg.Pool,
    capability: str,
    location_id: UUID,
    exclude_training: bool = True,
) -> list[dict[str, object]]:
    """Return on-duty staff at `location_id` who hold `capability`.

    On-duty = has a row in work_session_staff for a work_session at the
    given location. Inactive staff (`is_active=FALSE`) are always
    excluded; trainees (`is_training=TRUE`) are excluded when
    `exclude_training=True` (default, per D023).
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _GET_BY_CAPABILITY_SQL,
            capability,
            location_id,
            exclude_training,
        )
    return [dict(row) for row in rows]
