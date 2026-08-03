"""Staff CRUD service using asyncpg pool."""

from __future__ import annotations

import datetime
from uuid import UUID

import asyncpg
import structlog

from clinicai.api.identity import StaffIdentity, invalidate_identity_cache
from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.schemas.staff import (
    StaffCapabilityDTO,
    StaffCreateDTO,
    StaffDTO,
    StaffUpdateDTO,
)
from clinicai.services.audit import record_event

logger = structlog.get_logger()

_STAFF_PROJECTION = """
    s.id, s.full_name, s.short_name, m.role AS primary_department,
    s.primary_location_id, s.employment_type, s.is_training,
    m.is_active AS is_active, s.created_at, s.updated_at
"""


def _record_to_dto(
    record: asyncpg.Record,
    *,
    effective_is_active: bool | None = None,
    effective_primary_department: str | None = None,
) -> StaffDTO:
    """Convert an asyncpg Record into a StaffDTO."""
    payload = dict(record)
    if effective_is_active is not None:
        payload = {**payload, "is_active": effective_is_active}
    if effective_primary_department is not None:
        payload = {
            **payload,
            "primary_department": effective_primary_department,
        }
    return StaffDTO.model_validate(payload)


class StaffService:
    """CRUD operations for the staff table."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        clinic_id: str | UUID,
        actor: StaffIdentity | None = None,
    ) -> None:
        self._pool = pool
        self._clinic_id = UUID(str(clinic_id))
        # WHO changed a staff member's role. Creating an account, changing a
        # role and deactivating a membership are privilege changes — the most
        # audit-worthy writes in the system — and they left NO record at all:
        # this service wrote to `staff` and `clinic_membership` and never
        # touched `event_log`. Optional only so existing unit tests that
        # construct the service without a request context keep working; every
        # router path passes it, and the warning below makes an unattributed
        # write visible instead of silent.
        self._actor = actor

    async def _audit(
        self,
        conn: asyncpg.Connection,
        *,
        event_type: str,
        staff_id: str,
        payload: dict[str, object],
    ) -> None:
        """Record a privilege change, or say loudly that it went unattributed."""
        if self._actor is None:
            logger.warning(
                "staff_write_unattributed",
                event_type=event_type,
                staff_id=staff_id,
                clinic_id=str(self._clinic_id),
            )
            return
        await record_event(
            conn,
            event_type=event_type,
            aggregate_type="staff",
            aggregate_id=staff_id,
            identity=self._actor,
            origin="api:staff",
            payload=payload,
        )

    async def create_staff(self, data: StaffCreateDTO) -> StaffDTO:
        """Create a staff row and membership in the acting clinic atomically."""
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
            async with conn.transaction():
                await self._validate_location(conn, data.primary_location_id)
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
                await conn.execute(
                    """
                    INSERT INTO clinic_membership
                        (clinic_id, staff_id, role, is_active)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT ON CONSTRAINT uq_clinic_membership
                    DO UPDATE SET
                        is_active = EXCLUDED.is_active,
                        updated_at = NOW()
                    """,
                    self._clinic_id,
                    row["id"],
                    data.primary_department.value,
                    data.is_active,
                )
                await self._audit(
                    conn,
                    event_type="staff.created",
                    staff_id=str(row["id"]),
                    payload={
                        "staff_id": str(row["id"]),
                        "role": data.primary_department.value,
                        "is_active": data.is_active,
                        "employment_type": data.employment_type.value,
                    },
                )

        logger.info(
            "staff_created",
            staff_id=str(row["id"]),
            clinic_id=str(self._clinic_id),
        )
        return _record_to_dto(row)

    async def get_by_id(self, staff_id: UUID) -> StaffDTO | None:
        """Fetch a staff member only when they belong to the acting clinic."""
        query = f"""
            SELECT {_STAFF_PROJECTION}
            FROM staff AS s
            JOIN clinic_membership AS m ON m.staff_id = s.id
            WHERE s.id = $1 AND m.clinic_id = $2
            ORDER BY m.created_at
            LIMIT 1;
        """  # noqa: S608
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, staff_id, self._clinic_id)
        if row is None:
            return None
        return _record_to_dto(row)

    async def list_active(
        self,
        location_id: UUID | None = None,
    ) -> list[StaffDTO]:
        """Return active staff in the acting clinic."""
        if location_id is not None:
            query = f"""
                SELECT {_STAFF_PROJECTION}
                FROM staff AS s
                JOIN clinic_membership AS m ON m.staff_id = s.id
                WHERE m.clinic_id = $1
                  AND m.is_active = TRUE
                  AND s.is_active = TRUE
                  AND s.primary_location_id = $2
                ORDER BY s.full_name;
            """  # noqa: S608
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, self._clinic_id, location_id)
        else:
            query = f"""
                SELECT {_STAFF_PROJECTION}
                FROM staff AS s
                JOIN clinic_membership AS m ON m.staff_id = s.id
                WHERE m.clinic_id = $1
                  AND m.is_active = TRUE
                  AND s.is_active = TRUE
                ORDER BY s.full_name;
            """  # noqa: S608
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, self._clinic_id)
        return [_record_to_dto(r) for r in rows]

    async def list_assignable(self) -> list[StaffDTO]:
        """Return staff eligible for auto-assignment (D023 gate).

        Only staff who are:
          - is_active = TRUE
          - is_training = FALSE
        are returned.
        """
        query = f"""
            SELECT {_STAFF_PROJECTION}
            FROM staff AS s
            JOIN clinic_membership AS m ON m.staff_id = s.id
            WHERE m.clinic_id = $1
              AND m.is_active = TRUE
              AND s.is_active = TRUE
              AND s.is_training = FALSE
            ORDER BY s.full_name;
        """  # noqa: S608
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, self._clinic_id)
        return [_record_to_dto(r) for r in rows]

    async def update_staff(
        self,
        staff_id: UUID,
        data: StaffUpdateDTO,
    ) -> StaffDTO:
        """Partial-update a staff record. Only non-None fields are written."""
        raw_updates = data.model_dump(exclude_none=True)
        if not raw_updates:
            raise ValidationError("No fields to update")

        effective_is_active = raw_updates.get("is_active")
        membership_role_raw = raw_updates.get("primary_department")
        membership_role = (
            membership_role_raw.value
            if membership_role_raw is not None and hasattr(membership_role_raw, "value")
            else membership_role_raw
        )
        # Build a new mapping: tenant-local membership fields never enter the
        # global staff UPDATE, and enum values become asyncpg-safe strings.
        updates = {
            key: value.value if hasattr(value, "value") else value
            for key, value in raw_updates.items()
            if key not in {"is_active", "primary_department"}
        }

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if "primary_location_id" in updates:
                    await self._validate_location(
                        conn,
                        updates["primary_location_id"],
                    )
                if updates:
                    await self._ensure_global_profile_editable(conn, staff_id)
                    set_parts: list[str] = []
                    values: list[object] = []
                    for idx, (col, val) in enumerate(updates.items(), start=1):
                        set_parts.append(f"{col} = ${idx}")
                        values.append(val)

                    set_parts.append(f"updated_at = ${len(values) + 1}")
                    values.append(datetime.datetime.now(tz=datetime.timezone.utc))
                    values.extend((staff_id, self._clinic_id))
                    staff_idx = len(values) - 1
                    clinic_idx = len(values)

                    query = (
                        f"UPDATE staff AS s SET {', '.join(set_parts)} "  # noqa: S608
                        "FROM clinic_membership AS m "
                        f"WHERE s.id = ${staff_idx} "
                        "AND m.staff_id = s.id "
                        f"AND m.clinic_id = ${clinic_idx} "
                        f"RETURNING {_STAFF_PROJECTION};"
                    )
                    row = await conn.fetchrow(query, *values)
                else:
                    row = await conn.fetchrow(
                        f"""
                        SELECT {_STAFF_PROJECTION}
                        FROM staff AS s
                        JOIN clinic_membership AS m ON m.staff_id = s.id
                        WHERE s.id = $1 AND m.clinic_id = $2
                        LIMIT 1
                        """,  # noqa: S608
                        staff_id,
                        self._clinic_id,
                    )

                if row is None:
                    raise ResourceNotFoundError(f"Staff {staff_id} not found")

                if membership_role is not None:
                    await conn.execute(
                        """
                        UPDATE clinic_membership
                        SET role = $3, updated_at = NOW()
                        WHERE clinic_id = $1 AND staff_id = $2
                        """,
                        self._clinic_id,
                        staff_id,
                        membership_role,
                    )

                if effective_is_active is not None:
                    await conn.execute(
                        """
                        UPDATE clinic_membership
                        SET is_active = $3, updated_at = NOW()
                        WHERE clinic_id = $1 AND staff_id = $2
                        """,
                        self._clinic_id,
                        staff_id,
                        effective_is_active,
                    )
                    if effective_is_active:
                        await conn.execute(
                            """
                            UPDATE staff
                            SET is_active = TRUE, updated_at = NOW()
                            WHERE id = $1
                              AND EXISTS (
                                  SELECT 1 FROM clinic_membership
                                  WHERE clinic_id = $2 AND staff_id = $1
                              )
                            """,
                            staff_id,
                            self._clinic_id,
                        )
                    else:
                        await self._deactivate_global_if_orphaned(conn, staff_id)

                await self._audit(
                    conn,
                    event_type="staff.updated",
                    staff_id=str(staff_id),
                    payload={
                        "staff_id": str(staff_id),
                        # Tên trường đã sửa, không phải giá trị — trừ vai và
                        # trạng thái hoạt động, vì ĐÓ CHÍNH LÀ quyền hạn và một
                        # bản ghi kiểm toán không nói ra thì vô dụng.
                        "fields": sorted(updates.keys()),
                        "role": membership_role,
                        "is_active": effective_is_active,
                    },
                )

        # Vai và trạng thái hoạt động vừa đổi; identity cache đang giữ bản cũ tới
        # 30 giây. Với một thay đổi quyền thì 30 giây là quá dài — xoá thẳng.
        invalidate_identity_cache()

        logger.info(
            "staff_updated",
            staff_id=str(staff_id),
            clinic_id=str(self._clinic_id),
            fields=[
                *updates.keys(),
                *(["primary_department"] if membership_role is not None else []),
                *(["is_active"] if effective_is_active is not None else []),
            ],
        )
        return _record_to_dto(
            row,
            effective_is_active=effective_is_active,
            effective_primary_department=membership_role,
        )

    async def deactivate(self, staff_id: UUID) -> None:
        """Deactivate only the acting clinic's membership."""
        query = """
            UPDATE clinic_membership
            SET is_active = FALSE, updated_at = $2
            WHERE clinic_id = $1 AND staff_id = $3
            RETURNING staff_id;
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    query,
                    self._clinic_id,
                    datetime.datetime.now(tz=datetime.timezone.utc),
                    staff_id,
                )
                if row is not None:
                    await self._deactivate_global_if_orphaned(conn, staff_id)
                    await self._audit(
                        conn,
                        event_type="staff.deactivated",
                        staff_id=str(staff_id),
                        payload={
                            "staff_id": str(staff_id),
                            "clinic_id": str(self._clinic_id),
                        },
                    )

        if row is None:
            raise ResourceNotFoundError(f"Staff {staff_id} not found")

        # Người vừa bị gỡ khỏi phòng khám phải mất quyền NGAY, không phải sau TTL.
        invalidate_identity_cache()

        logger.info(
            "staff_deactivated",
            staff_id=str(staff_id),
            clinic_id=str(self._clinic_id),
        )

    @staticmethod
    async def _deactivate_global_if_orphaned(
        conn: asyncpg.Connection,
        staff_id: UUID,
    ) -> None:
        """Deactivate the global person only after their last membership ends."""
        await conn.execute(
            """
            UPDATE staff
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1
              AND NOT EXISTS (
                  SELECT 1
                  FROM clinic_membership
                  WHERE staff_id = $1 AND is_active = TRUE
              )
            """,
            staff_id,
        )

    async def _validate_location(
        self,
        conn: asyncpg.Connection,
        location_id: object,
    ) -> None:
        """Reject a location UUID that belongs to a different clinic."""
        if location_id is None:
            return
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM clinic_location
                WHERE id = $1 AND clinic_id = $2
            )
            """,
            location_id,
            self._clinic_id,
        )
        if not exists:
            raise ValidationError("primary_location_id is not in this clinic")

    async def _ensure_global_profile_editable(
        self,
        conn: asyncpg.Connection,
        staff_id: UUID,
    ) -> None:
        """Prevent one tenant from rewriting a shared multi-clinic profile."""
        belongs_here = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM clinic_membership
                WHERE staff_id = $1 AND clinic_id = $2
            )
            """,
            staff_id,
            self._clinic_id,
        )
        if not belongs_here:
            raise ResourceNotFoundError(f"Staff {staff_id} not found")

        belongs_only_here = await conn.fetchval(
            """
            SELECT NOT EXISTS (
                SELECT 1
                FROM clinic_membership
                WHERE staff_id = $1 AND clinic_id <> $2
            )
            """,
            staff_id,
            self._clinic_id,
        )
        if not belongs_only_here:
            raise ValidationError(
                "Shared multi-clinic staff profiles require system administration"
            )


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
    SELECT $1, $2, $3
    WHERE EXISTS (
        SELECT 1
        FROM clinic_membership
        WHERE staff_id = $1 AND clinic_id = $4::uuid
    )
      AND NOT EXISTS (
        SELECT 1
        FROM clinic_membership
        WHERE staff_id = $1 AND clinic_id <> $4::uuid
    )
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
      AND ws.clinic_id = $4::uuid
"""


