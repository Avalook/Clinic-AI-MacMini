"""Scheduling service: WorkSession, WorkSessionStaff, and Appointment operations."""

from __future__ import annotations

import datetime
from uuid import UUID

import asyncpg
import structlog

from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.schemas.scheduling import (
    AppointmentCreateDTO,
    AppointmentDTO,
    WorkSessionCreateDTO,
    WorkSessionDTO,
    WorkSessionStaffAssignDTO,
    WorkSessionStaffDTO,
)

logger = structlog.get_logger()


def _to_work_session_dto(record: asyncpg.Record) -> WorkSessionDTO:
    return WorkSessionDTO.model_validate(dict(record))


def _to_wss_dto(record: asyncpg.Record) -> WorkSessionStaffDTO:
    return WorkSessionStaffDTO.model_validate(dict(record))


def _to_appointment_dto(record: asyncpg.Record) -> AppointmentDTO:
    return AppointmentDTO.model_validate(dict(record))


class SchedulingService:
    """Operations for work sessions, staff assignments, and appointments."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Work Session
    # ------------------------------------------------------------------

    async def create_work_session(
        self,
        data: WorkSessionCreateDTO,
    ) -> WorkSessionDTO:
        """Insert a new work session.

        Raises ValidationError on duplicate (location + date + session_type).
        """
        query = """
            INSERT INTO work_session (
                location_id, session_date, session_type,
                start_time, end_time, max_patients
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *;
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    data.location_id,
                    data.session_date,
                    data.session_type.value,
                    data.start_time,
                    data.end_time,
                    data.max_patients,
                )
        except asyncpg.UniqueViolationError as exc:
            raise ValidationError(
                "Work session already exists for this location/date/type"
            ) from exc

        logger.info("work_session_created", session_id=str(row["id"]))
        return _to_work_session_dto(row)

    # ------------------------------------------------------------------
    # Work Session Staff Assignment
    # ------------------------------------------------------------------

    async def assign_staff_to_session(
        self,
        data: WorkSessionStaffAssignDTO,
    ) -> WorkSessionStaffDTO:
        """Assign a staff member to a work session at a given station.

        Snapshots is_training from the current staff record at assignment time.
        """
        async with self._pool.acquire() as conn:
            # Snapshot is_training from staff table
            staff_row = await conn.fetchrow(
                "SELECT is_training FROM staff WHERE id = $1;",
                data.staff_id,
            )
            if staff_row is None:
                raise ResourceNotFoundError(f"Staff {data.staff_id} not found")

            is_training_snapshot: bool = staff_row["is_training"]

            row = await conn.fetchrow(
                """
                INSERT INTO work_session_staff (
                    work_session_id, staff_id, role, station,
                    on_call_flag, is_training
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *;
                """,
                data.work_session_id,
                data.staff_id,
                data.role,
                data.station,
                data.on_call_flag,
                is_training_snapshot,
            )

        logger.info(
            "staff_assigned_to_session",
            work_session_id=str(data.work_session_id),
            staff_id=str(data.staff_id),
            is_training=is_training_snapshot,
        )
        return _to_wss_dto(row)

    async def get_oncall_staff(self, work_session_id: UUID) -> dict | None:
        """Return on-duty staff for a session, excluding trainees.

        Returns None if the work session does not exist (so the tool layer
        can raise WorkSessionNotFoundError with its own error_code).
        Returns {"staff": [<row dicts>]} when the session exists — note that
        an empty staff list is a valid result (session created, none assigned).
        """
        query = """
            SELECT
                wss.staff_id,
                s.full_name,
                wss.role,
                wss.station
            FROM work_session_staff wss
            JOIN staff s ON s.id = wss.staff_id
            WHERE wss.work_session_id = $1
              AND wss.is_training = FALSE
            ORDER BY wss.station;
        """
        async with self._pool.acquire() as conn:
            session_row = await conn.fetchrow(
                "SELECT id FROM work_session WHERE id = $1;",
                work_session_id,
            )
            if session_row is None:
                return None
            staff_rows = await conn.fetch(query, work_session_id)

        return {"staff": [dict(r) for r in staff_rows]}

    async def get_session_with_staff(self, work_session_id: UUID) -> dict:
        """Fetch a work session together with its assigned staff list."""
        async with self._pool.acquire() as conn:
            session_row = await conn.fetchrow(
                "SELECT * FROM work_session WHERE id = $1;",
                work_session_id,
            )
            if session_row is None:
                raise ResourceNotFoundError(f"Work session {work_session_id} not found")

            staff_rows = await conn.fetch(
                """
                SELECT wss.*, s.full_name, s.primary_department
                FROM work_session_staff wss
                JOIN staff s ON s.id = wss.staff_id
                WHERE wss.work_session_id = $1
                ORDER BY wss.station;
                """,
                work_session_id,
            )

        return {
            "session": _to_work_session_dto(session_row),
            "staff": [dict(r) for r in staff_rows],
        }

    # ------------------------------------------------------------------
    # Appointment
    # ------------------------------------------------------------------

    async def create_appointment(
        self,
        data: AppointmentCreateDTO,
    ) -> AppointmentDTO:
        """Insert a new appointment.

        Validates:
        - slot_end > slot_start (also enforced by DTO)
        - If work_session_id is set, confirms that doctor_id has an assignment
          in that work session (on-duty gate).
        """
        # DTO-level validation already guarantees slot_end > slot_start;
        # re-check here for defence-in-depth (e.g. service called directly).
        if data.slot_end <= data.slot_start:
            raise ValidationError("slot_end must be after slot_start")

        try:
            async with self._pool.acquire() as conn:
                # Validate doctor on-duty in the work session if both are set
                if data.work_session_id and data.doctor_id:
                    on_duty = await conn.fetchrow(
                        """
                        SELECT 1 FROM work_session_staff
                        WHERE work_session_id = $1 AND staff_id = $2;
                        """,
                        data.work_session_id,
                        data.doctor_id,
                    )
                    if on_duty is None:
                        raise ValidationError(
                            "Doctor is not assigned to the specified work session"
                        )

                row = await conn.fetchrow(
                    """
                    INSERT INTO appointment (
                        clinic_patient_id, doctor_id, work_session_id,
                        location_id, service_type_id, booking_channel,
                        slot_start, slot_end, assigned_station, queue_number,
                        is_priority_slot, is_walkin, status
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                        'SCHEDULED'
                    )
                    RETURNING *;
                    """,
                    data.clinic_patient_id,
                    data.doctor_id,
                    data.work_session_id,
                    data.location_id,
                    data.service_type_id,
                    data.booking_channel,
                    data.slot_start,
                    data.slot_end,
                    data.assigned_station,
                    data.queue_number,
                    data.is_priority_slot,
                    data.is_walkin,
                )
        except asyncpg.exceptions.ExclusionViolationError as exc:
            raise ValidationError("Bác sĩ đã có lịch hẹn trùng khung giờ này") from exc

        logger.info("appointment_created", appointment_id=str(row["id"]))
        return _to_appointment_dto(row)

    async def confirm_appointment(self, appointment_id: UUID) -> AppointmentDTO:
        """Transition an appointment from SCHEDULED → CONFIRMED.

        Raises ValidationError if current status is not SCHEDULED.
        """
        async with self._pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT status FROM appointment WHERE id = $1;",
                appointment_id,
            )
            if existing is None:
                raise ResourceNotFoundError(f"Appointment {appointment_id} not found")
            if existing["status"] != "SCHEDULED":
                raise ValidationError(
                    f"Cannot confirm appointment with status '{existing['status']}'"
                )

            row = await conn.fetchrow(
                """
                UPDATE appointment
                SET status = 'CONFIRMED',
                    confirmed_at = $2,
                    updated_at = $2
                WHERE id = $1
                RETURNING *;
                """,
                appointment_id,
                datetime.datetime.now(tz=datetime.timezone.utc),
            )

        logger.info("appointment_confirmed", appointment_id=str(appointment_id))
        return _to_appointment_dto(row)

    async def cancel_appointment(
        self,
        appointment_id: UUID,
        reason: str,
    ) -> AppointmentDTO:
        """Cancel an appointment, recording the reason.

        Raises ValidationError if status is COMPLETED or already CANCELLED.
        """
        async with self._pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT status FROM appointment WHERE id = $1;",
                appointment_id,
            )
            if existing is None:
                raise ResourceNotFoundError(f"Appointment {appointment_id} not found")
            if existing["status"] in ("COMPLETED", "CANCELLED"):
                raise ValidationError(
                    f"Cannot cancel appointment with status '{existing['status']}'"
                )

            now = datetime.datetime.now(tz=datetime.timezone.utc)
            row = await conn.fetchrow(
                """
                UPDATE appointment
                SET status = 'CANCELLED',
                    cancelled_at = $2,
                    cancellation_reason = $3,
                    updated_at = $2
                WHERE id = $1
                RETURNING *;
                """,
                appointment_id,
                now,
                reason,
            )

        logger.info(
            "appointment_cancelled",
            appointment_id=str(appointment_id),
            reason=reason,
        )
        return _to_appointment_dto(row)
