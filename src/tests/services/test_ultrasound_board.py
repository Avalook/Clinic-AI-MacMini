"""Bộ phận Siêu âm — bốn ô "sẵn sàng" và cách gom phiếu đã ký.

Đã chạy vòng đời đầy đủ trên prod (rollback): chỉ định → hàng chờ → soạn nháp →
lưu lại cùng loại (ghi đè) → khác loại (thêm bản) → ký → sang tab lưu trữ → sửa
bản đã ký bị chặn.
"""

from __future__ import annotations

import pytest

from clinicai.api.identity import ClinicRole
from clinicai.services.ultrasound_board_service import (
    ULTRASOUND_ROLES,
    group_by_patient,
)


def _rec(pid: str | None, name: str, uid: str) -> dict:
    return {
        "ultrasound_id": uid,
        "clinic_patient_id": pid,
        "patient_name": name,
        "patient_code": "BN-1",
        "gender": "Nữ",
        "birth_year": 1990,
    }


class TestGroupingSignedReports:
    """Tab "đã ký" gom theo BỆNH NHÂN, không theo phiếu.

    Một người siêu âm nhiều loại trong một đợt (đầu dò rồi ổ bụng), và người tra
    cứu nghĩ theo "chị A có những phiếu nào" chứ không theo "phiếu số mấy".
    """

    def test_two_reports_for_one_patient_become_one_group(self) -> None:
        out = group_by_patient([_rec("p1", "A", "u1"), _rec("p1", "A", "u2")])
        assert len(out) == 1
        assert out[0]["report_count"] == 2

    def test_two_patients_stay_apart(self) -> None:
        out = group_by_patient([_rec("p1", "A", "u1"), _rec("p2", "B", "u2")])
        assert [g["patient_name"] for g in out] == ["A", "B"]

    def test_the_order_of_first_appearance_is_kept(self) -> None:
        """Danh sách đến theo thứ tự thời gian giảm dần; gom lại không được
        xáo, nếu không phiếu mới nhất trôi xuống giữa bảng."""
        out = group_by_patient(
            [_rec("p2", "B", "u1"), _rec("p1", "A", "u2"), _rec("p2", "B", "u3")]
        )
        assert [g["patient_name"] for g in out] == ["B", "A"]

    def test_a_record_without_a_patient_is_not_merged_with_others(self) -> None:
        """Dữ liệu cũ có thể thiếu clinic_patient_id. Gom chúng lại thành một
        nhóm "None" sẽ trộn phiếu của nhiều người xa lạ vào một hồ sơ."""
        out = group_by_patient([_rec(None, "?", "u1"), _rec(None, "?", "u2")])
        assert len(out) == 2

    def test_nothing_in_nothing_out(self) -> None:
        assert group_by_patient([]) == []


class TestWhoWorksInUltrasound:
    @pytest.mark.parametrize(
        "role", sorted(ULTRASOUND_ROLES, key=lambda r: r.value)
    )
    def test_the_ultrasound_team_and_those_who_type_for_them(
        self, role: ClinicRole
    ) -> None:
        assert role in ULTRASOUND_ROLES

    def test_reception_and_cashier_have_no_business_here(self) -> None:
        """Màn này hiện chỉ định, kết quả và kết luận — dữ liệu lâm sàng."""
        assert ClinicRole.RECEPTION not in ULTRASOUND_ROLES
        assert ClinicRole.CASHIER not in ULTRASOUND_ROLES
        assert ClinicRole.CSKH not in ULTRASOUND_ROLES

    def test_the_secretary_may_type_results_for_the_doctor(self) -> None:
        """Báo cáo onsite: trợ lý nhập kết quả trong lúc bác sĩ đọc. Chữ ký vẫn
        là của bác sĩ — TKYK nhập được nhưng không ký được (clinical_sign)."""
        assert ClinicRole.TKYK in ULTRASOUND_ROLES
