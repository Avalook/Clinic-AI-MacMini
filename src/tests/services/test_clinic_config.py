"""Cấu hình phòng khám: ai được sửa, và ba tầng tên gọi lồng nhau.

Yêu cầu của Quang (04/08/2026): quản lý tự khai phòng nào là phòng siêu âm,
toà nhà có mấy tầng, bác sĩ nào khám được những gì — *"để khi sang phòng khám
khác họ có cấu trúc khác, lỡ họ có 2 tầng, 5 tầng thì sao"*.

Đã chạy trên prod (rollback): Kim Ngưu 9 phòng tầng 1 + 3 phòng chưa khai tầng ·
Trưởng ca bị chặn · bỏ bước chính bị chặn · thu hẹp KB01 từ 5 xuống 2 bước ·
đổi một bác sĩ thành chỉ siêu âm · gỡ hết năng lực (rỗng hợp lệ).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.clinic_config_service import (
    CONFIG_ROLES,
    ClinicConfigService,
    _group_locations,
    assert_may_configure,
)
from tests.services.fake_pool import FakePool


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


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


# ── Phần chạm database ─────────────────────────────────────────────────────
#
# Ba luồng ghi ở đây thay TOÀN BỘ danh sách thay vì thêm/bớt từng cái. Cái đáng
# kiểm không phải câu SQL, mà THỨ TỰ: từ chối phải xảy ra TRƯỚC khi xoá dòng
# nào, nếu không một lần bấm nhầm sẽ để lại phòng không phục vụ bước nào.


class TestSetRoomFloorIO:
    def test_blank_means_not_declared_not_an_empty_floor(self) -> None:
        pool = FakePool("SA1")
        out = _run(
            ClinicConfigService(pool).set_room_floor(
                identity=_who(ClinicRole.MANAGEMENT), room_id="r-1", floor="  "
            )
        )
        assert out["floor"] is None

    def test_unknown_room(self) -> None:
        pool = FakePool(None)
        with pytest.raises(ValidationError, match="Không tìm thấy phòng"):
            _run(
                ClinicConfigService(pool).set_room_floor(
                    identity=_who(ClinicRole.MANAGEMENT), room_id="r-1", floor="2"
                )
            )

    def test_a_refused_role_never_reaches_the_database(self) -> None:
        pool = FakePool("SA1")
        with pytest.raises(ValidationError):
            _run(
                ClinicConfigService(pool).set_room_floor(
                    identity=_who(ClinicRole.TRUONG_CA), room_id="r-1", floor="2"
                )
            )
        assert pool.queries() == []


class TestSetRoomNodesIO:
    def test_dropping_the_primary_step_is_refused_before_any_delete(self) -> None:
        """Trigger `clinic_room_primary_node_is_served` cũng chặn, nhưng nó ném
        tên ràng buộc. Ở đây nói bằng câu đọc được — và nói trước khi xoá."""
        pool = FakePool({"code": "SA1", "node_code": "DICHVU-SIEUAM"})
        with pytest.raises(ValidationError, match="bước chính"):
            _run(
                ClinicConfigService(pool).set_room_nodes(
                    identity=_who(ClinicRole.MANAGEMENT),
                    room_id="r-1",
                    node_codes=["KHAM-SK"],
                )
            )
        assert not any("DELETE" in q for q in pool.queries())

    def test_the_whole_list_is_replaced(self) -> None:
        pool = FakePool({"code": "SA1", "node_code": None})
        out = _run(
            ClinicConfigService(pool).set_room_nodes(
                identity=_who(ClinicRole.MANAGEMENT),
                room_id="r-1",
                node_codes=["DICHVU-SIEUAM", "KHAM-SK"],
            )
        )
        assert out["nodes"] == ["DICHVU-SIEUAM", "KHAM-SK"]
        assert pool.wrote("DELETE FROM public.clinic_room_node")
        assert pool.wrote("INSERT INTO public.clinic_room_node")

    def test_an_empty_list_still_clears(self) -> None:
        pool = FakePool({"code": "KB01", "node_code": None})
        _run(
            ClinicConfigService(pool).set_room_nodes(
                identity=_who(ClinicRole.MANAGEMENT), room_id="r-1", node_codes=[]
            )
        )
        assert pool.wrote("DELETE FROM public.clinic_room_node")
        assert not pool.wrote("INSERT INTO public.clinic_room_node")


class TestSetStaffNodesIO:
    def test_unknown_staff(self) -> None:
        pool = FakePool(None)
        with pytest.raises(ValidationError, match="Không tìm thấy nhân sự"):
            _run(
                ClinicConfigService(pool).set_staff_nodes(
                    identity=_who(ClinicRole.MANAGEMENT),
                    staff_id="s-9",
                    node_codes=["KHAM-SK"],
                )
            )

    def test_an_empty_list_is_valid_and_means_something(self) -> None:
        """Lễ tân và thu ngân không đảm nhiệm bước khám nào. Đọc rỗng thành
        "chưa khai" thì không ai gỡ được năng lực đã khai nhầm."""
        pool = FakePool("Chị Lễ tân")
        out = _run(
            ClinicConfigService(pool).set_staff_nodes(
                identity=_who(ClinicRole.MANAGEMENT), staff_id="s-1", node_codes=[]
            )
        )
        assert out["nodes"] == []
        assert pool.wrote("DELETE FROM public.staff_node")

    def test_one_doctor_may_hold_several_steps(self) -> None:
        pool = FakePool("BS. Thành")
        out = _run(
            ClinicConfigService(pool).set_staff_nodes(
                identity=_who(ClinicRole.MANAGEMENT),
                staff_id="s-1",
                node_codes=["KHAM-SK", "KHAM-PK", "DICHVU-SIEUAM"],
            )
        )
        assert len(out["nodes"]) == 3
        assert pool.wrote("INSERT INTO public.staff_node")


class TestReadIO:
    def test_overview_returns_layout_and_the_step_catalogue(self) -> None:
        pool = FakePool([], [{"code": "KHAM-SK", "name": "Khám Sản khoa"}])
        out = _run(
            ClinicConfigService(pool).overview(identity=_who(ClinicRole.MANAGEMENT))
        )
        assert out["locations"] == []
        assert out["nodes"] == [{"code": "KHAM-SK", "name": "Khám Sản khoa"}]

    def test_staff_returns_capabilities(self) -> None:
        pool = FakePool(
            [
                {
                    "id": "s-1",
                    "full_name": "BS. Thành",
                    "short_name": "Thành",
                    "role": "DOCTOR",
                    "location_name": "Kim Ngưu",
                    "nodes": ["KHAM-SK"],
                }
            ]
        )
        out = _run(
            ClinicConfigService(pool).staff(identity=_who(ClinicRole.MANAGEMENT))
        )
        assert out["items"][0]["nodes"] == ["KHAM-SK"]
