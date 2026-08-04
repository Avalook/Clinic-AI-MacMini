"""Điều kiện đóng lượt khám ở quầy Lễ tân.

Đây là chỗ quyết định một bệnh nhân có được cho về hay không, nên mọi tổ hợp
phải thử được mà không cần một lượt khám thật.

Notion §2 Lễ tân — Check-out liệt kê bốn thứ phải đối soát: dịch vụ chưa xong,
kết quả đang chờ, khoản chưa thu, và *"không cho đóng lượt khi bệnh nhân vẫn
đang được xử lý tại một phòng"*.
"""

from __future__ import annotations

from typing import Any

from clinicai.services.checkout_service import CLOSE_NODE, build_blockers


def _row(**over: Any) -> dict[str, Any]:
    """Một lượt khám SẠCH: đã thu tiền dịch vụ, không đơn thuốc, đã rời phòng."""
    base: dict[str, Any] = {
        "svc_open": 0,
        "lab_pending": 0,
        "paid_service": True,
        "paid_drug": False,
        "has_drug": False,
        "current_node_code": CLOSE_NODE,
        "room_name": None,
    }
    base.update(over)
    return base


def _types(row: dict[str, Any]) -> set[str]:
    return {b["type"] for b in build_blockers(row)}


class TestAcleanVisitCloses:
    def test_nothing_outstanding_means_no_blockers(self) -> None:
        assert build_blockers(_row()) == []


class TestTheFourThingsNotionAsksFor:
    def test_unfinished_services_block(self) -> None:
        assert "service_open" in _types(_row(svc_open=2))

    def test_pending_lab_results_block(self) -> None:
        assert "lab_pending" in _types(_row(lab_pending=1))

    def test_unpaid_service_fee_blocks(self) -> None:
        assert "unpaid_service" in _types(_row(paid_service=False))

    def test_a_patient_still_in_a_room_blocks(self) -> None:
        """*"Không cho đóng lượt khi bệnh nhân vẫn đang được xử lý tại một
        phòng"* — người còn đang siêu âm thì chưa thể ra về."""
        assert "still_at_station" in _types(
            _row(current_node_code="DICHVU-SIEUAM", room_name="Siêu âm SA1")
        )

    def test_standing_at_the_checkout_step_is_not_a_blocker(self) -> None:
        """Bước "Đóng lượt khám" chính là chỗ đang đứng — không tự chặn mình."""
        assert "still_at_station" not in _types(
            _row(current_node_code=CLOSE_NODE, room_name="Thu ngân")
        )


class TestDrugPaymentOnlyWhenThereIsAPrescription:
    def test_a_prescription_that_is_unpaid_blocks(self) -> None:
        assert "unpaid_drug" in _types(_row(has_drug=True, paid_drug=False))

    def test_a_prescription_already_paid_does_not_block(self) -> None:
        assert "unpaid_drug" not in _types(_row(has_drug=True, paid_drug=True))

    def test_no_prescription_means_no_drug_payment_is_expected(self) -> None:
        """Đòi thu tiền thuốc ở MỌI lượt sẽ chặn phần lớn bệnh nhân — những
        người không được kê thuốc gì cả."""
        assert "unpaid_drug" not in _types(_row(has_drug=False, paid_drug=False))


class TestTheMessagesAreForPeople:
    def test_a_blocker_says_what_to_do_not_which_table(self) -> None:
        """*"Lý do phải hiển thị bằng câu dễ hiểu… không hiển thị mã hoặc tên
        kỹ thuật."*"""
        msgs = [b["message"] for b in build_blockers(_row(svc_open=2, lab_pending=1))]
        assert any("dịch vụ" in m for m in msgs)
        assert not any("service_log" in m or "status" in m for m in msgs)

    def test_the_count_appears_in_the_sentence(self) -> None:
        msg = build_blockers(_row(svc_open=3))[0]["message"]
        assert "3" in msg

    def test_every_outstanding_thing_is_listed_not_just_the_first(self) -> None:
        """Nói một vướng mắc rồi im là bắt Lễ tân sửa xong lại bấm, lại bị chặn.

        Notion đòi *"hiển thị danh sách việc còn thiếu"* — số nhiều.
        """
        blockers = build_blockers(
            _row(
                svc_open=1,
                lab_pending=1,
                paid_service=False,
                has_drug=True,
                paid_drug=False,
                current_node_code="DICHVU-SIEUAM",
                room_name="Siêu âm SA1",
            )
        )
        assert len(blockers) == 5
