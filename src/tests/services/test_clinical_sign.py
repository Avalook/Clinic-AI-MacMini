"""Luật ký bệnh án: ai được ký, và trường nào bắt buộc.

Ký bệnh án là HÀNH VI PHÁP LÝ. Sau khi ký, trigger `visit_finalized_block_update`
khoá hồ sơ theo TT13/2011/TT-BYT và đường ra duy nhất là đính chính. Không có
nút "bỏ ký", nên mọi thứ chặn TRƯỚC chữ ký phải đúng ngay lần đầu.

Vòng đời đầy đủ đã được chạy trên prod rồi rollback: thiếu trường → chặn · TKYK
ký → chặn · bác sĩ ký → SIGNED · sửa sau khi ký → trigger chặn · cho phép gửi →
RELEASED · đính chính bản đã gửi → AMENDED, phiên bản 2, thu hồi quyền gửi, tạo
việc cho CSKH.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.clinical_sign_service import (
    REQUIRED_SOAP,
    SIGNING_ROLES,
    _assert_doctor,
    missing_fields,
)


def _identity(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        auth_user_id="00000000-0000-0000-0000-000000000000",
        staff_id="00000000-0000-0000-0000-000000000000",
        full_name="x",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="00000000-0000-0000-0000-000000000000",
        location_name="x",
    )


class TestOnlyDoctorsSign:
    @pytest.mark.parametrize("role", list(SIGNING_ROLES))
    def test_a_doctor_may_sign(self, role: ClinicRole) -> None:
        _assert_doctor(_identity(role))

    def test_the_medical_secretary_may_not_sign(self) -> None:
        """TKYK nhập hộ bệnh án được (Notion cho phép), nhưng KHÔNG ký.

        Người ký là người chịu trách nhiệm chuyên môn. Để TKYK ký là ghi sai
        người vào một chữ ký có giá trị pháp lý.
        """
        with pytest.raises(ValidationError, match="Chỉ bác sĩ"):
            _assert_doctor(_identity(ClinicRole.TKYK))

    def test_management_may_not_sign(self) -> None:
        """Quyết định của Quang: *"chỉ bác sĩ được ký vì bác sĩ làm mà"*.

        Quản lý có mọi quyền hành chính khác — nhưng ký bệnh án không phải
        quyền hành chính.
        """
        with pytest.raises(ValidationError, match="Chỉ bác sĩ"):
            _assert_doctor(_identity(ClinicRole.MANAGEMENT))

    def test_a_nurse_may_not_sign(self) -> None:
        with pytest.raises(ValidationError, match="Chỉ bác sĩ"):
            _assert_doctor(_identity(ClinicRole.NURSE_ULTRASOUND))


def _row(**over: Any) -> dict[str, Any]:
    """Hồ sơ ĐẦY ĐỦ; mỗi test làm rỗng đúng một mục."""
    base = {k: json.dumps({"x": "có nội dung"}) for k in REQUIRED_SOAP}
    base.update(over)
    return base


class TestRequiredFieldsBeforeSigning:
    def test_a_complete_record_has_nothing_missing(self) -> None:
        assert missing_fields(_row()) == []

    @pytest.mark.parametrize("field,label", list(REQUIRED_SOAP.items()))
    def test_each_required_field_is_checked(self, field: str, label: str) -> None:
        assert missing_fields(_row(**{field: None})) == [label]

    def test_an_empty_json_object_counts_as_missing(self) -> None:
        """CÁC CỘT SOAP LÀ `jsonb`, KHÔNG PHẢI TEXT — và đây là cái bẫy.

        Kiểm bằng `str(value).strip()` sẽ coi `{}` là ĐÃ ĐIỀN, vì chuỗi "{}"
        không rỗng. Nghĩa là một hồ sơ trống rỗng vẫn ký được, và cái chốt chặn
        duy nhất trước chữ ký sẽ luôn nói "đủ rồi".
        """
        assert missing_fields(_row(soap_assessment="{}")) == ["Chẩn đoán"]

    def test_a_json_object_with_only_blank_values_counts_as_missing(self) -> None:
        """Bác sĩ mở form rồi đóng lại: khoá có, giá trị rỗng."""
        assert missing_fields(
            _row(soap_plan=json.dumps({"xu_tri": "   "}))
        ) == ["Hướng xử trí"]

    def test_an_empty_list_counts_as_missing(self) -> None:
        assert missing_fields(_row(soap_objective="[]")) == ["Khám lâm sàng"]

    def test_a_dict_that_asyncpg_already_decoded_works_too(self) -> None:
        """Không phụ thuộc việc asyncpg trả jsonb dạng chuỗi hay dạng dict —
        hai môi trường có thể cấu hình codec khác nhau."""
        assert missing_fields(_row(soap_assessment={"chan_doan": ""})) == [
            "Chẩn đoán"
        ]
        assert missing_fields(_row(soap_assessment={"chan_doan": "viêm"})) == []

    def test_every_missing_field_is_listed_not_just_the_first(self) -> None:
        """Notion §6: *"liệt kê nội dung còn thiếu"*.

        Nói một mục rồi im là bắt bác sĩ điền xong lại bấm, lại bị chặn.
        """
        assert len(missing_fields({})) == len(REQUIRED_SOAP)

    def test_the_labels_are_what_a_doctor_reads(self) -> None:
        """"Chẩn đoán", không phải "soap_assessment" — bác sĩ đang đứng trước
        một cái form, không phải trước một cái bảng."""
        for label in missing_fields({}):
            assert not label.startswith("soap_")
