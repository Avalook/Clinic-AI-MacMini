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
from typing import Any

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
    """Giữ chỗ hỏi QUYỀN "Đặt lịch" (`booking.create`) — cùng câu với lệnh đặt
    lịch (24/09/2026). Trước đây là tập vai HOLD_ROLES chép tay."""

    def test_nhom_mau_co_dat_lich_dung_bon_vai_cu(self) -> None:
        """Chuyển sang quyền không ai được/mất việc: nhóm mẫu có khối "Đặt lịch"
        đúng là bốn vai cũ (HOLD_ROLES = INTAKE_ROLES; policy RLS chép y vậy)."""
        from clinicai.permissions.catalogue import PRESET
        from clinicai.services.booking_service import INTAKE_ROLES

        assert HOLD_ROLES == INTAKE_ROLES
        co = {vai for vai, khoi in PRESET.items() if "dat_lich" in khoi}
        assert co == {r.value for r in HOLD_ROLES}

    @pytest.mark.asyncio
    async def test_co_quyen_thi_giu_duoc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import clinicai.services.slot_hold_service as m

        async def co(*_: Any, **__: Any) -> bool:
            return True

        monkeypatch.setattr(m, "can", co)
        await _assert_may_hold(None, _identity(ClinicRole.CSKH))

    @pytest.mark.asyncio
    async def test_khong_co_quyen_thi_khong_giu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import clinicai.services.slot_hold_service as m

        async def khong(*_: Any, **__: Any) -> bool:
            return False

        monkeypatch.setattr(m, "can", khong)
        with pytest.raises(ValidationError, match="không giữ chỗ"):
            await _assert_may_hold(None, _identity(ClinicRole.DOCTOR))


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
