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
from pydantic import ValidationError as PydanticValidationError

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.clinical_sign import AmendRequest
from clinicai.permissions.catalogue import PRESET, QUYEN
from clinicai.services.clinical_sign_service import (
    REQUIRED_SOAP,
    missing_fields,
)
from clinicai.services.dinh_chinh_don import (
    MAX_PRESCRIPTIONS_PER_AMENDMENT,
    prescription_fingerprint,
    validate_amendment_prescriptions,
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


class TestOnlyDoctorsFinalize:
    """Không còn "Ký bệnh án" (CORE-A, 23/09/2026) — mốc khoá là HOÀN TẤT KHÁM,
    quyền `clinical.consult.finalize` (khối `hoan_tat_kham`). Luật cũ giữ
    nguyên ý nghĩa: người khoá hồ sơ là người chịu trách nhiệm chuyên môn."""

    def test_a_doctor_may_finalize(self) -> None:
        assert "hoan_tat_kham" in PRESET["DOCTOR"]
        # Hàng rào chứng chỉ đã bỏ 24/09/2026 — khối được cấp là đủ.
        assert not QUYEN["clinical.consult.finalize"].chung_chi_lam_sang

    def test_ultrasound_doctor_may_finalize_since_full_lego(self) -> None:
        """Mở full lego (Tuyền 30/09/2026): bác sĩ siêu âm cũng có Hoàn tất khám.
        Trước đó chỉ ký kết quả siêu âm của mình."""
        assert "hoan_tat_kham" in PRESET["ULTRASOUND_DOCTOR"]

    def test_the_medical_secretary_may_finalize(self) -> None:
        """29/09/2026: ĐD/TKYK trọn quyền (Tuyền) — TKYK hoàn tất khám như bác sĩ
        (trước đây chỉ nhập hộ, không khoá)."""
        assert "hoan_tat_kham" in PRESET["TKYK"]

    def test_management_has_every_pack_including_finalize(self) -> None:
        """ĐỔI 24/09/2026 — Tuyền chốt (và xác nhận lại khi được hỏi về câu cũ
        của Quang "chỉ bác sĩ được ký"): quản lý có MỌI khối; hệ thống để MỞ,
        phòng khám khác cần chặt hơn thì chỉnh nhóm mẫu của họ sau."""
        assert "hoan_tat_kham" in PRESET["MANAGEMENT"]

    def test_a_nurse_may_finalize(self) -> None:
        """29/09/2026: ĐD/TKYK trọn quyền (Tuyền)."""
        assert "hoan_tat_kham" in PRESET["NURSE_ULTRASOUND"]

    @pytest.mark.parametrize("vai", ["RECEPTION", "CSKH"])
    def test_mo_full_lego_vai_khac_cung_hoan_tat_duoc(self, vai: str) -> None:
        """Mở full lego (Tuyền 30/09/2026): mọi vai nội bộ có Hoàn tất khám. Tên
        KÝ vẫn là bác sĩ thật — `test_mo_full_lego_db.py`."""
        assert "hoan_tat_kham" in PRESET.get(vai, [])

    def test_doi_tac_khong_hoan_tat(self) -> None:
        assert "hoan_tat_kham" not in PRESET["PARTNER"]


class TestPrescriptionFingerprint:
    def test_only_active_clinical_fields_affect_fingerprint(self) -> None:
        rows = [
            {
                "id": "10000000-0000-4000-8000-000000000001",
                "drug_name_raw": "Thuốc A",
                "quantity": "10 viên",
                "dosage_instructions": "Sáng 1",
                "caution": "Sau ăn",
                "drug_catalog_id": "catalog-a",
                "purchased_qty": 10,
                "dispensed_qty": 0,
            }
        ]
        expected = prescription_fingerprint(rows)
        allocation_only = [{**rows[0], "purchased_qty": 8, "dispensed_qty": 2}]
        assert prescription_fingerprint(allocation_only) == expected
        assert (
            prescription_fingerprint([{**rows[0], "dosage_instructions": "Tối 1"}])
            != expected
        )

    def test_order_does_not_affect_fingerprint(self) -> None:
        a = {
            "id": "10000000-0000-4000-8000-000000000001",
            "drug_name_raw": "A",
            "quantity": "1 viên",
            "dosage_instructions": None,
            "caution": None,
        }
        b = {**a, "id": "10000000-0000-4000-8000-000000000002", "drug_name_raw": "B"}
        assert prescription_fingerprint([a, b]) == prescription_fingerprint([b, a])


class TestAmendPrescriptionInput:
    @pytest.mark.parametrize(
        "item",
        [
            {"drug_name": 123},
            {"drug_name": "   "},
            {"drug_name": "A", "unknown": "x"},
            {"drug_name": "A", "dosage": {"bad": True}},
        ],
    )
    def test_router_rejects_malformed_rx_rows(self, item: dict[str, Any]) -> None:
        with pytest.raises(PydanticValidationError):
            AmendRequest(
                reason="Đính chính đơn",
                corrected={"don_thuoc": [item]},
                expected_revision=1,
                expected_rx="0" * 64,
            )

    def test_router_caps_rx_row_count(self) -> None:
        with pytest.raises(PydanticValidationError):
            AmendRequest(
                reason="Đính chính đơn",
                corrected={
                    "don_thuoc": [
                        {"drug_name": f"Thuốc {index}"}
                        for index in range(MAX_PRESCRIPTIONS_PER_AMENDMENT + 1)
                    ]
                },
                expected_revision=1,
                expected_rx="0" * 64,
            )

    def test_service_boundary_rejects_blank_instead_of_treating_as_removal(
        self,
    ) -> None:
        with pytest.raises(ValidationError, match="không được để trống"):
            validate_amendment_prescriptions([{"id": None, "drug_name": " "}])


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

    def test_phieu_chuyen_khoa_va_sinh_hieu_bu_cho_muc_trong(self) -> None:
        """17/09/2026: thư ký điền Lý do khám ở phiếu Nội tiết, điều dưỡng đo sinh
        hiệu ở màn riêng — nút ký không được báo thiếu những thứ đã có."""
        row = _row(
            soap_subjective=None,
            soap_objective=None,
            soap_assessment=None,
            soap_plan=None,
            phieu_chuyen_khoa=json.dumps(
                {
                    "ly_do": "Kinh nguyệt không đều",
                    "chan_doan": "PCOS",
                    "loi_dan": "Giảm cân",
                }
            ),
            co_sinh_hieu=True,
        )
        assert missing_fields(row) == []

    def test_ly_do_kham_o_benh_an_tinh_cho_muc_trieu_chung(self) -> None:
        row = _row(
            soap_subjective=None, chief_complaint_at_visit="Rối loạn kinh nguyệt"
        )
        assert missing_fields(row) == []

    # ── S0-8 (18/09/2026): phiếu Sản và HMVS không dùng khoá `chan_doan` ──────

    @staticmethod
    def _chi_phieu(phieu: dict[str, Any]) -> dict[str, Any]:
        return _row(
            soap_assessment=None, soap_plan=None, phieu_chuyen_khoa=json.dumps(phieu)
        )

    def test_san_khoa_ket_luan_va_loi_dan_du_de_ky(self) -> None:
        row = self._chi_phieu(
            {"ket_luan": "Thai 12 tuần ổn định", "loi_dan": "Tái khám"}
        )
        assert missing_fields(row) == []

    @pytest.mark.parametrize(
        "khoa",
        [
            "cd_nguyen_nhan_vo",
            "cd_nguyen_nhan_chong",
            "cd_nguyen_nhan_phoi_hop",
            "cd_phan_biet",
        ],
    )
    def test_hmvs_co_nguyen_nhan_la_du_chan_doan(self, khoa: str) -> None:
        row = self._chi_phieu({khoa: "Tắc vòi trứng hai bên", "pp_dieu_tri": ["IVF"]})
        assert missing_fields(row) == []

    def test_hmvs_dang_danh_gia_co_ke_hoach_tiep_theo_thi_ky_duoc(self) -> None:
        """Nguồn HMVS cho phép hồ sơ còn đang đánh giá — không ép phải có nguyên
        nhân, nhưng phải có kế hoạch tiếp theo (Target Contract 18/09)."""
        for ke_hoach in (
            {"tai_kham_ngay": "2026-10-01"},
            {"chu_ky_dieu_tri_tiep": "Chu kỳ sau làm HSG"},
            {"tai_kham_xn": ["AMH"]},
        ):
            row = self._chi_phieu(
                {"cd_trang_thai": "DANG_DANH_GIA", "pp_dieu_tri": ["OI"], **ke_hoach}
            )
            assert missing_fields(row) == [], ke_hoach

    def test_hmvs_dang_danh_gia_khong_ke_hoach_thi_bao_thieu_ro_rang(self) -> None:
        row = self._chi_phieu({"cd_trang_thai": "DANG_DANH_GIA", "pp_dieu_tri": ["OI"]})
        thieu = missing_fields(row)
        assert len(thieu) == 1 and "kế hoạch tiếp theo" in thieu[0]

    @pytest.mark.parametrize(
        "loi_ban",
        [{"cd_phan_biet": "Theo dõi PCOS"}, {"cd_nguyen_nhan_vo": "Chưa rõ"}],
    )
    def test_hmvs_dang_danh_gia_khong_lach_bang_o_chan_doan(
        self, loi_ban: dict[str, str]
    ) -> None:
        """Rà 18/09: có chữ ở ô chẩn đoán KHÔNG thay được kế hoạch tiếp theo khi
        bác sĩ đã chọn "đang tiếp tục đánh giá"."""
        row = self._chi_phieu(
            {"cd_trang_thai": "DANG_DANH_GIA", "pp_dieu_tri": ["OI"], **loi_ban}
        )
        thieu = missing_fields(row)
        assert len(thieu) == 1 and "kế hoạch tiếp theo" in thieu[0]

    @pytest.mark.parametrize(
        "xu_tri",
        [
            {"mht_quyet_dinh": "chong_chi_dinh"},
            {"mht_phac_do": "tibolon"},
            {"dieu_tri_ho_tro": ["canxi_vitd"]},
        ],
    )
    def test_noi_tiet_mht_hay_dieu_tri_ho_tro_la_huong_xu_tri(
        self, xu_tri: dict[str, object]
    ) -> None:
        row = self._chi_phieu(
            {"ly_do": "Bốc hoả", "chan_doan": "Hội chứng mãn kinh", **xu_tri}
        )
        assert missing_fields(row) == []

    def test_hmvs_chi_tien_luong_hay_phan_loai_khong_phai_chan_doan(self) -> None:
        row = self._chi_phieu(
            {
                "cd_tien_luong": "Tốt",
                "cd_phan_loai": "Nguyên phát",
                "pp_dieu_tri": ["OI"],
            }
        )
        assert missing_fields(row) == [REQUIRED_SOAP["soap_assessment"]]

    def test_phieu_rong_khong_bu_duoc(self) -> None:
        row = _row(soap_subjective=None, phieu_chuyen_khoa=json.dumps({"ly_do": " "}))
        assert missing_fields(row) == [REQUIRED_SOAP["soap_subjective"]]

    def test_an_empty_json_object_counts_as_missing(self) -> None:
        """CÁC CỘT SOAP LÀ `jsonb`, KHÔNG PHẢI TEXT — và đây là cái bẫy.

        Kiểm bằng `str(value).strip()` sẽ coi `{}` là ĐÃ ĐIỀN, vì chuỗi "{}"
        không rỗng. Nghĩa là một hồ sơ trống rỗng vẫn ký được, và cái chốt chặn
        duy nhất trước chữ ký sẽ luôn nói "đủ rồi".
        """
        assert missing_fields(_row(soap_assessment="{}")) == ["Chẩn đoán"]

    def test_a_json_object_with_only_blank_values_counts_as_missing(self) -> None:
        """Bác sĩ mở form rồi đóng lại: khoá có, giá trị rỗng."""
        assert missing_fields(_row(soap_plan=json.dumps({"xu_tri": "   "}))) == [
            "Hướng xử trí"
        ]

    def test_an_empty_list_counts_as_missing(self) -> None:
        assert missing_fields(_row(soap_objective="[]")) == ["Khám lâm sàng"]

    def test_a_dict_that_asyncpg_already_decoded_works_too(self) -> None:
        """Không phụ thuộc việc asyncpg trả jsonb dạng chuỗi hay dạng dict —
        hai môi trường có thể cấu hình codec khác nhau."""
        assert missing_fields(_row(soap_assessment={"chan_doan": ""})) == ["Chẩn đoán"]
        assert missing_fields(_row(soap_assessment={"chan_doan": "viêm"})) == []

    def test_every_missing_field_is_listed_not_just_the_first(self) -> None:
        """Notion §6: *"liệt kê nội dung còn thiếu"*.

        Nói một mục rồi im là bắt bác sĩ điền xong lại bấm, lại bị chặn.
        """
        assert len(missing_fields({})) == len(REQUIRED_SOAP)

    def test_the_labels_are_what_a_doctor_reads(self) -> None:
        """ "Chẩn đoán", không phải "soap_assessment" — bác sĩ đang đứng trước
        một cái form, không phải trước một cái bảng."""
        for label in missing_fields({}):
            assert not label.startswith("soap_")


class TestRenotifyTaskCarriesItsVisit:
    """Việc "thông báo lại kết quả" phải GẮN với lượt khám nào.

    Màn CSKH đọc `cskh_action.visit_link_raw` để tra xem bác sĩ đã cho phép gửi
    lại chưa. Không có khoá đó thì cái chốt hai bước im lặng bỏ qua đúng tình
    huống nguy hiểm nhất: một kết quả ĐÃ GỬI vừa bị đính chính.

    Kiểm trên prod (đã rollback): INSERT này ghép được với v_clinical_status và
    trả về clinical_state <> 'RELEASED' → CSKH bị chặn.
    """

    @pytest.mark.asyncio
    async def test_the_insert_records_the_visit_id(self) -> None:
        from clinicai.services.clinical_sign_service import _create_renotify_task

        visit = "11111111-1111-4111-8111-111111111111"
        seen: list[tuple[str, tuple[Any, ...]]] = []

        class Conn:
            async def fetchrow(self, *_: Any) -> dict[str, Any]:
                return {"clinic_patient_id": "22222222-2222-4222-8222-222222222222"}

            async def execute(self, sql: str, *args: Any) -> None:
                seen.append((sql, args))

        await _create_renotify_task(
            Conn(),
            _identity(ClinicRole.DOCTOR),
            visit,
            "sai chẩn đoán",
        )

        # HAI CÂU GHI, CÓ CHỦ Ý (08/08/2026).
        #
        # `hen_goi_lai` là bảng mà màn CSKH mới THẬT SỰ đọc (qua
        # v_trang_thai_cskh). Trước khi thêm nó, việc "gọi lại báo đính chính"
        # chỉ nằm ở `cskh_action` — bảng view không đọc — nên nó vô hình, đúng
        # với loại việc mà bỏ sót thì bệnh nhân đang cầm một tờ kết quả sai.
        #
        # `cskh_action` giữ lại để nhật ký nhập khẩu cũ đọc được liên tục.
        assert len(seen) == 2, "phải ghi cả việc CSKH mới lẫn nhật ký cũ"

        sql_viec, args_viec = seen[0]
        assert "hen_goi_lai" in sql_viec, (
            "việc đính chính không vào bảng mà màn CSKH đọc — nó sẽ vô hình"
        )
        assert "đính chính" in " ".join(str(a) for a in args_viec)

        sql, args = seen[1]
        assert "visit_link_raw" in sql
        assert visit in args, "việc CSKH không mang theo lượt khám của nó"
