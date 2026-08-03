"""Booking override CRUD (C.4 — per-doctor / per-slot capacity overrides).

Same shape as ``clinic_settings_service.py``: thin Python over a well-
constrained schema. Every write is tenant-scoped (from ``identity.clinic_id``)
and audit-logged via ``event_log``. The DB CHECK constraints are the real
guards; Python validates early so a bad number becomes a 422 instead of an
opaque constraint error.

Override layers (resolve order):
  Tầng 3  slot_booking_override   — date range × hour range × doctor
  Tầng 2  doctor_booking_override — per doctor, optionally per weekday
  Tầng 1  clinic.settings.booking — clinic default (C.3)

SQL function ``resolve_effective_cap()`` does the merge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

# Safety ceiling: overrides cannot exceed these (mirrors DB CHECK).
MAX_CAP = 100
# Max date range for slot overrides (mirrors DB CHECK).
MAX_SLOT_RANGE_DAYS = 90


# ── DTOs ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DoctorOverrideDTO:
    """One doctor_booking_override row."""

    id: str
    doctor_id: str
    weekday: int | None
    slot_minutes: int | None
    regular_cap: int | None
    walkin_cap: int | None
    effective_from: date
    effective_to: date | None
    reason: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class SlotOverrideDTO:
    """One slot_booking_override row."""

    id: str
    doctor_id: str | None
    date_start: date
    date_end: date
    hour_start: int
    hour_end: int
    regular_cap: int | None
    walkin_cap: int | None
    reason: str
    created_by: str
    created_at: datetime


# ── Service ────────────────────────────────────────────────────────────────

class BookingOverrideService:
    """CRUD for booking capacity overrides."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Doctor overrides (Tầng 2) ──────────────────────────────────────

    async def create_doctor_override(
        self,
        *,
        identity: StaffIdentity,
        doctor_id: str,
        weekday: int | None = None,
        slot_minutes: int | None = None,
        regular_cap: int | None = None,
        walkin_cap: int | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Create a per-doctor booking capacity override.

        Returns ``{"ok": True, "id": "<uuid>"}``.
        """
        self._validate_doctor_fields(
            weekday=weekday,
            slot_minutes=slot_minutes,
            regular_cap=regular_cap,
            walkin_cap=walkin_cap,
            effective_from=effective_from,
            effective_to=effective_to,
        )

        eff_from = effective_from or date.today()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Verify doctor belongs to this clinic.
                exists = await conn.fetchval(
                    """
                    SELECT 1 FROM clinic_membership
                     WHERE clinic_id = $1::uuid
                       AND staff_id  = $2::uuid
                       AND is_active = true
                    """,
                    identity.clinic_id,
                    doctor_id,
                )
                if not exists:
                    raise ValidationError(
                        "Bác sĩ không thuộc phòng khám này hoặc đã bị vô hiệu."
                    )

                override_id = await conn.fetchval(
                    """
                    INSERT INTO doctor_booking_override
                        (clinic_id, doctor_id, weekday, slot_minutes,
                         regular_cap, walkin_cap,
                         effective_from, effective_to, created_by, reason)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9::uuid, $10)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    doctor_id,
                    weekday,
                    slot_minutes,
                    regular_cap,
                    walkin_cap,
                    eff_from,
                    effective_to,
                    identity.auth_user_id,
                    reason,
                )

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.doctor_created",
                    payload={
                        "override_id": str(override_id),
                        "doctor_id": doctor_id,
                        "weekday": weekday,
                        "slot_minutes": slot_minutes,
                        "regular_cap": regular_cap,
                        "walkin_cap": walkin_cap,
                        "effective_from": str(eff_from),
                        "effective_to": str(effective_to) if effective_to else None,
                        "reason": reason,
                    },
                )

        logger.info(
            "doctor_override_created",
            override_id=str(override_id),
            doctor_id=doctor_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": str(override_id)}

    async def list_doctor_overrides(
        self,
        *,
        identity: StaffIdentity,
        doctor_id: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """List doctor overrides for this clinic."""
        async with self._pool.acquire() as conn:
            if doctor_id:
                rows = await conn.fetch(
                    """
                    SELECT id, doctor_id, weekday, slot_minutes,
                           regular_cap, walkin_cap,
                           effective_from, effective_to, reason,
                           created_by, created_at
                      FROM doctor_booking_override
                     WHERE clinic_id = $1::uuid
                       AND doctor_id = $2::uuid
                       AND ($3::boolean IS FALSE
                            OR (effective_to IS NULL OR effective_to >= current_date))
                     ORDER BY effective_from DESC
                    """,
                    identity.clinic_id,
                    doctor_id,
                    active_only,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, doctor_id, weekday, slot_minutes,
                           regular_cap, walkin_cap,
                           effective_from, effective_to, reason,
                           created_by, created_at
                      FROM doctor_booking_override
                     WHERE clinic_id = $1::uuid
                       AND ($2::boolean IS FALSE
                            OR (effective_to IS NULL OR effective_to >= current_date))
                     ORDER BY effective_from DESC
                    """,
                    identity.clinic_id,
                    active_only,
                )

        return [_doctor_row_to_dict(r) for r in rows]

    async def delete_doctor_override(
        self,
        *,
        identity: StaffIdentity,
        override_id: str,
    ) -> None:
        """Delete a doctor override by id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                deleted = await conn.fetchval(
                    """
                    DELETE FROM doctor_booking_override
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING id
                    """,
                    override_id,
                    identity.clinic_id,
                )
                if deleted is None:
                    raise NotFoundError("Override không tồn tại.")

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.doctor_deleted",
                    payload={"override_id": override_id},
                )

        logger.info(
            "doctor_override_deleted",
            override_id=override_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )

    # ── Slot overrides (Tầng 3) ────────────────────────────────────────

    async def create_slot_override(
        self,
        *,
        identity: StaffIdentity,
        doctor_id: str | None = None,
        date_start: date,
        date_end: date,
        hour_start: int,
        hour_end: int,
        regular_cap: int | None = None,
        walkin_cap: int | None = None,
        reason: str,
    ) -> dict[str, Any]:
        """Create a per-slot booking capacity override (date range)."""
        self._validate_slot_fields(
            date_start=date_start,
            date_end=date_end,
            hour_start=hour_start,
            hour_end=hour_end,
            regular_cap=regular_cap,
            walkin_cap=walkin_cap,
            reason=reason,
        )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Verify doctor if specified.
                if doctor_id:
                    exists = await conn.fetchval(
                        """
                        SELECT 1 FROM clinic_membership
                         WHERE clinic_id = $1::uuid
                           AND staff_id  = $2::uuid
                           AND is_active = true
                        """,
                        identity.clinic_id,
                        doctor_id,
                    )
                    if not exists:
                        raise ValidationError(
                            "Bác sĩ không thuộc phòng khám này hoặc đã bị vô hiệu."
                        )

                override_id = await conn.fetchval(
                    """
                    INSERT INTO slot_booking_override
                        (clinic_id, doctor_id, date_start, date_end,
                         hour_start, hour_end, regular_cap, walkin_cap,
                         reason, created_by)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10::uuid)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    doctor_id,
                    date_start,
                    date_end,
                    hour_start,
                    hour_end,
                    regular_cap,
                    walkin_cap,
                    reason,
                    identity.auth_user_id,
                )

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.slot_created",
                    payload={
                        "override_id": str(override_id),
                        "doctor_id": doctor_id,
                        "date_start": str(date_start),
                        "date_end": str(date_end),
                        "hour_start": hour_start,
                        "hour_end": hour_end,
                        "regular_cap": regular_cap,
                        "walkin_cap": walkin_cap,
                        "reason": reason,
                    },
                )

        logger.info(
            "slot_override_created",
            override_id=str(override_id),
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
            date_range=f"{date_start}..{date_end}",
        )
        return {"ok": True, "id": str(override_id)}

    async def list_slot_overrides(
        self,
        *,
        identity: StaffIdentity,
        date_from: date | None = None,
        date_to: date | None = None,
        doctor_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List slot overrides, optionally filtered by date range and doctor."""
        query_date = date_from or date.today()
        query_end = date_to or query_date

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, doctor_id, date_start, date_end,
                       hour_start, hour_end, regular_cap, walkin_cap,
                       reason, created_by, created_at
                  FROM slot_booking_override
                 WHERE clinic_id = $1::uuid
                   AND date_end >= $2
                   AND date_start <= $3
                   AND ($4::uuid IS NULL OR doctor_id = $4::uuid
                        OR doctor_id IS NULL)
                 ORDER BY date_start, hour_start
                """,
                identity.clinic_id,
                query_date,
                query_end,
                doctor_id,
            )

        return [_slot_row_to_dict(r) for r in rows]

    async def delete_slot_override(
        self,
        *,
        identity: StaffIdentity,
        override_id: str,
    ) -> None:
        """Delete a slot override by id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                deleted = await conn.fetchval(
                    """
                    DELETE FROM slot_booking_override
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING id
                    """,
                    override_id,
                    identity.clinic_id,
                )
                if deleted is None:
                    raise NotFoundError("Override không tồn tại.")

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.slot_deleted",
                    payload={"override_id": override_id},
                )

        logger.info(
            "slot_override_deleted",
            override_id=override_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )

    # ── Internals ──────────────────────────────────────────────────────

    @staticmethod
    def _validate_doctor_fields(
        *,
        weekday: int | None,
        slot_minutes: int | None,
        regular_cap: int | None,
        walkin_cap: int | None,
        effective_from: date | None,
        effective_to: date | None,
    ) -> None:
        if weekday is not None and not 0 <= weekday <= 6:
            raise ValidationError("weekday phải từ 0 (CN) đến 6 (T7)")
        if slot_minutes is not None:
            if not 1 <= slot_minutes <= 60:
                raise ValidationError("slot_minutes phải từ 1 đến 60")
            if 60 % slot_minutes != 0:
                raise ValidationError("slot_minutes phải chia hết 60")
        if regular_cap is not None and not 1 <= regular_cap <= MAX_CAP:
            raise ValidationError(f"regular_cap phải từ 1 đến {MAX_CAP}")
        if walkin_cap is not None and not 0 <= walkin_cap <= MAX_CAP:
            raise ValidationError(f"walkin_cap phải từ 0 đến {MAX_CAP}")
        if (
            slot_minutes is None
            and regular_cap is None
            and walkin_cap is None
        ):
            raise ValidationError(
                "Ít nhất một trường (slot_minutes, regular_cap,"
                " walkin_cap) phải có giá trị."
            )
        if effective_from and effective_to and effective_to < effective_from:
            raise ValidationError("effective_to phải sau effective_from")

    @staticmethod
    def _validate_slot_fields(
        *,
        date_start: date,
        date_end: date,
        hour_start: int,
        hour_end: int,
        regular_cap: int | None,
        walkin_cap: int | None,
        reason: str,
    ) -> None:
        if date_end < date_start:
            raise ValidationError("date_end phải sau hoặc bằng date_start")
        if (date_end - date_start).days > MAX_SLOT_RANGE_DAYS:
            raise ValidationError(
                f"Khoảng thời gian tối đa {MAX_SLOT_RANGE_DAYS} ngày"
            )
        if not 0 <= hour_start <= 23:
            raise ValidationError("hour_start phải từ 0 đến 23")
        if not 1 <= hour_end <= 24:
            raise ValidationError("hour_end phải từ 1 đến 24")
        if hour_end <= hour_start:
            raise ValidationError("hour_end phải lớn hơn hour_start")
        if regular_cap is None and walkin_cap is None:
            raise ValidationError(
                "Ít nhất một trường (regular_cap, walkin_cap) phải có giá trị."
            )
        if regular_cap is not None and not 1 <= regular_cap <= MAX_CAP:
            raise ValidationError(f"regular_cap phải từ 1 đến {MAX_CAP}")
        if walkin_cap is not None and not 0 <= walkin_cap <= MAX_CAP:
            raise ValidationError(f"walkin_cap phải từ 0 đến {MAX_CAP}")
        if not reason or not reason.strip():
            raise ValidationError("Lý do thay đổi không được để trống.")

    @staticmethod
    async def _log_event(
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        await conn.execute(
            """
            INSERT INTO event_log
                (clinic_id, event_type, aggregate_type, aggregate_id,
                 payload, metadata, source, event_published)
            VALUES ($1::uuid, $2, 'booking_override', $3,
                    $4, $5, 'api:booking-override', FALSE)
            """,
            identity.clinic_id,
            event_type,
            payload.get("override_id", identity.clinic_id),
            json.dumps(payload),
            json.dumps(
                {
                    "clinic_role": identity.role.value,
                    "clinic_staff_id": identity.staff_id,
                    "actor_auth_user_id": identity.auth_user_id,
                    "origin": "api:booking-override",
                }
            ),
        )


# ── Row mappers ────────────────────────────────────────────────────────────


def _doctor_row_to_dict(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "doctor_id": str(r["doctor_id"]),
        "weekday": r["weekday"],
        "slot_minutes": r["slot_minutes"],
        "regular_cap": r["regular_cap"],
        "walkin_cap": r["walkin_cap"],
        "effective_from": r["effective_from"].isoformat(),
        "effective_to": r["effective_to"].isoformat() if r["effective_to"] else None,
        "reason": r["reason"],
        "created_by": str(r["created_by"]),
        "created_at": r["created_at"].isoformat(),
    }


def _slot_row_to_dict(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "doctor_id": str(r["doctor_id"]) if r["doctor_id"] else None,
        "date_start": r["date_start"].isoformat(),
        "date_end": r["date_end"].isoformat(),
        "hour_start": r["hour_start"],
        "hour_end": r["hour_end"],
        "regular_cap": r["regular_cap"],
        "walkin_cap": r["walkin_cap"],
        "reason": r["reason"],
        "created_by": str(r["created_by"]),
        "created_at": r["created_at"].isoformat(),
    }
