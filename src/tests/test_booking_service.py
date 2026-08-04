"""The appointment lifecycle state machine (W5).

Ten actions, four role groups and a set of allowed source statuses each. Every
one of these assertions is a clinic rule someone decided, so a change here
should be a conversation rather than a green refactor.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.booking_service import (
    DEAD_STATUSES,
    DOCTOR_OVERLAP_CAP,
    KEEP_STATUS,
    TRANSITIONS,
    Action,
    BookingService,
    is_dead,
    is_walkin,
    resolve_action,
)
from clinicai.services.clinic_policy import DEFAULT_POLICY, ClinicPolicy


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

    def test_a_new_booking_needs_no_confirming(self) -> None:
        """LUẬT ĐÃ ĐỔI (Quang, 2026-08-04) — không còn vòng gọi xác nhận.

        Trước: đặt lịch ra SCHEDULED ("chờ xác nhận"), rồi CSKH gọi cho bệnh
        nhân để xác nhận, rồi bác sĩ nhận. Ba bước cho một việc đã xong.

        Lý do của Quang: *"nó vốn phải là cái đã được gọi tới CSKH hoặc nhắn
        tin rồi mới đặt mà"*. Cuộc gọi ấy CHÍNH LÀ thứ sinh ra lịch hẹn; gọi
        lại để xác nhận cái vừa thoả thuận là làm hai lần một việc.

        `confirm` và `cskh_confirm` KHÔNG nhận CONFIRMED: lịch mới đã chắc rồi,
        "nhận" thêm lần nữa chỉ đẻ ra một event không nói thêm gì.
        """
        assert "CONFIRMED" not in TRANSITIONS["cskh_confirm"].from_statuses
        assert "CONFIRMED" not in TRANSITIONS["confirm"].from_statuses

    def test_the_old_confirm_path_still_works_for_old_appointments(self) -> None:
        """23 lịch SCHEDULED trên prod đặt từ trước luật này.

        Bỏ đường đi của chúng là làm 23 lịch hẹn thật kẹt cứng — người cầm
        chúng vẫn phải khám được, đổi được, huỷ được.
        """
        assert TRANSITIONS["cskh_confirm"].from_statuses == frozenset({"SCHEDULED"})
        assert TRANSITIONS["confirm"].from_statuses == frozenset(
            {"SCHEDULED", "CSKH_CONFIRMED"}
        )
        for act in ("checkin", "cancel", "reschedule"):
            assert "SCHEDULED" in TRANSITIONS[act].from_statuses

    def test_a_doctor_may_still_decline_an_already_confirmed_appointment(
        self,
    ) -> None:
        """Bỏ vòng xác nhận KHÔNG có nghĩa là bác sĩ hết quyền từ chối.

        Lịch mới sinh ra đã CONFIRMED; nếu decline không nhận CONFIRMED thì kể
        từ hôm nay không bác sĩ nào từ chối được lịch nào nữa.
        """
        assert "CONFIRMED" in TRANSITIONS["decline"].from_statuses

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

    def test_reassigning_does_not_send_the_patient_back_to_be_confirmed(
        self,
    ) -> None:
        """Đổi bác sĩ là việc NỘI BỘ.

        Trước đây reassign trả lịch về SCHEDULED — tức là về "chờ xác nhận", và
        CSKH phải gọi lại bệnh nhân chỉ vì bên trong phòng khám đổi người. Thoả
        thuận với bệnh nhân không mất đi khi một bác sĩ bận.
        """
        assert TRANSITIONS["reassign"].to_status == "CONFIRMED"

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

    @pytest.mark.parametrize("action", ["checkin", "undo_checkin", "no_show"])
    def test_only_front_desk_checks_patients_in_or_out(self, action: str) -> None:
        assert TRANSITIONS[action].allowed_roles == frozenset(
            {ClinicRole.RECEPTION, ClinicRole.MANAGEMENT}
        )

    def test_only_the_doctor_actions_are_owner_scoped(self) -> None:
        owner_only = {a for a, t in TRANSITIONS.items() if t.owner_only}
        assert owner_only == {"confirm", "decline", "complete"}


class TestSeatRule:
    def test_dr4women_still_gets_two_plus_one(self) -> None:
        # Đây là luật của Dr4Women, không phải của sản phẩm (C.3) — nhưng nó vẫn
        # phải là cái phòng khám nhận được khi không khai gì, nếu không thì
        # migration đã lặng lẽ đổi cách một phòng khám đang chạy vận hành.
        assert (DEFAULT_POLICY.regular_cap, DEFAULT_POLICY.walkin_cap) == (2, 1)
        assert DEFAULT_POLICY.slot_minutes == 15

    def test_a_clinic_can_have_a_different_rule(self) -> None:
        # Cái test này là toàn bộ lý do C.3 tồn tại: khung 30 phút, 4 chỗ đặt
        # trước, không nhận vãng lai — không phải sửa dòng code nào.
        other = ClinicPolicy(slot_minutes=30, regular_cap=4, walkin_cap=0)
        assert other.cap_for(walkin=False) == 4
        assert other.cap_for(walkin=True) == 0
        assert other.total_seats == 4

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
        moment = datetime(2026, 7, 30, 9, minute, tzinfo=timezone.utc)
        begin, end = DEFAULT_POLICY.bucket(moment)
        assert begin.minute == expected
        assert (end - begin).total_seconds() == 15 * 60

    @pytest.mark.parametrize(
        ("minute", "expected"), [(0, 0), (14, 0), (29, 0), (30, 30), (59, 30)]
    )
    def test_a_half_hour_clinic_lands_in_its_half(
        self, minute: int, expected: int
    ) -> None:
        moment = datetime(2026, 7, 30, 9, minute, tzinfo=timezone.utc)
        begin, end = ClinicPolicy(slot_minutes=30).bucket(moment)
        assert begin.minute == expected
        assert (end - begin).total_seconds() == 30 * 60

    def test_buckets_line_up_with_the_clinic_grid(self) -> None:
        # Flooring on the UTC epoch is only safe because Vietnam's offset is a
        # whole number of hours; if that stopped being true the grid would drift.
        from clinicai.services.booking_service import CLINIC_TZ

        offset = datetime(2026, 7, 30, tzinfo=CLINIC_TZ).utcoffset()
        assert offset is not None
        assert offset.total_seconds() % 3600 == 0


class TestNoInventedDurations:
    """The 15'/5'/+12'/+8' table is gone, and must not come back.

    TestSuggestedLoad used to live here and asserted those four numbers. It
    passed for months, which is the point worth remembering: the test proved the
    code returned what someone once typed, not that a new patient takes fifteen
    minutes. No measurement was ever involved, and nothing in the suite would
    have noticed if the real figure were twenty-two.

    Durations are now OBSERVED (work_item.started_at → finished_at, exposed as
    v_consultation_duration in 20260803000005). Booking limits are the SEAT
    COUNT that Trưởng ca / Quản lý configure. This test guards the boundary
    between those two ideas.
    """

    def test_the_service_no_longer_exports_a_duration_guesser(self) -> None:
        import clinicai.services.booking_service as mod

        assert not hasattr(mod, "suggest_load"), (
            "suggest_load is back. Duration belongs to measurement "
            "(v_consultation_duration), not to a table of constants."
        )

    def test_absent_minutes_stay_absent(self) -> None:
        """NULL means 'nobody estimated', and that is a usable answer.

        The old code filled the gap from the constant table, so every row looked
        estimated even when nobody had estimated anything — which made the
        guessed numbers indistinguishable from real ones in the data.
        """
        from clinicai.services.booking_service import BookingService

        source = inspect.getsource(BookingService.create)
        assert "suggest_load" not in source
        assert "thanh = thanh_min" in source


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
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class TestSeatMessages:
    """The wording is the feature: a receptionist has to know what to do next."""

    def _rows(self, regular: int, walkin: int) -> list[dict[str, str]]:
        return [{"booking_channel": "ZALO", "status": "SCHEDULED"}] * regular + [
            {"booking_channel": "WALK_IN", "status": "SCHEDULED"}
        ] * walkin

    def test_a_full_booked_slot_says_the_third_seat_is_for_walk_ins(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(self._rows(DEFAULT_POLICY.regular_cap, 0))
        message = asyncio.run(
            service._slot_full(
                conn,
                None,
                datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                "ZALO",
                _identity(),
                DEFAULT_POLICY,
            )
        )
        assert message is not None
        assert "2 chỗ đặt hẹn" in message and "vãng lai" in message
        # The window is stated in clinic time, not UTC.
        assert "16:15–16:30" in message

    def test_the_reserved_seat_is_still_free_for_a_walk_in(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(self._rows(DEFAULT_POLICY.regular_cap, 0))
        assert (
            asyncio.run(
                service._slot_full(
                    conn,
                    None,
                    datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                    "WALK_IN",
                    _identity(),
                    DEFAULT_POLICY,
                )
            )
            is None
        )

    def test_a_second_walk_in_is_turned_away(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(self._rows(0, DEFAULT_POLICY.walkin_cap))
        message = asyncio.run(
            service._slot_full(
                conn,
                None,
                datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                "WALK_IN",
                _identity(),
                DEFAULT_POLICY,
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
                    DEFAULT_POLICY,
                )
            )
            is None
        )

    def test_the_sentence_follows_the_clinic_not_the_code(self) -> None:
        # Phòng khám khung 30 phút, 4 chỗ: cùng một hàng dữ liệu, khác câu trả
        # lời. Nếu câu này vẫn nói "15 phút" thì lễ tân được bảo đi tìm một
        # khung không tồn tại trên lưới của họ.
        service = BookingService(MagicMock())
        policy = ClinicPolicy(slot_minutes=30, regular_cap=4, walkin_cap=1)
        conn = _Conn(self._rows(4, 0))
        message = asyncio.run(
            service._slot_full(
                conn,
                None,
                datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                "ZALO",
                _identity(),
                policy,
            )
        )
        assert message is not None
        assert "4 chỗ đặt hẹn" in message
        # 09:00–09:30 UTC = 16:00–16:30 giờ phòng khám, không phải 16:15–16:30.
        assert "16:00–16:30" in message

    def test_a_clinic_that_takes_no_walk_ins_says_so_on_the_first_one(self) -> None:
        service = BookingService(MagicMock())
        policy = ClinicPolicy(walkin_cap=0)
        conn = _Conn(self._rows(0, 0))
        message = asyncio.run(
            service._slot_full(
                conn,
                None,
                datetime(2026, 7, 30, 9, 20, tzinfo=timezone.utc),
                "WALK_IN",
                _identity(),
                policy,
            )
        )
        assert message is not None
        assert "0 chỗ vãng lai" in message

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "source_status"),
    [
        ("reassign", "DOCTOR_DECLINED"),
        ("reschedule", "SCHEDULED"),
    ],
)
async def test_doctor_change_audit_records_target_doctor(
    action: Action,
    source_status: str,
) -> None:
    old_doctor = "d0000000-0000-4000-8000-000000000001"
    target_doctor = "d0000000-0000-4000-8000-000000000002"
    start = datetime(2026, 7, 31, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 31, 9, 30, tzinfo=timezone.utc)
    pool = MagicMock()
    conn = AsyncMock()
    acquire = AsyncMock()
    acquire.__aenter__.return_value = conn
    pool.acquire.return_value = acquire
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction)
    conn.fetchrow.return_value = {
        "id": "a0000000-0000-4000-8000-000000000001",
        "doctor_id": old_doctor,
        "status": source_status,
        "clinic_patient_id": "p0000000-0000-4000-8000-000000000001",
        "slot_start": start,
        "slot_end": end,
        "queue_number": None,
        "booking_channel": "PHONE",
        "patient_in_clinic": True,
        "location_in_clinic": True,
        "service_in_clinic": True,
        "doctor_in_clinic": True,
    }
    service = BookingService(pool)
    audit_log = AsyncMock()

    with (
        patch.object(service, "_guard_slot", AsyncMock(return_value=None)),
        patch.object(service, "_update", AsyncMock(return_value=True)),
        patch("clinicai.services.booking_service._log", new=audit_log),
    ):
        await service.apply_action(
            appointment_id="a0000000-0000-4000-8000-000000000001",
            action=action,
            identity=_identity(),
            doctor_id=target_doctor,
            doctor_id_provided=True,
            slot_start=start if action == "reschedule" else None,
            slot_end=end if action == "reschedule" else None,
        )

    assert audit_log.await_args is not None
    assert audit_log.await_args.kwargs["payload"]["doctor_id"] == target_doctor


class TestANewBookingIsAlreadyDone:
    """Đặt xong là xong — không có bước "chờ xác nhận" nào nữa.

    Quang (2026-08-04): *"ngay khi chọn hết các thông tin và giờ đặt rồi thì ấn
    nút đặt lịch hẹn thì phải hoàn thành luôn rồi chứ nhỉ"*.
    """

    def test_a_booking_lands_confirmed_not_waiting(self) -> None:
        from clinicai.services.booking_service import initial_status

        assert initial_status(False) == "CONFIRMED"

    def test_it_is_never_scheduled_again(self) -> None:
        """SCHEDULED = "Chờ xác nhận" ở mọi màn hình. Sinh ra một dòng SCHEDULED
        là sinh ra một việc gọi điện mà Quang vừa bỏ."""
        from clinicai.services.booking_service import initial_status

        assert initial_status(False) != "SCHEDULED"
        assert initial_status(True) != "SCHEDULED"

    def test_a_walkin_today_is_still_checked_in_on_the_spot(self) -> None:
        """Người đã đứng ở quầy thì không "chờ" gì cả — luật cũ, giữ nguyên."""
        from clinicai.services.booking_service import initial_status

        assert initial_status(True) == "CHECKED_IN"
