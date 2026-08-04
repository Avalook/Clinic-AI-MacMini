"""Cấu hình phòng khám: ai được sửa, và ba tầng tên gọi lồng nhau.

Yêu cầu của Quang (04/08/2026): quản lý tự khai phòng nào là phòng siêu âm,
toà nhà có mấy tầng, bác sĩ nào khám được những gì — *"để khi sang phòng khám
khác họ có cấu trúc khác, lỡ họ có 2 tầng, 5 tầng thì sao"*.

Đã chạy trên prod (rollback): Kim Ngưu 9 phòng tầng 1 + 3 phòng chưa khai tầng ·
Trưởng ca bị chặn · bỏ bước chính bị chặn · thu hẹp KB01 từ 5 xuống 2 bước ·
đổi một bác sĩ thành chỉ siêu âm · gỡ hết năng lực (rỗng hợp lệ).
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.clinic_config_service import (
    CONFIG_ROLES,
    _group_locations,
    assert_may_configure,
)


def _who(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        auth_user_id="00000000-0000-0000-0000-000000000000",
        staff_id="00000000-0000-0000-0000-000000000000",
        full_name="x",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        # `location_id` là str BẮT BUỘC, không phải Optional — mọi nhân sự đều
        # có cơ sở kể từ 20260803000007. Fixture khai None là khai một trạng
        # thái không tồn tại trong hệ thống thật.
        location_id="c1100000-0000-4000-8000-000000000001",
        location_name="x",
    )


class TestWhoMayChangeTheLayout:
    def test_only_management(self) -> None:
        assert_may_configure(_who(ClinicRole.MANAGEMENT))

    @pytest.mark.parametrize(
        "role",
        [ClinicRole.TRUONG_CA, ClinicRole.DOCTOR, ClinicRole.RECEPTION],
    )
    def test_everyone_else_is_refused(self, role: ClinicRole) -> None:
        """Khai cấu hình là đổi LUẬT vận hành, khác với dùng hằng ngày.

        Trưởng ca điều phối bệnh nhân giữa các phòng nhưng không đổi được sơ đồ
        phòng — gộp hai quyền thì một lần bấm nhầm giữa ca đổi luôn cách cả
        phòng khám vận hành.
        """
        with pytest.raises(ValidationError, match="không sửa được cấu hình"):
            assert_may_configure(_who(role))

    def test_the_list_is_exactly_management(self) -> None:
        assert CONFIG_ROLES == frozenset({ClinicRole.MANAGEMENT})


def _row(
    loc: str, room: str | None, floor: str | None, sort: int = 0
) -> dict[str, Any]:
    return {
        "location_id": loc,
        "location_code": loc[:3].upper(),
        "location_name": loc,
        "location_active": True,
        "room_id": room,
        "room_code": room,
        "room_name": room,
        "floor": floor,
        "capacity": 1,
        "room_active": True,
        "primary_node": "KHAM-PHUKHOA",
        "sort": sort,
        "serves": ["KHAM-PHUKHOA"],
    }


class TestGroupingIntoLocationsAndFloors:
    """Ba tầng tên gọi lồng nhau: phòng khám → cơ sở → phòng (trên một tầng)."""

    def test_rooms_gather_under_their_floor(self) -> None:
        out = _group_locations(
            [_row("Kim Ngưu", "KB01", "1"), _row("Kim Ngưu", "KB02", "1")]
        )
        assert len(out) == 1
        assert len(out[0]["floors"]) == 1
        assert len(out[0]["floors"][0]["rooms"]) == 2

    def test_two_floors_stay_apart(self) -> None:
        out = _group_locations(
            [_row("Kim Ngưu", "KB01", "1"), _row("Kim Ngưu", "SA1", "2")]
        )
        assert [f["floor"] for f in out[0]["floors"]] == ["1", "2"]

    def test_an_unlabelled_floor_is_its_own_group_not_merged_into_floor_one(
        self,
    ) -> None:
        """ "Chưa khai" và "tầng 1" là hai chuyện khác nhau.

        Gộp chúng thì màn cấu hình không còn nhìn thấy cái cần đi khai — và
        Trưởng ca đọc lên thành một câu chỉ đường sai.
        """
        out = _group_locations(
            [_row("Kim Ngưu", "KB01", "1"), _row("Kim Ngưu", "SA1", None)]
        )
        floors = [f["floor"] for f in out[0]["floors"]]
        assert floors == ["1", None]

    def test_two_buildings_never_share_a_floor(self) -> None:
        """ "Tầng 2" ở Kim Ngưu và "tầng 2" ở Hào Nam là hai chỗ khác nhau."""
        out = _group_locations(
            [_row("Kim Ngưu", "SA1", "2"), _row("Hào Nam", "SA9", "2")]
        )
        assert len(out) == 2
        assert all(len(loc["floors"]) == 1 for loc in out)

    def test_a_location_with_no_rooms_still_appears(self) -> None:
        """Hào Nam có trong hệ thống nhưng chưa khai phòng nào. Ẩn nó đi thì
        quản lý không có chỗ nào để bắt đầu khai."""
        out = _group_locations([_row("Hào Nam", None, None)])
        assert len(out) == 1
        assert out[0]["floors"] == []
