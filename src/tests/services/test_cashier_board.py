"""Bảng thu ngân — luật ghép hoá đơn, sau khi chuyển từ TSX xuống backend.

Đây là màn TÍNH TIỀN. Ghép thiếu một dòng là thu thiếu tiền và không ai biết,
vì màn hình vẫn hiện đủ các mục khác — đúng chuyện đã xảy ra với xét nghiệm
(xem TestLabResultsFinallyReachTheBill).
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.identity import ClinicRole
from clinicai.services.cashier_board_service import (
    CASHIER_ROLES,
    build_rows,
    clean_name,
    norm_name,
)


class TestNameNormalisation:
    """Tên dán từ Zalo hay kèm đường link. Không bỏ ra thì không khớp bảng giá."""

    def test_a_link_glued_to_the_name_is_stripped(self) -> None:
        assert norm_name("Siêu âm (https://notion.so/abc)") == "siêu âm"

    def test_an_unclosed_link_is_stripped_too(self) -> None:
        """Dán hụt mất dấu đóng ngoặc là chuyện thường."""
        assert norm_name("Siêu âm (https://notion.so/abc") == "siêu âm"

    def test_case_and_spacing_do_not_matter_for_lookup(self) -> None:
        assert norm_name("  SIÊU   ÂM  ") == norm_name("siêu âm")

    def test_the_displayed_name_keeps_its_capitals(self) -> None:
        """`clean_name` là tên HIỆN RA, `norm_name` là khoá TRA CỨU. Trộn hai
        cái thì hoá đơn in ra toàn chữ thường."""
        assert clean_name("Siêu âm Đầu dò (https://x.co/1)") == "Siêu âm Đầu dò"

    def test_nothing_in_gives_nothing_out(self) -> None:
        assert norm_name(None) == ""
        assert clean_name(None) == ""


def _raw(**over: object) -> dict[str, Any]:
    base = {
        "visits": [
            {
                "visit_id": "v1",
                "clinic_patient_id": "p1",
                "appointment_id": "a1",
                "full_name": "Nguyễn Thị A",
                "patient_code": "BN-1",
                "phone_primary": "090",
                "appt_status": "COMPLETED",
                "exam_service_name": "Khám phụ khoa",
            }
        ],
        "labs": [],
        "services": [],
        "drugs": [],
        "prices": [
            {"name": "Khám phụ khoa", "group": "dich_vu", "unit_price": 300000},
            {"name": "Siêu âm", "group": "dich_vu", "unit_price": 550000},
            {"name": "Paracetamol", "group": "thuoc", "unit_price": 5000},
        ],
        "paid": [],
    }
    base.update(over)
    return base


class TestBuildingTheBill:
    def test_the_consultation_fee_comes_first(self) -> None:
        """Tiền khám đứng đầu hoá đơn — thu ngân đọc từ trên xuống."""
        out = build_rows(_raw(), want_svc=True, want_rx=True)
        assert out["items"][0]["services"][0]["name"] == "Khám phụ khoa"
        assert out["items"][0]["services"][0]["price"] == 300000

    def test_a_price_that_does_not_exist_is_none_not_zero(self) -> None:
        """0đ và "chưa khai giá" là hai chuyện khác nhau.

        Trả 0 thì thu ngân thu 0đ cho một dịch vụ có tính tiền; trả None thì ô
        giá trống và người ta hỏi lại.
        """
        raw = _raw(prices=[])
        out = build_rows(raw, want_svc=True, want_rx=True)
        assert out["items"][0]["services"][0]["price"] is None

    def test_prices_match_through_the_link_noise(self) -> None:
        """Đúng cái làm giá biến mất trên màn thật."""
        raw = _raw(
            services=[
                {
                    "id": "s1",
                    "clinic_patient_id": "p1",
                    "name": "Siêu âm (https://notion.so/x)",
                }
            ]
        )
        out = build_rows(raw, want_svc=True, want_rx=True)
        sieu_am = [s for s in out["items"][0]["services"] if "Siêu âm" in s["name"]]
        assert sieu_am and sieu_am[0]["price"] == 550000

    def test_drug_mode_off_means_no_drugs(self) -> None:
        """CASHIER_DV không được thấy ô thuốc — hai quầy, hai người thu."""
        raw = _raw(
            drugs=[
                {
                    "id": "d1",
                    "visit_id": "v1",
                    "name": "Paracetamol",
                    "quantity": "10",
                    "dosage": "1v x 2",
                }
            ]
        )
        assert build_rows(raw, want_svc=True, want_rx=False)["items"][0]["drugs"] == []
        assert (
            build_rows(raw, want_svc=True, want_rx=True)["items"][0]["drugs"][0][
                "price"
            ]
            == 5000
        )

    def test_service_mode_off_means_no_services(self) -> None:
        assert (
            build_rows(_raw(), want_svc=False, want_rx=True)["items"][0]["services"]
            == []
        )

    def test_a_nameless_line_is_dropped_not_shown_blank(self) -> None:
        """Một dòng trống trên hoá đơn là thu ngân phải đoán nó là gì."""
        raw = _raw(services=[{"id": "s1", "clinic_patient_id": "p1", "name": "  "}])
        assert (
            len(build_rows(raw, want_svc=True, want_rx=True)["items"][0]["services"])
            == 1
        )  # chỉ còn tiền khám


class TestLabResultsFinallyReachTheBill:
    """LỖI TIỀN BẠC CÓ SẴN, tìm ra ngày 04/08/2026.

    Truy vấn cũ hỏi PostgREST `lab_result?select=id,...`, nhưng cột khoá tên là
    `lab_result_id`. PostgREST trả lỗi 42703 và TSX nuốt bằng `?? []` — nên XÉT
    NGHIỆM CHƯA BAO GIỜ vào hoá đơn thu ngân. Màn hình vẫn hiện tiền khám và
    thuốc nên trông hoàn toàn bình thường; chỉ có tiền là thiếu.
    """

    def test_lab_results_appear_as_billable_lines(self) -> None:
        raw = _raw(labs=[{"id": "l1", "appointment_id": "a1", "test_name": "Siêu âm"}])
        names = [
            s["name"]
            for s in build_rows(raw, want_svc=True, want_rx=True)["items"][0][
                "services"
            ]
        ]
        assert "Siêu âm" in names

    def test_a_lab_result_of_another_appointment_does_not_leak_in(self) -> None:
        """Ghép sai lịch hẹn là tính tiền của người này cho người khác."""
        raw = _raw(
            labs=[{"id": "l1", "appointment_id": "a-khac", "test_name": "Siêu âm"}]
        )
        names = [
            s["name"]
            for s in build_rows(raw, want_svc=True, want_rx=True)["items"][0][
                "services"
            ]
        ]
        assert "Siêu âm" not in names


class TestWhatCountsAsAlreadyPaid:
    def test_only_the_two_real_kinds_seed_the_paid_state(self) -> None:
        raw = _raw(
            paid=[
                {"visit_id": "v1", "kind": "thuoc"},
                {"visit_id": "v1", "kind": "linh_tinh"},
            ]
        )
        out = build_rows(raw, want_svc=True, want_rx=True)
        assert out["paid"] == [{"visit_id": "v1", "kind": "thuoc"}]


class TestWhoMaySeeTheCashierBoard:
    @pytest.mark.parametrize("role", sorted(CASHIER_ROLES))
    def test_the_cashier_roles_and_management(self, role: ClinicRole) -> None:
        assert role in CASHIER_ROLES

    def test_a_doctor_is_not_a_cashier(self) -> None:
        """Bác sĩ khám, thu ngân thu. Trộn hai vai là bỏ mất một lớp đối soát."""
        assert ClinicRole.DOCTOR not in CASHIER_ROLES
        assert ClinicRole.CSKH not in CASHIER_ROLES
