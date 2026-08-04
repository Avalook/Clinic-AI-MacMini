"""Giữ chỗ 10 phút — giữ lúc ĐANG CHỌN, không phải sau khi đã đặt.

Quang (2026-08-04): *"cái đếm 10' chỉ sinh event khi mà CSKH đang chọn khung
giờ khám để CSKH khác được hiện là khung này đang được giữ để đặt để tránh đặt
trùng, chứ không phải đã ấn đặt lịch rồi lại còn giữ 10' làm gì"*.

Đã chạy trên prod (rollback): giữ hai lần cùng một khung ra ĐÚNG MỘT dòng (gia
hạn, không đẻ thêm), view thấy nó, và lùi `expires_at` về quá khứ thì view hết
thấy ngay — hết hạn là thụ động, không cần cron dọn.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.slot_hold_service import (
    HOLD_MINUTES,
    HOLD_ROLES,
    _assert_may_hold,
    hold_expiry,
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


class TestWhoMayHold:
    @pytest.mark.parametrize("role", sorted(HOLD_ROLES))
    def test_anyone_who_can_book_can_hold(self, role: ClinicRole) -> None:
        """Giữ chỗ là bước đầu của việc đặt lịch.

        Hai danh sách quyền lệch nhau nghĩa là có người bấm chọn được khung giờ
        rồi mới biết mình không đặt được — hoặc đặt được mà không giữ được, và
        người bên cạnh không thấy gì.
        """
        _assert_may_hold(_identity(role))

    def test_the_intake_roles_are_the_same_list_as_booking(self) -> None:
        """Chép tay danh sách vai là cách một quyền lệch đi mà không test nào
        đỏ. Policy RLS của bảng cũng chép đúng bốn vai này."""
        from clinicai.services.booking_service import INTAKE_ROLES

        assert HOLD_ROLES == INTAKE_ROLES

    def test_a_doctor_does_not_hold_booking_slots(self) -> None:
        with pytest.raises(ValidationError, match="không giữ chỗ"):
            _assert_may_hold(_identity(ClinicRole.DOCTOR))

    def test_a_cashier_does_not_hold_booking_slots(self) -> None:
        with pytest.raises(ValidationError, match="không giữ chỗ"):
            _assert_may_hold(_identity(ClinicRole.CASHIER))


class TestHowLongAHoldLasts:
    def test_ten_minutes(self) -> None:
        now = datetime(2026, 8, 4, 9, 0, tzinfo=timezone.utc)
        assert hold_expiry(now) == now + timedelta(minutes=10)

    def test_the_constant_is_what_the_screen_promises(self) -> None:
        """Màn đặt lịch nói "10 phút" bằng chữ. Đổi hằng số mà quên đổi câu chữ
        là nói dối người dùng bằng một con số."""
        assert HOLD_MINUTES == 10

    def test_expiry_is_computed_from_the_moment_of_holding(self) -> None:
        """Không phải từ giờ hẹn. Giữ một khung của tuần sau vẫn chỉ giữ được
        10 phút — nếu tính từ giờ hẹn thì chỗ đó bị treo cả tuần."""
        a = datetime(2026, 8, 4, 9, 0, tzinfo=timezone.utc)
        b = datetime(2026, 8, 4, 15, 30, tzinfo=timezone.utc)
        assert hold_expiry(b) - hold_expiry(a) == b - a
