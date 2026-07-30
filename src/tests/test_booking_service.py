"""The appointment lifecycle state machine (W5).

Ten actions, four role groups and a set of allowed source statuses each. Every
one of these assertions is a clinic rule someone decided, so a change here
should be a conversation rather than a green refactor.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.booking_service import (
    DEAD_STATUSES,
    DOCTOR_OVERLAP_CAP,
    KEEP_STATUS,
    REGULAR_CAP,
    TRANSITIONS,
    WALKIN_CAP,
    BookingService,
    is_dead,
    is_walkin,
    resolve_action,
    slot_bucket,
    suggest_load,
)


class TestTransitions:
    def test_every_action_is_covered(self) -> None:
        assert set(TRANSITIONS) == {
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
        }

    def test_a_patient_who_never_arrived_cannot_be_completed(self) -> None:
        # COMPLETED only from CHECKED_IN. Allowing it from CONFIRMED would let a
        # doctor close a visit for someone still in the car park.
        assert TRANSITIONS["complete"].from_statuses == frozenset({"CHECKED_IN"})

    def test_confirmation_is_two_step(self) -> None:
        # CSKH confirms with the patient (SCHEDULED -> CSKH_CONFIRMED); the slot
        # still waits on the doctor, so confirm accepts both.
        assert TRANSITIONS["cskh_confirm"].from_statuses == frozenset({"SCHEDULED"})
        assert TRANSITIONS["confirm"].from_statuses == frozenset(
            {"SCHEDULED", "CSKH_CONFIRMED"}
        )

    def test_check_in_does_not_wait_for_the_doctor(self) -> None:
        # D21: reception checks in from any live appointment. Requiring CONFIRMED
        # first meant patients waited at the desk for a doctor to press a button.
        assert TRANSITIONS["checkin"].from_statuses == frozenset(
            {"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"}
        )

    def test_no_show_is_impossible_once_they_have_arrived(self) -> None:
        assert "CHECKED_IN" not in TRANSITIONS["no_show"].from_statuses

    def test_rescheduling_keeps_the_status(self) -> None:
        # Moving the time does not un-confirm or un-check-in an appointment.
        assert TRANSITIONS["reschedule"].to_status == KEEP_STATUS

    def test_reassignment_only_rescues_a_declined_appointment(self) -> None:
        assert TRANSITIONS["reassign"].from_statuses == frozenset({"DOCTOR_DECLINED"})

    def test_a_declined_appointment_is_not_cancelled(self) -> None:
        # It keeps its doctor_id for history and surfaces to CSKH to reassign.
        assert TRANSITIONS["decline"].to_status == "DOCTOR_DECLINED"

    @pytest.mark.parametrize("action", ["", "CONFIRM", "finish", "delete", "reopen"])
    def test_unknown_actions_are_refused(self, action: str) -> None:
        with pytest.raises(ValidationError):
            resolve_action(action)


class TestRoleGates:
    @pytest.mark.parametrize("action", ["confirm", "decline", "complete"])
    def test_only_the_doctor_side_accepts_or_finishes(self, action: str) -> None:
        transition = TRANSITIONS[action]
        assert transition.allowed_roles == frozenset(
            {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.TKYK}
        )
        # And on their OWN list — TKYK is the exception, entering on behalf.
        assert transition.owner_only

    @pytest.mark.parametrize("action", ["cancel", "reassign", "reschedule"])
    def test_lifecycle_management_is_cskh_and_above(self, action: str) -> None:
        allowed = TRANSITIONS[action].allowed_roles
        assert ClinicRole.CSKH in allowed and ClinicRole.MANAGEMENT in allowed
        assert ClinicRole.DOCTOR not in allowed

    def test_cashiers_never_move_an_appointment(self) -> None:
        for transition in TRANSITIONS.values():
            for cashier in (
                ClinicRole.CASHIER,
                ClinicRole.CASHIER_THUOC,
                ClinicRole.CASHIER_DV,
            ):
                assert cashier not in transition.allowed_roles

    def test_only_the_doctor_actions_are_owner_scoped(self) -> None:
        owner_only = {a for a, t in TRANSITIONS.items() if t.owner_only}
        assert owner_only == {"confirm", "decline", "complete"}


class TestSeatRule:
    def test_two_plus_one(self) -> None:
        # Each doctor × 15 minutes: two booked seats, one held for a walk-in.
        assert (REGULAR_CAP, WALKIN_CAP) == (2, 1)

    def test_a_freed_seat_is_reusable(self) -> None:
        # Cancelled, no-show and declined stop holding the slot; anything else
        # still does, or the grid would oversell.
        assert DEAD_STATUSES == frozenset({"CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"})
        for status in ("SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"):
            assert not is_dead(status)

    @pytest.mark.parametrize("channel", ["WALK_IN", "walk_in", " Walk_In "])
    def test_walkin_detection_is_forgiving(self, channel: str) -> None:
        assert is_walkin(channel)

    @pytest.mark.parametrize("channel", [None, "", "ZALO", "PHONE"])
    def test_everything_else_takes_a_booked_seat(self, channel: str | None) -> None:
        assert not is_walkin(channel)

    def test_the_doctor_overlap_ceiling_matches_the_db(self) -> None:
        assert DOCTOR_OVERLAP_CAP == 6


class TestSlotBucket:
    @pytest.mark.parametrize(
        ("minute", "expected"), [(0, 0), (7, 0), (14, 0), (15, 15), (44, 30), (59, 45)]
    )
    def test_a_time_lands_in_its_quarter(self, minute: int, expected: int) -> None:
        begin, end = slot_bucket(datetime(2026, 7, 30, 9, minute, tzinfo=timezone.utc))
        assert begin.minute == expected
        assert (end - begin).total_seconds() == 15 * 60

    def test_buckets_line_up_with_the_clinic_grid(self) -> None:
        # Flooring on the UTC epoch is only safe because Vietnam's offset is a
        # whole number of hours; if that stopped being true the grid would drift.
        from clinicai.services.booking_service import CLINIC_TZ

        offset = datetime(2026, 7, 30, tzinfo=CLINIC_TZ).utcoffset()
        assert offset is not None
        assert offset.total_seconds() % 3600 == 0


class TestSuggestedLoad:
    def test_a_new_patient_gets_the_longer_slot(self) -> None:
        assert suggest_load("NEW", False) == (15, 0)
        assert suggest_load("NEW", True) == (15, 12)

    def test_a_returning_patient_is_quicker(self) -> None:
        assert suggest_load("RETURN", False) == (5, 0)
        assert suggest_load("RETURN", True) == (7, 8)

    def test_no_kind_means_no_suggestion(self) -> None:
        # Rather than guessing a duration onto the schedule.
        assert suggest_load(None, True) == (None, None)
        assert suggest_load("SOMETHING", False) == (None, None)


class _Conn:
    """A connection stub returning canned answers, in call order."""

    def __init__(self, *results: object) -> None:
        self._results = list(results)
        self.executed: list[str] = []

    async def fetchval(self, sql: str, *args: object) -> object:
        self.executed.append(sql)
        return self._results.pop(0) if self._results else None

    async def fetch(self, sql: str, *args: object) -> list[Any]:
        self.executed.append(sql)
        return self._results.pop(0) if self._results else []  # type: ignore[return-value]

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append(sql)


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="CSKH A",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
    )


class TestSeatMessages:
    """The wording is the feature: a receptionist has to know what to do next."""

    def _rows(self, regular: int, walkin: int) -> list[dict[str, str]]:
        return [{"booking_channel": "ZALO", "status": "SCHEDULED"}] * regular + [
            {"booking_channel": "WALK_IN", "status": "SCHEDULED"}
        ] * walkin

    def test_a_full_booked_slot_says_the_third_seat_is_for_walk_ins(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(self._rows(REGULAR_CAP, 0))
        message = asyncio.run(
            service._slot_full(
                conn,
                None,
                datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                "ZALO",
                _identity(),
            )
        )
        assert message is not None
        assert "BN1, BN2" in message and "vãng lai" in message
        # The window is stated in clinic time, not UTC.
        assert "16:15–16:30" in message

    def test_the_reserved_seat_is_still_free_for_a_walk_in(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(self._rows(REGULAR_CAP, 0))
        assert (
            asyncio.run(
                service._slot_full(
                    conn,
                    None,
                    datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                    "WALK_IN",
                    _identity(),
                )
            )
            is None
        )

    def test_a_second_walk_in_is_turned_away(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(self._rows(0, WALKIN_CAP))
        message = asyncio.run(
            service._slot_full(
                conn,
                None,
                datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                "WALK_IN",
                _identity(),
            )
        )
        assert message is not None and "khung 15 phút kế tiếp" in message

    def test_cancelled_bookings_free_their_seat(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn([{"booking_channel": "ZALO", "status": s} for s in DEAD_STATUSES])
        assert (
            asyncio.run(
                service._slot_full(
                    conn,
                    None,
                    datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                    "ZALO",
                    _identity(),
                )
            )
            is None
        )

    def test_the_overlap_message_names_the_doctor_and_the_window(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(DOCTOR_OVERLAP_CAP, "BS Thành")
        message = asyncio.run(
            service._doctor_conflict(
                conn,
                "d1",
                datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 30, 9, 30, tzinfo=timezone.utc),
                _identity(),
            )
        )
        assert message is not None
        assert "BS Thành" in message and "16:00–16:30" in message and "30/07" in message

    def test_under_the_ceiling_is_not_a_conflict(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(DOCTOR_OVERLAP_CAP - 1)
        assert (
            asyncio.run(
                service._doctor_conflict(
                    conn,
                    "d1",
                    datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc),
                    datetime(2026, 7, 30, 9, 30, tzinfo=timezone.utc),
                    _identity(),
                )
            )
            is None
        )


class TestPatchBuilding:
    def _appt(self) -> dict[str, Any]:
        return {
            "id": "a1",
            "doctor_id": None,
            "status": "SCHEDULED",
            "slot_start": datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc),
            "slot_end": datetime(2026, 7, 30, 9, 30, tzinfo=timezone.utc),
            "booking_channel": "ZALO",
        }

    def test_cancelling_records_when_and_why(self) -> None:
        patch = asyncio.run(
            BookingService(MagicMock())._build_patch(
                _Conn(),
                action="cancel",
                appt=self._appt(),
                new_status="CANCELLED",
                cancellation_reason="  khách bận  ",
                doctor_id=None,
                doctor_id_provided=False,
                slot_start=None,
                slot_end=None,
                identity=_identity(),
            )
        )
        assert patch["status"] == "CANCELLED"
        assert patch["cancellation_reason"] == "khách bận"
        assert patch["cancelled_at"] is not None

    def test_a_blank_reason_is_stored_as_nothing(self) -> None:
        patch = asyncio.run(
            BookingService(MagicMock())._build_patch(
                _Conn(),
                action="cancel",
                appt=self._appt(),
                new_status="CANCELLED",
                cancellation_reason="   ",
                doctor_id=None,
                doctor_id_provided=False,
                slot_start=None,
                slot_end=None,
                identity=_identity(),
            )
        )
        assert patch["cancellation_reason"] is None

    def test_rescheduling_without_a_new_time_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            asyncio.run(
                BookingService(MagicMock())._build_patch(
                    _Conn(),
                    action="reschedule",
                    appt=self._appt(),
                    new_status="SCHEDULED",
                    cancellation_reason=None,
                    doctor_id=None,
                    doctor_id_provided=False,
                    slot_start=None,
                    slot_end=None,
                    identity=_identity(),
                )
            )

    def test_a_backwards_slot_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            asyncio.run(
                BookingService(MagicMock())._build_patch(
                    _Conn(),
                    action="reschedule",
                    appt=self._appt(),
                    new_status="SCHEDULED",
                    cancellation_reason=None,
                    doctor_id=None,
                    doctor_id_provided=False,
                    slot_start=datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc),
                    slot_end=datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc),
                    identity=_identity(),
                )
            )

    def test_an_absent_doctor_field_leaves_the_doctor_alone(self) -> None:
        # Absent means "leave them"; an explicit null means "unassign". Getting
        # this backwards would silently strip doctors off rescheduled bookings.
        patch = asyncio.run(
            BookingService(MagicMock())._build_patch(
                _Conn([], []),
                action="reschedule",
                appt=self._appt(),
                new_status="SCHEDULED",
                cancellation_reason=None,
                doctor_id=None,
                doctor_id_provided=False,
                slot_start=datetime(2026, 7, 30, 11, 0, tzinfo=timezone.utc),
                slot_end=datetime(2026, 7, 30, 11, 30, tzinfo=timezone.utc),
                identity=_identity(),
            )
        )
        assert "doctor_id" not in patch

    def test_an_explicit_null_unassigns(self) -> None:
        patch = asyncio.run(
            BookingService(MagicMock())._build_patch(
                _Conn([], []),
                action="reschedule",
                appt=self._appt(),
                new_status="SCHEDULED",
                cancellation_reason=None,
                doctor_id=None,
                doctor_id_provided=True,
                slot_start=datetime(2026, 7, 30, 11, 0, tzinfo=timezone.utc),
                slot_end=datetime(2026, 7, 30, 11, 30, tzinfo=timezone.utc),
                identity=_identity(),
            )
        )
        assert patch["doctor_id"] is None
