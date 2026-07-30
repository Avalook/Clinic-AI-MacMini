"""Unit tests for the clinical rules moved out of the dashboard (W5).

The DB paths are covered by integration tests; what is pinned here is the part
that would change a patient's record if it were wrong — link normalisation, how
measurements merge, and which roles each gate admits.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.lab import _ORDER_GUARD, _RESULT_GUARD
from clinicai.api.v1.routers.ultrasound import _SONOGRAPHER_GUARD
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.exceptions import ValidationError as CoreValidationError
from clinicai.services.clinical_record_service import (
    ARRIVED_APPOINTMENT_STATUSES as ARRIVED,
)
from clinicai.services.clinical_record_service import (
    RECORD_LOCK,
    may_write,
    merge_objective,
    merge_vitals_only,
)
from clinicai.services.clinical_record_service import (
    WRITABLE_VISIT_STATUSES as RECORD_WRITABLE,
)
from clinicai.services.config_service import (
    PRICE_ROLES,
    ROSTER_ADMIN_ROLES,
    ROSTER_ROLES,
    RosterService,
    parse_price,
    week_start_of,
)
from clinicai.services.cskh_service import (
    INTAKE_ROLES,
    clinic_today,
    manual_source_ref,
)
from clinicai.services.lab_order_service import normalize_link
from clinicai.services.patient_service import validate_phone
from clinicai.services.service_log_service import (
    MILESTONE_COLUMN,
    QUEUE_CANCELLED,
    QUEUE_DONE,
    QUEUE_IN_PROGRESS,
    QUEUE_WAITING,
    SONO_ROLES,
    TASK_DONE,
    TASK_IN_PROGRESS,
    TASK_WAITING,
    queue_patch,
    source_ref,
    task_patch,
)
from clinicai.services.ultrasound_service import (
    MEASURE_KEYS,
    WRITABLE_VISIT_STATUSES,
    merge_findings,
    num_or_none,
)


class TestNormalizeLink:
    def test_a_pasted_host_gets_a_scheme(self) -> None:
        # Without this the href resolves against our own domain and whoever
        # opens the result gets a 404 instead of the lab's PDF.
        assert (
            normalize_link("drive.google.com/file/x")
            == "https://drive.google.com/file/x"
        )
        assert normalize_link("www.lab.vn/kq") == "https://www.lab.vn/kq"

    @pytest.mark.parametrize(
        "link",
        [
            "https://drive.google.com/x",
            "http://lab.vn/x",
            "//cdn.lab.vn/x",
            "mailto:lab@example.com",
            "tel:+84901234567",
            "/internal/report",
        ],
    )
    def test_anything_already_addressable_is_left_alone(self, link: str) -> None:
        assert normalize_link(link) == link

    @pytest.mark.parametrize("empty", [None, "", "   "])
    def test_blank_is_no_link(self, empty: str | None) -> None:
        assert normalize_link(empty) is None


class TestNumOrNone:
    @pytest.mark.parametrize(
        ("raw", "expected"), [("12.5", 12.5), (3, 3.0), (0, 0.0), (-1, -1.0)]
    )
    def test_numbers_pass_through(self, raw: object, expected: float) -> None:
        assert num_or_none(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "abc", True, False, [], {}])
    def test_a_blank_never_becomes_zero(self, raw: object) -> None:
        # "not measured" and "measured as 0" are different things on a
        # pregnancy record, so anything unparseable must stay None.
        assert num_or_none(raw) is None


class TestMergeFindings:
    def test_saving_one_measurement_keeps_the_others(self) -> None:
        previous = {"bpd": 45.0, "hc": 170.0, "is_abnormal": False}
        merged = merge_findings(
            previous, measurements={"ac": 150.0}, is_abnormal=None, status=None
        )
        assert merged == {"bpd": 45.0, "hc": 170.0, "ac": 150.0, "is_abnormal": False}

    def test_clearing_a_field_is_possible(self) -> None:
        merged = merge_findings(
            {"crl": 30.0}, measurements={"crl": ""}, is_abnormal=None, status=None
        )
        assert merged["crl"] is None

    def test_the_abnormal_flag_is_only_ever_set_explicitly(self) -> None:
        # It must never be inferred from the measurements.
        merged = merge_findings(
            {"is_abnormal": True},
            measurements={"bpd": 45.0},
            is_abnormal=None,
            status=None,
        )
        assert merged["is_abnormal"] is True

        cleared = merge_findings(
            {"is_abnormal": True}, measurements=None, is_abnormal=False, status=None
        )
        assert cleared["is_abnormal"] is False

    def test_all_seven_standard_measurements_are_supported(self) -> None:
        assert MEASURE_KEYS == ("crl", "nt", "bpd", "hc", "ac", "fl", "efw")

    def test_a_finalised_visit_is_not_writable(self) -> None:
        assert WRITABLE_VISIT_STATUSES == frozenset({"OPEN", "IN_PROGRESS"})
        assert "FINALIZED" not in WRITABLE_VISIT_STATUSES


class TestGuards:
    def test_only_doctors_order_tests(self) -> None:
        assert _ORDER_GUARD.allowed_roles == frozenset(
            {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR}
        )

    def test_reception_and_management_may_not_enter_results(self) -> None:
        # Entering a lab result is clinical work — decided 2026-06-17.
        assert ClinicRole.RECEPTION not in _RESULT_GUARD.allowed_roles
        assert ClinicRole.MANAGEMENT not in _RESULT_GUARD.allowed_roles
        assert _RESULT_GUARD.allowed_roles == frozenset(
            {
                ClinicRole.DOCTOR,
                ClinicRole.ULTRASOUND_DOCTOR,
                ClinicRole.TKYK,
                ClinicRole.NURSE_ULTRASOUND,
            }
        )

    def test_ultrasound_stays_narrow(self) -> None:
        # Deliberately not widened to doctors in general.
        assert _SONOGRAPHER_GUARD.allowed_roles == frozenset(
            {ClinicRole.ULTRASOUND_DOCTOR}
        )


class TestClinicalRecordWriteRoles:
    @pytest.mark.parametrize(
        "role",
        [
            ClinicRole.DOCTOR,
            ClinicRole.ULTRASOUND_DOCTOR,
            ClinicRole.TKYK,
            ClinicRole.NURSE_ULTRASOUND,
        ],
    )
    def test_clinical_writers_may_write_the_full_record(self, role: ClinicRole) -> None:
        assert may_write(role, vitals_only=False)
        assert may_write(role, vitals_only=True)

    def test_reception_writes_vitals_and_nothing_else(self) -> None:
        assert may_write(ClinicRole.RECEPTION, vitals_only=True)
        assert not may_write(ClinicRole.RECEPTION, vitals_only=False)

    @pytest.mark.parametrize(
        "role",
        [
            ClinicRole.CASHIER,
            ClinicRole.CASHIER_THUOC,
            ClinicRole.CASHIER_DV,
            ClinicRole.CSKH,
            ClinicRole.MANAGEMENT,
            ClinicRole.TRUONG_CA,
        ],
    )
    def test_nobody_else_touches_a_clinical_record(self, role: ClinicRole) -> None:
        # Management included: being in charge is not the same as being clinical.
        assert not may_write(role, vitals_only=False)
        assert not may_write(role, vitals_only=True)


class TestObjectiveMerge:
    def test_a_doctor_saving_late_does_not_wipe_the_nurses_vitals(self) -> None:
        # The doctor opened the form before the nurse entered vitals, so their
        # form posts an empty vitals block. Blind overwrite would delete
        # measurements already taken from the patient.
        stored = {"vitals": {"bp": "120/80", "pulse": "78"}, "notes": "n"}
        incoming = {"vitals": {"bp": "", "temp": None}}

        merged = merge_objective(stored, incoming, incoming_was_sent=True)

        assert merged is not None
        assert merged["vitals"] == {"bp": "120/80", "pulse": "78"}
        assert merged["notes"] == "n"

    def test_a_real_value_does_override(self) -> None:
        merged = merge_objective(
            {"vitals": {"bp": "120/80"}},
            {"vitals": {"bp": "130/85"}},
            incoming_was_sent=True,
        )
        assert merged is not None
        assert merged["vitals"]["bp"] == "130/85"

    def test_nothing_stored_and_nothing_sent_stays_null(self) -> None:
        # An empty object would look like "examined, found nothing".
        assert merge_objective(None, None, incoming_was_sent=False) is None

    def test_stored_content_survives_a_save_that_omits_objective(self) -> None:
        merged = merge_objective(
            {"vitals": {"bp": "120/80"}}, None, incoming_was_sent=False
        )
        assert merged is not None
        assert merged["vitals"]["bp"] == "120/80"

    def test_a_json_string_from_the_driver_is_understood(self) -> None:
        merged = merge_objective(
            '{"vitals": {"bp": "110/70"}}', {"vitals": {}}, incoming_was_sent=True
        )
        assert merged is not None
        assert merged["vitals"]["bp"] == "110/70"


class TestVitalsOnlyMerge:
    def test_the_nurse_path_leaves_the_doctors_sections_alone(self) -> None:
        stored = {"vitals": {"bp": "old"}, "exam": "doctor's findings"}
        merged = merge_vitals_only(stored, {"vitals": {"bp": "120/80"}})
        assert merged == {"vitals": {"bp": "120/80"}, "exam": "doctor's findings"}


class TestImmutability:
    def test_finalized_and_amended_are_both_closed(self) -> None:
        # A whitelist, so a future terminal status cannot slip through as
        # writable the way it would with a FINALIZED-only check (Circular 13).
        assert RECORD_WRITABLE == frozenset({"OPEN", "IN_PROGRESS"})
        for closed in ("FINALIZED", "AMENDED", "CANCELLED"):
            assert closed not in RECORD_WRITABLE

    def test_vitals_need_the_patient_to_have_arrived(self) -> None:
        assert ARRIVED == frozenset({"CHECKED_IN", "COMPLETED"})
        for not_yet in ("SCHEDULED", "CONFIRMED", "CSKH_CONFIRMED"):
            assert not_yet not in ARRIVED

    def test_the_record_locks_after_two_shifts(self) -> None:
        assert RECORD_LOCK == timedelta(hours=48)


class TestCskh:
    def test_intake_roles_only(self) -> None:
        # Care work is intake, not clinical: doctors and cashiers have their own
        # screens and must not be logging CSKH actions.
        assert INTAKE_ROLES == frozenset(
            {
                ClinicRole.CSKH,
                ClinicRole.RECEPTION,
                ClinicRole.MANAGEMENT,
                ClinicRole.TRUONG_CA,
            }
        )
        for role in (ClinicRole.DOCTOR, ClinicRole.CASHIER, ClinicRole.TKYK):
            assert role not in INTAKE_ROLES

    def test_the_working_day_is_the_clinic_s_not_utc(self) -> None:
        # 20:30 in Hanoi is already tomorrow in UTC. Filing the call on the UTC
        # date would push every evening call onto the next working day and make
        # the overdue-recall list wrong.
        evening = datetime(2026, 7, 30, 20, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        assert clinic_today(evening) == "2026-07-30"
        assert evening.astimezone(timezone.utc).date().isoformat() == "2026-07-30"

        late = datetime(2026, 7, 30, 23, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        assert clinic_today(late) == "2026-07-30"
        # ... which UTC would have called the 30th too, but an early-hours call
        # is where the two really diverge:
        early = datetime(2026, 7, 31, 6, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        assert clinic_today(early) == "2026-07-31"
        assert early.astimezone(timezone.utc).date().isoformat() == "2026-07-30"

    def test_manual_refs_do_not_collide(self) -> None:
        # source_ref is UNIQUE NOT NULL and shared with the import pipeline, so
        # two clicks in the same millisecond must not produce the same key.
        refs = {manual_source_ref() for _ in range(500)}
        assert len(refs) == 500
        assert all(r.startswith("dash-manual-") for r in refs)


class TestServiceLog:
    def test_the_two_screens_keep_their_own_vocabularies(self) -> None:
        # One table, two status languages, because each screen filters to its
        # own rows. Unifying them is a data migration plus two UI changes — not
        # something a port should do silently, which would blank whichever
        # worklist was not updated.
        assert (TASK_WAITING, TASK_IN_PROGRESS, TASK_DONE) == (
            "Chờ làm",
            "Đang làm",
            "Hoàn tất",
        )
        assert (QUEUE_WAITING, QUEUE_IN_PROGRESS, QUEUE_DONE, QUEUE_CANCELLED) == (
            "WAITING",
            "IN_PROGRESS",
            "DONE",
            "CANCELLED",
        )

    def test_starting_stamps_a_start_and_finishing_stamps_a_finish(self) -> None:
        assert task_patch("start", None) == {
            "started_at": "now",
            "status": TASK_IN_PROGRESS,
        }
        finished = task_patch("finish", "  kết quả  ")
        assert finished["finished_at"] == "now"
        assert finished["status"] == TASK_DONE
        assert finished["result_text"] == "kết quả"

    def test_a_blank_result_is_stored_as_nothing(self) -> None:
        assert task_patch("finish", "   ")["result_text"] is None

    def test_cancelling_does_not_erase_what_already_happened(self) -> None:
        # A cancelled scan that was already started still started; wiping the
        # timestamps would lose that.
        patch = queue_patch("cancel")
        assert patch == {"status": QUEUE_CANCELLED}
        assert "started_at" not in patch and "finished_at" not in patch

    @pytest.mark.parametrize("action", ["", "START", "done", "delete"])
    def test_unknown_actions_are_refused(self, action: str) -> None:
        with pytest.raises(ValidationError):
            task_patch(action, None)
        with pytest.raises(ValidationError):
            queue_patch(action)

    def test_lab_milestones_are_three_independent_timestamps(self) -> None:
        # A single status cannot express "sample taken and result back, but a
        # second sample not yet sent", which is why these are separate columns.
        assert MILESTONE_COLUMN == {
            "sample": "started_at",
            "sendlab": "sent_to_lab_at",
            "result": "finished_at",
        }
        assert len(set(MILESTONE_COLUMN.values())) == 3

    def test_the_sono_queue_belongs_to_the_ultrasound_nurse(self) -> None:
        assert SONO_ROLES == frozenset(
            {ClinicRole.NURSE_ULTRASOUND, ClinicRole.MANAGEMENT}
        )
        assert ClinicRole.RECEPTION not in SONO_ROLES

    def test_source_refs_do_not_collide(self) -> None:
        refs = {source_ref("api-svc") for _ in range(500)}
        assert len(refs) == 500


class TestRosterRules:
    def test_the_week_is_derived_not_trusted(self) -> None:
        # The schedule form keeps the previously viewed week in state, so a
        # client-supplied week_start filed shifts under the wrong week.
        for day in range(30, 32):
            assert week_start_of(date(2026, 7, day)) == date(2026, 7, 27)
        assert week_start_of(date(2026, 7, 27)) == date(2026, 7, 27)  # Monday
        assert week_start_of(date(2026, 8, 2)) == date(2026, 7, 27)  # Sunday

    def test_approving_is_management_only(self) -> None:
        assert ROSTER_ADMIN_ROLES == frozenset({ClinicRole.MANAGEMENT})

    def test_everyone_may_sign_themselves_up(self) -> None:
        # The service ignores a client-supplied staff_id unless the caller is
        # management, so the endpoint itself does not need to be narrow.
        assert ROSTER_ROLES == frozenset(ClinicRole)


class TestPriceParsing:
    @pytest.mark.parametrize(
        ("raw", "expected"), [("150000", 150000), (99.6, 100), (0, 0), ("0", 0)]
    )
    def test_prices_are_whole_dong(self, raw: object, expected: int) -> None:
        assert parse_price(raw) == expected

    @pytest.mark.parametrize("raw", [None, ""])
    def test_blank_means_not_priced_yet(self, raw: object) -> None:
        # Distinct from zero, which is a real price of nothing.
        assert parse_price(raw) is None

    @pytest.mark.parametrize("raw", [-1, "-5", "abc", float("inf"), float("nan"), True])
    def test_nonsense_is_refused_rather_than_coerced(self, raw: object) -> None:
        with pytest.raises(ValidationError):
            parse_price(raw)

    def test_only_the_cash_desk_maintains_prices(self) -> None:
        assert ClinicRole.DOCTOR not in PRICE_ROLES
        assert (
            ClinicRole.CASHIER in PRICE_ROLES and ClinicRole.MANAGEMENT in PRICE_ROLES
        )


class TestPatientEditRules:
    def test_editing_is_wider_than_creating(self) -> None:
        # A doctor who spots a wrong date of birth should not have to find a
        # receptionist; only intake may CREATE a patient.
        from clinicai.api.v1.patients import _PATIENT_EDIT_GUARD

        assert ClinicRole.DOCTOR in _PATIENT_EDIT_GUARD.allowed_roles

    @pytest.mark.parametrize(
        "phone", ["0901234567", "0281234567", "0321234567", "0791234567"]
    )
    def test_valid_vietnamese_numbers_pass(self, phone: str) -> None:
        validate_phone(phone, "SĐT")

    @pytest.mark.parametrize(
        "phone", ["901234567", "09012345678", "0101234567", "+84901234567", "abc"]
    )
    def test_malformed_numbers_are_refused_server_side(self, phone: str) -> None:
        # The form is not the only caller.
        with pytest.raises(CoreValidationError):
            validate_phone(phone, "SĐT")

    @pytest.mark.parametrize("phone", [None, "", "  "])
    def test_a_blank_number_is_allowed(self, phone: str | None) -> None:
        validate_phone(phone, "SĐT")


class _StubPool:
    """Minimal asyncpg pool stand-in: one connection, canned answers."""

    def __init__(self, *results: object) -> None:
        self.conn = _StubConn(*results)

    def acquire(self) -> "_StubPool":
        return self

    async def __aenter__(self) -> "_StubConn":
        return self.conn

    async def __aexit__(self, *_: object) -> None:
        return None


class _StubConn:
    def __init__(self, *results: object) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchval(self, sql: str, *args: object) -> object:
        self.calls.append((sql, args))
        return self._results.pop(0) if self._results else None

    async def fetchrow(self, sql: str, *args: object) -> object:
        self.calls.append((sql, args))
        return self._results.pop(0) if self._results else None

    async def execute(self, sql: str, *args: object) -> None:
        self.calls.append((sql, args))

    def transaction(self) -> "_StubConn":
        return self

    async def __aenter__(self) -> "_StubConn":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _staff(role: ClinicRole, staff_id: str = "s1") -> StaffIdentity:
    return StaffIdentity(
        staff_id=staff_id,
        auth_user_id="u1",
        full_name="Người dùng",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
    )


class TestRosterAuthorisation:
    def test_a_nurse_signing_up_is_pending_and_cannot_name_anybody(self) -> None:
        # The client's staff_id is not validated — it is never read. There is
        # nothing to spoof when the value is ignored.
        pool = _StubPool("r1")
        asyncio.run(
            RosterService(pool).add_shift(
                work_date=date(2026, 7, 30),
                station="LICH_KHAM",
                shift="SANG",
                identity=_staff(ClinicRole.NURSE_ULTRASOUND, "nurse-1"),
                staff_id="somebody-else",
                staff_name="Ai đó",
            )
        )
        args = pool.conn.calls[0][1]
        assert "somebody-else" not in args
        assert "nurse-1" in args
        assert "PENDING" in args

    def test_management_may_schedule_somebody_and_it_is_approved(self) -> None:
        pool = _StubPool("r2")
        asyncio.run(
            RosterService(pool).add_shift(
                work_date=date(2026, 7, 30),
                station="LICH_KHAM",
                shift="CHIEU",
                identity=_staff(ClinicRole.MANAGEMENT, "mgr-1"),
                staff_id="doctor-9",
                staff_name="BS Chín",
            )
        )
        args = pool.conn.calls[0][1]
        assert "doctor-9" in args and "APPROVED" in args

    def test_an_unknown_shift_falls_back_to_full_day(self) -> None:
        pool = _StubPool("r3")
        asyncio.run(
            RosterService(pool).add_shift(
                work_date=date(2026, 7, 30),
                station="LICH_KHAM",
                shift="TOI",
                identity=_staff(ClinicRole.RECEPTION),
            )
        )
        assert "FULL" in pool.conn.calls[0][1]

    def test_only_management_approves(self) -> None:
        with pytest.raises(SafetyGateError):
            asyncio.run(
                RosterService(_StubPool()).decide(
                    roster_id="r1",
                    decision="approve",
                    reason=None,
                    identity=_staff(ClinicRole.DOCTOR),
                )
            )

    def test_a_rejection_keeps_its_reason_and_an_approval_clears_it(self) -> None:
        pool = _StubPool("r1")
        asyncio.run(
            RosterService(pool).decide(
                roster_id="r1",
                decision="reject",
                reason="  trùng ca  ",
                identity=_staff(ClinicRole.MANAGEMENT),
            )
        )
        assert "trùng ca" in pool.conn.calls[0][1]

        pool = _StubPool("r1")
        asyncio.run(
            RosterService(pool).decide(
                roster_id="r1",
                decision="approve",
                reason="ignored",
                identity=_staff(ClinicRole.MANAGEMENT),
            )
        )
        assert "ignored" not in pool.conn.calls[0][1]

    def test_staff_may_only_remove_their_own_shift(self) -> None:
        pool = _StubPool({"staff_id": "someone-else"})
        with pytest.raises(SafetyGateError):
            asyncio.run(
                RosterService(pool).remove(
                    roster_id="r1", identity=_staff(ClinicRole.DOCTOR, "me")
                )
            )

    def test_management_may_remove_anybody_s(self) -> None:
        pool = _StubPool({"staff_id": "someone-else"})
        asyncio.run(
            RosterService(pool).remove(
                roster_id="r1", identity=_staff(ClinicRole.MANAGEMENT, "mgr")
            )
        )
        assert any("DELETE" in sql for sql, _ in pool.conn.calls)