async def add_capability(
    pool: asyncpg.Pool,
    staff_id: UUID,
    capability: str,
    clinic_id: str,
    proficiency_level: str = "COMPETENT",
) -> StaffCapabilityDTO:
    """Upsert a capability for a staff member owned only by this clinic.

    On the (staff_id, capability) conflict we update proficiency_level so
    callers can promote / demote without a separate code path. The
    `capability` value is enforced at the application layer
    (see clinicai.schemas.staff.Capability); the DB column is TEXT (D019).
    Shared multi-clinic profiles require a system-admin path because this table
    has no clinic_id and any write would otherwise affect another tenant.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _ADD_CAPABILITY_SQL,
            staff_id,
            capability,
            proficiency_level,
            clinic_id,
        )
    if row is None:
        raise ResourceNotFoundError(f"Staff {staff_id} not found")

    logger.info(
        "staff_capability_upserted",
        staff_id=str(staff_id),
        clinic_id=clinic_id,
        capability=capability,
        proficiency_level=proficiency_level,
    )
    return StaffCapabilityDTO.model_validate(dict(row))


async def get_staff_by_capability(
    pool: asyncpg.Pool,
    capability: str,
    location_id: UUID,
    clinic_id: str,
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
            clinic_id,
        )
    return [dict(row) for row in rows]
