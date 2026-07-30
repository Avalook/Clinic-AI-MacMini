"""Unit tests for the clinical rules moved out of the dashboard (W5).

The DB paths are covered by integration tests; what is pinned here is the part
that would change a patient's record if it were wrong — link normalisation, how
measurements merge, and which roles each gate admits.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from clinicai.api.identity import ClinicRole
from clinicai.api.v1.routers.lab import _ORDER_GUARD, _RESULT_GUARD
from clinicai.api.v1.routers.ultrasound import _SONOGRAPHER_GUARD
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
from clinicai.services.lab_order_service import normalize_link
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
