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


# ── Đóng lượt khi khách về giữa chừng ───────────────────────────────────────
class TestDongLuotKhamDo:
    """Khách đang khám thì có việc phải về.

    Trước đây tình huống này không có chỗ nào ghi, nên cách duy nhất là HUỶ LỊCH
    HẸN — và hồ sơ trông như người ấy chưa từng đến: mất dấu vết họ đã lấy số,
    đã đo sinh hiệu, đã được chỉ định dịch vụ.
    """

    def _service(self) -> Any:
        from unittest.mock import AsyncMock, MagicMock

        from clinicai.services.checkout_service import CheckoutService

        pool = MagicMock()
        conn = AsyncMock()
        acquire = AsyncMock()
        acquire.__aenter__.return_value = conn
        pool.acquire = MagicMock(return_value=acquire)
        # `conn.transaction()` phải trả về một context manager BẤT ĐỒNG BỘ.
        # AsyncMock trả coroutine, và coroutine thì không dùng được với
        # `async with` — lỗi hiện ra ở tận dòng UPDATE, xa chỗ sai.
        tx = AsyncMock()
        tx.__aenter__.return_value = None
        conn.transaction = MagicMock(return_value=tx)
        return CheckoutService(pool), conn

    def test_khong_co_ly_do_thi_khong_dong_duoc_du_sach_vuong_mac(self) -> None:
        """Một lượt dở không lý do là một người bệnh mà CSKH không biết phải gọi
        lại để nói gì. Ràng buộc ở database cũng chặn, nhưng phải từ chối được
        bằng tiếng người TRƯỚC khi chạm database."""
        import asyncio
        from unittest.mock import AsyncMock

        import pytest

        from clinicai.api.exceptions import ValidationError

        svc, _ = self._service()
        svc.readiness = AsyncMock(
            return_value={"already_closed": False, "blockers": []}
        )

        with pytest.raises(ValidationError, match="vì sao"):
            asyncio.run(
                svc.close(
                    identity=_identity(),
                    visit_id="11111111-1111-4111-8111-111111111111",
                    incomplete=True,
                )
            )

    def test_kham_do_khong_can_ly_do_ngoai_le_du_con_vuong_mac(self) -> None:
        """Khách về giữa chừng thì ĐƯƠNG NHIÊN còn việc chưa xong — đòi thêm một
        "lý do ngoại lệ" nữa là bắt Lễ tân gõ hai lần cho cùng một sự việc."""
        import asyncio
        from unittest.mock import AsyncMock

        svc, _ = self._service()
        svc.readiness = AsyncMock(
            return_value={
                "already_closed": False,
                "blockers": [{"type": "service_open", "message": "Còn 2 dịch vụ"}],
            }
        )

        ket = asyncio.run(
            svc.close(
                identity=_identity(),
                visit_id="11111111-1111-4111-8111-111111111111",
                incomplete=True,
                incomplete_reason="Khách có việc gấp, xin về",
            )
        )
        assert ket["incomplete"] is True

    def test_con_viec_treo_van_dong_duoc_khong_can_giai_trinh(self) -> None:
        """Luật đổi 13/08/2026: còn việc treo thì BÁO, không CHẶN.

        Tuyền chốt khi nghiệm thu: bấm Checkout / Đặt lịch / Tái khám phải đi
        được. Ở phòng khám thật gần như lượt nào cũng còn một hai việc chưa tick
        (kết quả về sau, tệp gửi sau), nên cửa cũ bắt người ở quầy giải trình cho
        chuyện bình thường — và một cửa lần nào cũng phải vượt thì người ta gõ
        bừa cho xong, biến dòng lý do thành rác trong sổ.

        `blockers` vẫn được tính và vẫn trả về, nên màn hình vẫn nói được "lượt
        này còn 2 việc". Bài kiểm này giữ ranh giới ấy: BÁO thì còn, CHẶN thì hết.
        """
        import asyncio
        from unittest.mock import AsyncMock

        svc, _ = self._service()
        svc.readiness = AsyncMock(
            return_value={
                "already_closed": False,
                "blockers": [{"type": "service_open", "message": "Còn 2 dịch vụ"}],
            }
        )

        ket = asyncio.run(
            svc.close(
                identity=_identity(),
                visit_id="11111111-1111-4111-8111-111111111111",
            )
        )
        assert ket["ok"] is True, "còn việc treo vẫn phải đóng được, không đòi lý do"

    def test_kham_do_khong_phai_trang_thai_cuoi(self) -> None:
        """Tính chất quan trọng nhất: khách còn quay lại, nên hồ sơ còn ghi
        được. Nếu INCOMPLETE lọt vào danh sách khoá thì "khám dở" đã lặng lẽ
        trở thành một cái ngõ cụt."""
        from clinicai.services.clinical_record_service import (
            WRITABLE_VISIT_STATUSES,
        )

        assert "INCOMPLETE" in WRITABLE_VISIT_STATUSES
        assert "FINALIZED" not in WRITABLE_VISIT_STATUSES


def _identity() -> Any:
    from clinicai.api.identity import ClinicRole, StaffIdentity

    return StaffIdentity(
        staff_id="22222222-2222-4222-8222-222222222222",
        auth_user_id="33333333-3333-4333-8333-333333333333",
        full_name="Lễ tân",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
        clinic_id="44444444-4444-4444-8444-444444444444",
        location_id="55555555-5555-4555-8555-555555555555",
        location_name="Kim Ngưu",
    )
