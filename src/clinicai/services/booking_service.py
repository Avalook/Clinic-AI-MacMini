"""Appointment booking and lifecycle (W5, ADR-0012).

Ported from ``src/dashboard/app/api/appointments/route.ts``, the largest and
most rule-dense route in the dashboard. Two entry points:

* ``create`` — book an appointment.
* ``apply_action`` — the ten-action lifecycle state machine.

WHERE THE REAL GUARANTEES LIVE. Two invariants are enforced by Postgres, not
here: ``appointment_no_doctor_overlap`` (a doctor cannot be in two places) and
the atomic 2+1 slot-capacity trigger (20260714000002). The checks in this module
run *before* the write purely to produce a sentence a receptionist can act on —
"khung 09:15–09:30 đã đủ 2 chỗ" rather than a constraint name. They are
best-effort and fail open, because the database is the actual net; that is why
the SQLSTATE handlers below matter more than the pre-checks do.

THE 2+1 RULE, in the clinic's words: each doctor × 15-minute window has three
seats — two for booked patients and a third reserved for a walk-in. A row with
no doctor assigned is its own queue with the same limits.

Check-in is the one transition that is not an optimistic update. Allocating the
daily queue number and moving the status have to be one serialized transaction,
so it goes through the ``check_in_appointment`` function — the same advisory
lock the walk-in path uses. Two receptionists checking in at once must not hand
out the same number.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError

logger = structlog.get_logger()

CLINIC_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

SLOT_MINUTES = 15
REGULAR_CAP = 2  # BN1 + BN2
WALKIN_CAP = 1  # the third seat, reserved
# A doctor's hard ceiling on overlapping appointments, matching the DB constraint.
DOCTOR_OVERLAP_CAP = 6

# Statuses that no longer hold a seat.
DEAD_STATUSES: frozenset[str] = frozenset({"CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"})

Action = Literal[
    "confirm",
    "decline",
    "complete",
    "checkin",
    "undo_checkin",
    "cskh_confirm",
    "cancel",
    "no_show",
    "reassign",
    "reschedule",
]

# Who may issue which action. Mirrors roles.ts: isDoctorRole / canManageAppt /
# canCheckin / canWriteIntake.
DOCTOR_ROLES: frozenset[ClinicRole] = frozenset(
    {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.TKYK}
)
MANAGE_ROLES: frozenset[ClinicRole] = frozenset(
    {ClinicRole.CSKH, ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA}
)
CHECKIN_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.RECEPTION,
        ClinicRole.MANAGEMENT,
    }
)
INTAKE_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.CSKH,
        ClinicRole.RECEPTION,
        ClinicRole.MANAGEMENT,
        ClinicRole.TRUONG_CA,
    }
)

# "keep" means the action changes fields but not the status (reschedule).
KEEP_STATUS = "__keep__"


@dataclass(frozen=True)
class Transition:
    """What an action does, and what it may be done from."""

    to_status: str
    from_statuses: frozenset[str]
    allowed_roles: frozenset[ClinicRole]
    event_type: str
    # confirm/decline/complete are the doctor's own calls on their own list.
    owner_only: bool = False


_ALIVE = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"})
_PRE_ARRIVAL = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"})
_AWAITING_DOCTOR = frozenset({"SCHEDULED", "CSKH_CONFIRMED"})

# Actions that take the visit off the board again. undo_checkin and cancel mean
# the arrival did not stand, so the still-open steps of that visit are cancelled
# and stop appearing in worklists. no_show is deliberately absent: a patient who
# never arrived never had a visit opened, so there is nothing to cancel.
_WORKFLOW_CANCELLING: frozenset[str] = frozenset({"undo_checkin", "cancel"})

TRANSITIONS: dict[str, Transition] = {
    # The doctor takes the case, even one CSKH already confirmed with the
    # patient — confirmation is two-step and these are the second step.
    "confirm": Transition(
        "CONFIRMED", _AWAITING_DOCTOR, DOCTOR_ROLES, "appointment.confirmed", True
    ),
    # Declining keeps doctor_id for history and surfaces to CSKH for reassignment.
    "decline": Transition(
        "DOCTOR_DECLINED", _AWAITING_DOCTOR, DOCTOR_ROLES, "appointment.declined", True
    ),
    # Finished only from CHECKED_IN: a patient who never arrived cannot have
    # been examined, whatever the doctor pressed.
    "complete": Transition(
        "COMPLETED",
        frozenset({"CHECKED_IN"}),
        DOCTOR_ROLES,
        "appointment.completed",
        True,
    ),
    # D21: reception checks in directly from any live appointment. The doctor's
    # accept/decline is no longer a precondition for the patient being seen.
    "checkin": Transition(
        "CHECKED_IN", _PRE_ARRIVAL, CHECKIN_ROLES, "appointment.checked_in"
    ),
    "undo_checkin": Transition(
        "CONFIRMED",
        frozenset({"CHECKED_IN"}),
        CHECKIN_ROLES,
        "appointment.checkin_undone",
    ),
    # CSKH confirmed with the patient; the slot still waits on the doctor.
    "cskh_confirm": Transition(
        "CSKH_CONFIRMED",
        frozenset({"SCHEDULED"}),
        INTAKE_ROLES,
        "appointment.cskh_confirmed",
    ),
    "cancel": Transition("CANCELLED", _ALIVE, MANAGE_ROLES, "appointment.cancelled"),
    "no_show": Transition(
        "NO_SHOW", _PRE_ARRIVAL, CHECKIN_ROLES, "appointment.no_show"
    ),
    # Reassignment puts a declined appointment back in the pool.
    "reassign": Transition(
        "SCHEDULED",
        frozenset({"DOCTOR_DECLINED"}),
        MANAGE_ROLES,
        "appointment.reassigned",
    ),
    # Rescheduling keeps whatever status the appointment already had.
    "reschedule": Transition(
        KEEP_STATUS, _ALIVE, MANAGE_ROLES, "appointment.rescheduled"
    ),
}


def resolve_action(action: str) -> Transition:
    """The transition for an action. Pure, so the state machine is testable."""
    try:
        return TRANSITIONS[action]
    except KeyError:
        raise ValidationError(f"Hành động không hợp lệ: {action!r}") from None


def is_walkin(channel: str | None) -> bool:
    return (channel or "").strip().upper() == "WALK_IN"


def is_dead(status: str | None) -> bool:
    return (status or "").strip() in DEAD_STATUSES


def slot_bucket(moment: datetime) -> tuple[datetime, datetime]:
    """The 15-minute window containing ``moment``.

    Floor on the UTC epoch: 15 divides 60, and Vietnam's offset is a whole
    number of hours, so the UTC buckets line up with the grid the UI draws.
    """
    epoch = int(moment.timestamp())
    start = epoch - (epoch % (SLOT_MINUTES * 60))
    begin = datetime.fromtimestamp(start, tz=timezone.utc)
    return begin, begin + timedelta(minutes=SLOT_MINUTES)


def suggest_load(
    patient_kind: str | None, need_sono: bool
) -> tuple[int | None, int | None]:
    """Suggested minutes for a booking. A suggestion — CSKH may override it."""
    if patient_kind == "NEW":
        return 15, (12 if need_sono else 0)
    if patient_kind == "RETURN":
        return (7 if need_sono else 5), (8 if need_sono else 0)
    return None, None


def _hhmm(moment: datetime) -> str:
    return moment.astimezone(CLINIC_TZ).strftime("%H:%M")


class BookingService:
    """Book appointments and drive their lifecycle."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ---------------------------------------------------------------- create

    async def create(
        self,
        *,
        clinic_patient_id: str,
        service_type_id: str,
        location_id: str,
        slot_start: datetime,
        slot_end: datetime,
        identity: StaffIdentity,
        doctor_id: str | None = None,
        booking_channel: str | None = None,
        queue_number: str | None = None,
        patient_kind: str | None = None,
        need_sono: bool | None = None,
        thanh_min: int | None = None,
        sono_min: int | None = None,
    ) -> dict[str, Any]:
        """Book one appointment. Returns its id and the status it landed in."""
        if slot_end <= slot_start:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu")

        raw_channel = (booking_channel or "").strip()
        channel = raw_channel or "WALK_IN"
        kind = (patient_kind or "").strip().upper() or None
        if kind not in (None, "NEW", "RETURN"):
            kind = None

        suggested_thanh, suggested_sono = suggest_load(kind, bool(need_sono))
        thanh = thanh_min if thanh_min is not None else suggested_thanh
        sono = sono_min if sono_min is not None else suggested_sono

        # A walk-in booked for today is already standing at the desk, so it is
        # checked in on creation. Only when WALK_IN was chosen explicitly and
        # the slot is today — otherwise a future booking, or one phoned in
        # without a channel, would be checked in for a patient who is not here.
        auto_checkin = raw_channel.upper() == "WALK_IN" and self._is_today(slot_start)
        status = "CHECKED_IN" if auto_checkin else "SCHEDULED"

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await self._validate_booking_refs(
                    conn,
                    clinic_patient_id=clinic_patient_id,
                    location_id=location_id,
                    service_type_id=service_type_id,
                    doctor_id=doctor_id,
                    identity=identity,
                )

                if doctor_id:
                    busy = await self._doctor_conflict(
                        conn, doctor_id, slot_start, slot_end, identity
                    )
                    if busy:
                        raise ConflictError(busy)

                full = await self._slot_full(
                    conn, doctor_id, slot_start, channel, identity
                )
                if full:
                    raise ConflictError(full)

                try:
                    appointment_id = await conn.fetchval(
                        """
                        INSERT INTO appointment (
                            clinic_id, clinic_patient_id, doctor_id, service_type_id,
                            location_id, slot_start, slot_end, booking_channel,
                            queue_number, status, patient_kind, thanh_min, sono_min,
                            need_sono
                        )
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                                $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        RETURNING id
                        """,
                        identity.clinic_id,
                        clinic_patient_id,
                        doctor_id,
                        service_type_id,
                        location_id,
                        slot_start,
                        slot_end,
                        channel,
                        (queue_number or "").strip() or None,
                        status,
                        kind,
                        thanh,
                        sono,
                        need_sono,
                    )
                except asyncpg.ExclusionViolationError as exc:
                    raise ConflictError(
                        "Bác sĩ đã có lịch trùng khung giờ này."
                    ) from exc
                except asyncpg.CheckViolationError as exc:
                    # The atomic 2+1 trigger lost the race to us and won.
                    if "Khung giờ đã đầy" in str(exc):
                        raise ConflictError(str(exc)) from exc
                    raise

                await self._attach_episode(
                    conn,
                    appointment_id=appointment_id,
                    clinic_patient_id=clinic_patient_id,
                    service_type_id=service_type_id,
                    patient_kind=kind,
                    identity=identity,
                )

                await _log(
                    conn,
                    event_type="appointment.created",
                    aggregate_id=str(appointment_id),
                    payload={
                        "appointment_id": str(appointment_id),
                        "clinic_patient_id": clinic_patient_id,
                        "doctor_id": doctor_id,
                        "slot_start": slot_start.isoformat(),
                        "booking_channel": channel,
                        "status": status,
                    },
                    identity=identity,
                    origin="api:appointment-booking",
                )

                if auto_checkin:
                    # Same audit trail as the receptionist's check-in button, and
                    # the visit opens now so the patient shows on the board from
                    # the moment they arrive rather than when someone types.
                    await _log(
                        conn,
                        event_type="appointment.checked_in",
                        aggregate_id=str(appointment_id),
                        payload={
                            "appointment_id": str(appointment_id),
                            "auto_walk_in": True,
                            "status": "CHECKED_IN",
                        },
                        identity=identity,
                        origin="api:appointment-walkin-autocheckin",
                    )
                    await self._open_visit(
                        conn,
                        appointment_id=appointment_id,
                        clinic_patient_id=clinic_patient_id,
                        doctor_id=doctor_id,
                        identity=identity,
                    )

        logger.info(
            "appointment_created",
            appointment_id=str(appointment_id),
            status=status,
            by_staff_id=identity.staff_id,
        )
        return {"appointment_id": str(appointment_id), "status": status}

    # ---------------------------------------------------------------- action

    async def apply_action(
        self,
        *,
        appointment_id: str,
        action: Action,
        identity: StaffIdentity,
        cancellation_reason: str | None = None,
        doctor_id: str | None = None,
        doctor_id_provided: bool = False,
        slot_start: datetime | None = None,
        slot_end: datetime | None = None,
    ) -> dict[str, Any]:
        """Run one lifecycle action. Returns the resulting status."""
        transition = resolve_action(action)

        if identity.role not in transition.allowed_roles:
            raise SafetyGateError(
                f"Vai trò của bạn không được phép '{action}' lịch hẹn"
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                appt = await conn.fetchrow(
                    """
                    SELECT
                        a.id, a.doctor_id, a.status, a.clinic_patient_id,
                        a.slot_start, a.slot_end, a.queue_number,
                        a.booking_channel,
                        EXISTS (
                            SELECT 1
                              FROM patient p
                             WHERE p.clinic_patient_id = a.clinic_patient_id
                               AND p.clinic_id = a.clinic_id
                        ) AS patient_in_clinic,
                        EXISTS (
                            SELECT 1
                              FROM clinic_location l
                             WHERE l.id = a.location_id
                               AND l.clinic_id = a.clinic_id
                        ) AS location_in_clinic,
                        EXISTS (
                            SELECT 1
                              FROM service_type s
                             WHERE s.id = a.service_type_id
                               AND s.clinic_id = a.clinic_id
                        ) AS service_in_clinic,
                        (
                            a.doctor_id IS NULL
                            OR EXISTS (
                                SELECT 1
                                  FROM staff st
                                  JOIN clinic_membership m
                                    ON m.staff_id = st.id
                                 WHERE st.id = a.doctor_id
                                   AND st.is_active
                                   AND m.clinic_id = a.clinic_id
                                   AND m.is_active
                                   AND m.role IN (
                                       'DOCTOR', 'ULTRASOUND_DOCTOR'
                                   )
                            )
                        ) AS doctor_in_clinic
                      FROM appointment a
                     WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
                    """,
                    appointment_id,
                    identity.clinic_id,
                )
                if appt is None:
                    raise NotFoundError("Không tìm thấy lịch hẹn")
                if not appt["patient_in_clinic"]:
                    raise ValidationError(
                        "Bệnh nhân của lịch hẹn không thuộc phòng khám này"
                    )
                if not appt["location_in_clinic"]:
                    raise ValidationError(
                        "Cơ sở của lịch hẹn không thuộc phòng khám này"
                    )
                if not appt["service_in_clinic"]:
                    raise ValidationError(
                        "Dịch vụ của lịch hẹn không thuộc phòng khám này"
                    )
                repairs_doctor = action in {"cancel", "reassign"} or (
                    action == "reschedule" and doctor_id_provided
                )
                if not appt["doctor_in_clinic"] and not repairs_doctor:
                    raise ValidationError(
                        "Bác sĩ của lịch hẹn không thuộc phòng khám này"
                    )

                # A doctor acts on their own list. TKYK enters on their behalf.
                if (
                    transition.owner_only
                    and identity.role is not ClinicRole.TKYK
                    and str(appt["doctor_id"] or "") != identity.staff_id
                ):
                    raise SafetyGateError("Lịch hẹn này không thuộc bác sĩ")

                if appt["status"] not in transition.from_statuses:
                    raise ConflictError(
                        f"Lịch hẹn đang ở trạng thái {appt['status']}, "
                        "không thể thực hiện."
                    )

                new_status = (
                    appt["status"]
                    if transition.to_status == KEEP_STATUS
                    else transition.to_status
                )
                effective_doctor_id = (
                    str(appt["doctor_id"]) if appt["doctor_id"] else None
                )

                if action == "checkin":
                    updated = await self._check_in(conn, appointment_id, transition)
                else:
                    patch = await self._build_patch(
                        conn,
                        action=action,
                        appt=appt,
                        new_status=new_status,
                        cancellation_reason=cancellation_reason,
                        doctor_id=doctor_id,
                        doctor_id_provided=doctor_id_provided,
                        slot_start=slot_start,
                        slot_end=slot_end,
                        identity=identity,
                    )
                    updated = await self._update(
                        conn,
                        appointment_id,
                        patch,
                        transition.from_statuses,
                        identity.clinic_id,
                    )
                    if "doctor_id" in patch:
                        effective_doctor_id = (
                            str(patch["doctor_id"]) if patch["doctor_id"] else None
                        )

                if not updated:
                    # Somebody moved it between our read and our write.
                    raise ConflictError(
                        "Lịch hẹn vừa được người khác cập nhật, hãy tải lại."
                    )

                await _log(
                    conn,
                    event_type=transition.event_type,
                    aggregate_id=appointment_id,
                    payload={
                        "appointment_id": appointment_id,
                        "status": new_status,
                        "doctor_id": effective_doctor_id,
                        "clinic_patient_id": str(appt["clinic_patient_id"]),
                    },
                    identity=identity,
                    origin=f"api:appointment-{action}",
                )

                if action == "checkin":
                    await self._open_visit(
                        conn,
                        appointment_id=appointment_id,
                        clinic_patient_id=str(appt["clinic_patient_id"]),
                        doctor_id=effective_doctor_id,
                        identity=identity,
                    )
                elif action in _WORKFLOW_CANCELLING:
                    await self._cancel_visit_workflow(
                        conn,
                        appointment_id=appointment_id,
                        identity=identity,
                        reason=action,
                    )

        logger.info(
            "appointment_action",
            appointment_id=appointment_id,
            action=action,
            status=new_status,
            by_staff_id=identity.staff_id,
        )
        return {"status": new_status}

    # --------------------------------------------------------------- helpers

    async def _build_patch(
        self,
        conn: asyncpg.Connection,
        *,
        action: str,
        appt: asyncpg.Record,
        new_status: str,
        cancellation_reason: str | None,
        doctor_id: str | None,
        doctor_id_provided: bool,
        slot_start: datetime | None,
        slot_end: datetime | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        patch: dict[str, Any] = {"status": new_status}

        if action == "cancel":
            patch["cancelled_at"] = datetime.now(timezone.utc)
            patch["cancellation_reason"] = (cancellation_reason or "").strip() or None

        elif action == "reassign":
            new_doctor = (doctor_id or "").strip() or None
            patch["doctor_id"] = new_doctor
            await self._guard_slot(
                conn,
                doctor_id=new_doctor,
                slot_start=appt["slot_start"],
                slot_end=appt["slot_end"],
                channel=appt["booking_channel"],
                exclude_id=str(appt["id"]),
                identity=identity,
            )

        elif action == "reschedule":
            if slot_start is None or slot_end is None:
                raise ValidationError("Thiếu giờ hẹn mới")
            if slot_end <= slot_start:
                raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu")
            patch["slot_start"] = slot_start
            patch["slot_end"] = slot_end
            # Only touch the doctor when the field was actually sent; an absent
            # field means "leave them", an empty one means "unassign".
            if doctor_id_provided:
                patch["doctor_id"] = (doctor_id or "").strip() or None
            target_doctor = (
                patch.get("doctor_id")
                if doctor_id_provided
                else (str(appt["doctor_id"]) if appt["doctor_id"] else None)
            )
            await self._guard_slot(
                conn,
                doctor_id=target_doctor,
                slot_start=slot_start,
                slot_end=slot_end,
                channel=appt["booking_channel"],
                exclude_id=str(appt["id"]),
                identity=identity,
            )

        return patch

    async def _guard_slot(
        self,
        conn: asyncpg.Connection,
        *,
        doctor_id: str | None,
        slot_start: datetime,
        slot_end: datetime,
        channel: str | None,
        exclude_id: str,
        identity: StaffIdentity,
    ) -> None:
        if doctor_id:
            await self._validate_doctor_ref(conn, doctor_id, identity.clinic_id)
            busy = await self._doctor_conflict(
                conn, doctor_id, slot_start, slot_end, identity, exclude_id
            )
            if busy:
                raise ConflictError(busy)
        full = await self._slot_full(
            conn, doctor_id, slot_start, channel or "", identity, exclude_id
        )
        if full:
            raise ConflictError(full)

    async def _validate_booking_refs(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_patient_id: str,
        location_id: str,
        service_type_id: str,
        doctor_id: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Fail before INSERT when any supplied id belongs to another clinic."""
        refs = await conn.fetchrow(
            """
            SELECT
                EXISTS (
                    SELECT 1 FROM patient p
                     WHERE p.clinic_patient_id = $1::uuid
                       AND p.clinic_id = $5::uuid
                       AND p.is_active
                ) AS patient_ok,
                EXISTS (
                    SELECT 1 FROM clinic_location l
                     WHERE l.id = $2::uuid
                       AND l.clinic_id = $5::uuid
                       AND l.is_active
                ) AS location_ok,
                EXISTS (
                    SELECT 1 FROM service_type s
                     WHERE s.id = $3::uuid
                       AND s.clinic_id = $5::uuid
                       AND s.is_active
                ) AS service_ok,
                (
                    $4::uuid IS NULL
                    OR EXISTS (
                        SELECT 1
                          FROM staff st
                          JOIN clinic_membership m ON m.staff_id = st.id
                         WHERE st.id = $4::uuid
                           AND st.is_active
                           AND m.clinic_id = $5::uuid
                           AND m.is_active
                           AND m.role IN (
                               'DOCTOR', 'ULTRASOUND_DOCTOR'
                           )
                    )
                ) AS doctor_ok
            """,
            clinic_patient_id,
            location_id,
            service_type_id,
            doctor_id,
            identity.clinic_id,
        )
        if refs is None or not refs["patient_ok"]:
            raise ValidationError("Mã bệnh nhân không thuộc phòng khám này")
        if not refs["location_ok"]:
            raise ValidationError("Mã cơ sở không thuộc phòng khám này")
        if not refs["service_ok"]:
            raise ValidationError("Mã dịch vụ không thuộc phòng khám này")
        if not refs["doctor_ok"]:
            raise ValidationError("Mã bác sĩ không thuộc phòng khám này")

    async def _validate_doctor_ref(
        self,
        conn: asyncpg.Connection,
        doctor_id: str,
        clinic_id: str | None,
    ) -> None:
        valid = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM staff st
                  JOIN clinic_membership m ON m.staff_id = st.id
                 WHERE st.id = $1::uuid
                   AND st.is_active
                   AND m.clinic_id = $2::uuid
                   AND m.is_active
                   AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
            )
            """,
            doctor_id,
            clinic_id,
        )
        if not valid:
            raise ValidationError("Mã bác sĩ không thuộc phòng khám này")

    async def _update(
        self,
        conn: asyncpg.Connection,
        appointment_id: str,
        patch: dict[str, Any],
        from_statuses: frozenset[str],
        clinic_id: str | None,
    ) -> bool:
        columns = list(patch)
        assignments = ", ".join(f"{c} = ${i + 3}" for i, c in enumerate(columns))
        try:
            updated = await conn.fetchval(
                f"""
                UPDATE appointment
                   SET {assignments}, updated_at = now()
                 WHERE id = $1::uuid AND status = ANY($2::text[])
                   AND clinic_id = ${len(columns) + 3}::uuid
                RETURNING id
                """,
                appointment_id,
                list(from_statuses),
                *[patch[c] for c in columns],
                clinic_id,
            )
        except asyncpg.ExclusionViolationError as exc:
            raise ConflictError("Bác sĩ đã có lịch trùng khung giờ mới này.") from exc
        except asyncpg.CheckViolationError as exc:
            if "Khung giờ đã đầy" in str(exc):
                raise ConflictError(str(exc)) from exc
            raise
        return updated is not None

    async def _check_in(
        self,
        conn: asyncpg.Connection,
        appointment_id: str,
        transition: Transition,
    ) -> bool:
        """Status change plus daily queue number, in one serialized call."""
        rows = await conn.fetch(
            "SELECT * FROM check_in_appointment($1::uuid, $2::text[])",
            appointment_id,
            list(transition.from_statuses),
        )
        return bool(rows)

    async def _doctor_conflict(
        self,
        conn: asyncpg.Connection,
        doctor_id: str,
        slot_start: datetime,
        slot_end: datetime,
        identity: StaffIdentity,
        exclude_id: str | None = None,
    ) -> str | None:
        """A sentence about why this doctor is unavailable, or None.

        Advisory only — ``appointment_no_doctor_overlap`` is the real guard. The
        point of doing it first is that "đã đạt giới hạn 6 lịch trong khung
        09:15–09:30" tells a receptionist what to do next; a constraint name
        does not.
        """
        overlapping = await conn.fetchval(
            """
            SELECT count(*)
              FROM appointment
             WHERE clinic_id = $1::uuid
               AND doctor_id = $2::uuid
               AND slot_start < $4
               AND slot_end > $3
               AND status <> ALL ($5::text[])
               AND ($6::uuid IS NULL OR id <> $6::uuid)
            """,
            identity.clinic_id,
            doctor_id,
            slot_start,
            slot_end,
            ["CANCELLED", "NO_SHOW"],
            exclude_id,
        )
        if (overlapping or 0) < DOCTOR_OVERLAP_CAP:
            return None

        name = await conn.fetchval(
            "SELECT full_name FROM staff WHERE id = $1::uuid", doctor_id
        )
        day = slot_start.astimezone(CLINIC_TZ).strftime("%d/%m")
        return (
            f"Bác sĩ{' ' + name if name else ''} đã đạt giới hạn "
            f"{DOCTOR_OVERLAP_CAP} lịch hẹn trong khung giờ "
            f"{_hhmm(slot_start)}–{_hhmm(slot_end)} ngày {day}. "
            "Vui lòng chọn khung giờ khác."
        )

    async def _slot_full(
        self,
        conn: asyncpg.Connection,
        doctor_id: str | None,
        slot_start: datetime,
        channel: str,
        identity: StaffIdentity,
        exclude_id: str | None = None,
    ) -> str | None:
        """The 2+1 rule, as a sentence. Advisory; the DB trigger is the net."""
        begin, end = slot_bucket(slot_start)
        rows = await conn.fetch(
            """
            SELECT booking_channel, status
              FROM appointment
             WHERE clinic_id = $1::uuid
               AND slot_start >= $2 AND slot_start < $3
               AND (($4::uuid IS NULL AND doctor_id IS NULL)
                    OR doctor_id = $4::uuid)
               AND ($5::uuid IS NULL OR id <> $5::uuid)
            """,
            identity.clinic_id,
            begin,
            end,
            doctor_id,
            exclude_id,
        )

        regular = walkin = 0
        for row in rows:
            if is_dead(row["status"]):
                continue
            if is_walkin(row["booking_channel"]):
                walkin += 1
            else:
                regular += 1

        window = f"{_hhmm(begin)}–{_hhmm(end)}"
        if is_walkin(channel):
            if walkin >= WALKIN_CAP:
                return (
                    f"Khung {window} đã có khách vãng lai — "
                    "chuyển khách sang khung 15 phút kế tiếp."
                )
            return None
        if regular >= REGULAR_CAP:
            return (
                f"Khung {window} đã đủ {REGULAR_CAP} chỗ đặt hẹn (BN1, BN2) — "
                "chọn khung khác. Chỗ thứ 3 chỉ dành cho khách vãng lai."
            )
        return None

    async def _attach_episode(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: Any,
        clinic_patient_id: str,
        service_type_id: str,
        patient_kind: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Attach the booking to a care episode.

        NEW closes any live episode and opens a fresh one — a new problem is a
        new course of care. RETURN (or an unstated kind with a live episode)
        joins the existing one, reopening a PENDING_CLOSE because a patient who
        came back is evidently still in care.
        """
        live = await conn.fetchrow(
            """
            SELECT id, status FROM care_episode
             WHERE clinic_id = $1::uuid
               AND clinic_patient_id = $2::uuid
               AND service_type_id = $3::uuid
               AND status <> 'CLOSED'
             ORDER BY created_at DESC LIMIT 1
            """,
            identity.clinic_id,
            clinic_patient_id,
            service_type_id,
        )

        if patient_kind == "NEW" and live is not None:
            await conn.execute(
                "UPDATE care_episode SET status = 'CLOSED', closed_at = now(), "
                "close_reason = 'new_problem', updated_at = now() "
                "WHERE id = $1 AND clinic_id = $2::uuid",
                live["id"],
                identity.clinic_id,
            )
            live = None

        if live is not None:
            if live["status"] == "PENDING_CLOSE":
                await conn.execute(
                    "UPDATE care_episode SET status = 'OPEN', closed_at = NULL, "
                    "close_reason = NULL, updated_at = now() "
                    "WHERE id = $1 AND clinic_id = $2::uuid",
                    live["id"],
                    identity.clinic_id,
                )
            episode_id = live["id"]
        else:
            episode_id = await conn.fetchval(
                """
                INSERT INTO care_episode (
                    clinic_id, clinic_patient_id, service_type_id,
                    opened_appointment_id, status
                )
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'OPEN')
                RETURNING id
                """,
                identity.clinic_id,
                clinic_patient_id,
                service_type_id,
                appointment_id,
            )

        await conn.execute(
            "UPDATE appointment SET episode_id = $2 "
            "WHERE id = $1 AND clinic_id = $3::uuid",
            appointment_id,
            episode_id,
            identity.clinic_id,
        )

    async def _open_visit(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: Any,
        clinic_patient_id: str,
        doctor_id: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Open the visit so the patient appears on the board immediately.

        ON CONFLICT rather than catching UniqueViolationError. Catching it looks
        equivalent and is not: by the time asyncpg raises, Postgres has already
        aborted the transaction, so swallowing the exception leaves a dead
        transaction whose COMMIT silently degrades to ROLLBACK. This runs LAST
        in the check-in transaction, so the status change, the queue number and
        the audit event all disappeared with it — while the API answered
        {"ok": true, "status": "CHECKED_IN"}.

        Reproduced end to end: check in, undo, check in again (undo_checkin only
        patches the appointment, so the visit row survives). The second check-in
        returned 200 and left the appointment CONFIRMED. A receptionist is told
        the patient has arrived and the patient never reaches the board.

        clinical_record_service._ensure_visit has always done it this way.

        Also instantiates the visit's work items. Both check-in paths — the
        walk-in auto-check-in in create() and the checkin action — already funnel
        through here, so hanging the kernel off this one place covers walk-ins by
        construction instead of by remembering to add a second call.
        """
        visit_id = await conn.fetchval(
            """
            INSERT INTO visit (
                clinic_id, clinic_patient_id, appointment_id,
                attending_doctor_id, status, checked_in_at, checked_in_by
            )
            VALUES ($1::uuid, $2::uuid, $3, $4::uuid, 'OPEN', now(), $5::uuid)
            ON CONFLICT (appointment_id) WHERE appointment_id IS NOT NULL
            DO NOTHING
            RETURNING visit_id
            """,
            identity.clinic_id,
            clinic_patient_id,
            appointment_id,
            doctor_id,
            identity.staff_id,
        )

        if visit_id is None:
            # Somebody opened the visit first — a nurse recording vitals, a
            # sonographer. It still needs its work items.
            visit_id = await conn.fetchval(
                "SELECT visit_id FROM visit "
                "WHERE appointment_id = $1 AND clinic_id = $2::uuid",
                appointment_id,
                identity.clinic_id,
            )

        if visit_id is None:
            return

        created = await conn.fetchval(
            "SELECT public.instantiate_visit_workflow("
            "$1::uuid, $2::uuid, $3::uuid, $4::text)",
            identity.clinic_id,
            visit_id,
            identity.staff_id,
            identity.role.value,
        )
        if not created:
            # Zero is normal on a re-check-in (the items are already there) but
            # also what a clinic with no seeded node catalogue returns, and that
            # one is worth seeing in the log rather than discovering when the
            # board is empty.
            logger.info(
                "visit_workflow_no_new_items",
                visit_id=str(visit_id),
                clinic_id=identity.clinic_id,
            )

    async def _cancel_visit_workflow(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: Any,
        identity: StaffIdentity,
        reason: str,
    ) -> None:
        """Cancel the still-open work items of this appointment's visit.

        Completed steps stay completed: the patient really did arrive and
        really did have their vitals taken, and undoing a mis-click does not
        make that untrue.
        """
        visit_id = await conn.fetchval(
            "SELECT visit_id FROM visit "
            "WHERE appointment_id = $1 AND clinic_id = $2::uuid",
            appointment_id,
            identity.clinic_id,
        )
        if visit_id is None:
            return

        await conn.fetchval(
            "SELECT public.cancel_visit_workflow("
            "$1::uuid, $2::uuid, $3::uuid, $4::text, $5::text)",
            identity.clinic_id,
            visit_id,
            identity.staff_id,
            identity.role.value,
            reason,
        )

    def _is_today(self, moment: datetime) -> bool:
        local = moment.astimezone(CLINIC_TZ).date()
        return local == datetime.now(CLINIC_TZ).date()


async def _log(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    identity: StaffIdentity,
    origin: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, actor_staff_id, event_published)
        VALUES ($1::uuid, $2, 'appointment', $3, $4, $5, $6, $7::uuid, FALSE)
        """,
        identity.clinic_id,
        event_type,
        aggregate_id,
        json.dumps(payload),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": origin,
            }
        ),
        origin,
        identity.staff_id,
    )
