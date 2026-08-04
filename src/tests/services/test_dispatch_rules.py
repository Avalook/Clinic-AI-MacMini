"""Luật của bảng điều phối: bước kế tiếp, màu phòng, và xếp hạng cảnh báo.

Ba thứ này quyết định Trưởng ca nhìn vào việc gì trước, nên chúng phải kiểm được
mà không cần một phòng khám đang chạy. Phần SQL (vị trí bệnh nhân, tải từng
phòng) được đối chiếu trực tiếp trên prod bằng một lượt khám thật rồi rollback.
"""

from __future__ import annotations

from typing import Any

from clinicai.services.dispatch_service import (
    _station_state,
    build_alerts,
    next_step_of,
)


class TestNextStep:
    ROUTE = ["DICHVU-SIEUAM", "DICHVU-LAYMAU-MAU", "DICHVU-DUYET-KETQUA"]

    def test_the_first_unfinished_step_that_is_not_the_current_one(self) -> None:
        assert (
            next_step_of(self.ROUTE, ["DICHVU-SIEUAM"], "DICHVU-LAYMAU-MAU")
            == "DICHVU-DUYET-KETQUA"
        )

    def test_the_current_step_is_never_its_own_next_step(self) -> None:
        """Bệnh nhân đang ở siêu âm thì "bước tiếp theo" không phải siêu âm.

        Không loại bước hiện tại thì cột "Trạm kế tiếp" lặp lại cột "Trạm hiện
        tại" cho mọi người vừa được chuyển tới — và Trưởng ca không còn biết ai
        thật sự đang chờ đi đâu.
        """
        assert next_step_of(self.ROUTE, [], "DICHVU-SIEUAM") == "DICHVU-LAYMAU-MAU"

    def test_no_route_means_unknown_not_finished(self) -> None:
        """Chưa chọn tuyến khác hẳn đã đi hết tuyến — người gọi phân biệt bằng
        việc có route_steps hay không, nên cả hai đều trả None ở đây."""
        assert next_step_of(None, [], "DICHVU-SIEUAM") is None

    def test_a_finished_route_has_no_next_step(self) -> None:
        assert next_step_of(self.ROUTE, self.ROUTE, None) is None

    def test_a_route_changed_mid_way_keeps_finished_steps_out(self) -> None:
        """Đổi sang tuyến C sau khi đã siêu âm: bước đã xong không quay lại."""
        route_c = ["DICHVU-SIEUAM", "DICHVU-DUYET-KETQUA", "DICHVU-LAYMAU-MAU"]
        assert next_step_of(route_c, ["DICHVU-SIEUAM"], None) == "DICHVU-DUYET-KETQUA"


class TestStationColour:
    def test_within_both_thresholds_is_ok(self) -> None:
        assert (
            _station_state(waiting=3, max_wait=10, cap_waiting=8, cap_minutes=20)
            == "ok"
        )

    def test_one_threshold_breached_is_a_warning(self) -> None:
        assert _station_state(9, 10, 8, 20) == "warning"  # đông nhưng nhanh
        assert _station_state(3, 25, 8, 20) == "warning"  # vắng nhưng kẹt

    def test_both_thresholds_breached_is_critical(self) -> None:
        assert _station_state(9, 25, 8, 20) == "critical"

    def test_exactly_at_the_threshold_is_still_ok(self) -> None:
        """Ngưỡng là mốc VƯỢT, không phải mốc chạm.

        Đặt ngưỡng 20 phút mà cảnh báo nổ ở đúng phút thứ 20 thì người vận hành
        sẽ chỉnh ngưỡng lên 21 — và con số trong cấu hình thôi nói đúng ý nghĩa
        của nó.
        """
        assert _station_state(8, 20, 8, 20) == "ok"


def _patient(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "patient_name": "Nguyễn Thị A",
        "patient_code": "BN-2026-000001",
        "room_code": "SA1",
        "current_node_code": "DICHVU-SIEUAM",
        "current_node_name": "Thực hiện siêu âm",
        "wait_minutes": 5,
        "threshold_minutes": 20,
        "route_steps": ["DICHVU-SIEUAM", "DICHVU-LAYMAU-MAU"],
        "next_step": "DICHVU-LAYMAU-MAU",
    }
    base.update(over)
    return base


def _room(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "code": "SA1",
        "name": "Siêu âm SA1",
        "state": "ok",
        "waiting": 2,
        "max_wait": 8,
    }
    base.update(over)
    return base


class TestAlerts:
    def test_a_quiet_clinic_produces_no_alerts(self) -> None:
        assert build_alerts([_patient()], [_room()]) == []

    def test_an_overloaded_room_lists_the_patients_it_affects(self) -> None:
        """Yêu cầu khách hàng: cảnh báo "chỉ rõ phòng VÀ danh sách bệnh nhân".

        Một cảnh báo chỉ nói "SA1 quá tải" bắt Trưởng ca tự đi tìm xem ai đang
        kẹt ở đó — đúng lúc đang bận nhất.
        """
        alerts = build_alerts(
            [_patient(), _patient(patient_name="B", room_code="SA2")],
            [_room(state="critical", waiting=9, max_wait=30)],
        )
        overload = [a for a in alerts if a["type"] == "room_overloaded"]
        assert len(overload) == 1
        assert overload[0]["severity"] == "critical"
        assert [p["name"] for p in overload[0]["patients"]] == ["Nguyễn Thị A"]

    def test_critical_alerts_sort_above_warnings(self) -> None:
        """*"Cảnh báo phải được xếp theo mức độ… tránh hiển thị quá nhiều cảnh
        báo khiến trưởng ca không biết xử lý việc nào trước."*"""
        alerts = build_alerts(
            [
                _patient(wait_minutes=25),  # warning
                _patient(patient_name="B", wait_minutes=50),  # critical (>2×)
            ],
            [_room()],
        )
        assert [a["severity"] for a in alerts][0] == "critical"

    def test_a_patient_with_no_station_is_flagged(self) -> None:
        """Đã check-in mà không ở trạm nào = bị bỏ quên giữa phòng chờ."""
        alerts = build_alerts([_patient(current_node_code=None, room_code=None)], [])
        assert any(a["type"] == "missing_next_step" for a in alerts)

    def test_a_patient_with_no_route_is_flagged(self) -> None:
        alerts = build_alerts([_patient(route_steps=None, next_step=None)], [_room()])
        assert any(a["type"] == "no_route" for a in alerts)

    def test_the_message_is_a_sentence_not_a_code(self) -> None:
        """*"Lý do bệnh nhân bị chặn phải hiển thị bằng câu dễ hiểu… không hiển
        thị mã hoặc tên kỹ thuật."*"""
        alerts = build_alerts([_patient(wait_minutes=40)], [_room()])
        msg = alerts[0]["message"]
        assert "Nguyễn Thị A" in msg and "phút" in msg
        assert "DICHVU-" not in msg


class TestRoomsCarryTheirFloor:
    """Tầng phải đi cùng phòng ra tới màn hình.

    Cơ sở Kim Ngưu có ba tầng và SIÊU ÂM NẰM Ở HAI TẦNG KHÁC NHAU (báo cáo
    onsite 23/04/2026: tầng 2 và tầng 4), mọi thứ khác ở tầng 1. Nên "sang SA2"
    là câu chưa đủ để chỉ đường — Trưởng ca đang phải tự nhớ phần còn lại,
    40–60 lần mỗi buổi.
    """

    def test_the_station_query_selects_the_floor(self) -> None:
        from clinicai.services.dispatch_service import _STATIONS_SQL

        assert "r.floor" in _STATIONS_SQL
        # Có trong SELECT thì phải có trong GROUP BY, nếu không Postgres từ chối
        # cả câu và bảng điều phối trắng.
        after_group = _STATIONS_SQL.split("GROUP BY", 1)[1]
        assert "r.floor" in after_group

    def test_the_overview_query_carries_the_floor_of_the_room_they_are_in(
        self,
    ) -> None:
        from clinicai.services.dispatch_service import _OVERVIEW_SQL

        assert "r.floor" in _OVERVIEW_SQL
        assert "room_floor" in _OVERVIEW_SQL

    def test_an_unassigned_floor_stays_null_instead_of_becoming_a_guess(
        self,
    ) -> None:
        """SA1/SA2/SA3 của Kim Ngưu CỐ Ý để trống.

        Báo cáo nói siêu âm ở tầng 2 VÀ tầng 4 nhưng không nói phòng nào ở tầng
        nào. Điền đại một cái thì phần lớn khả năng là sai — và cái sai đó được
        đọc lên thành câu chỉ đường cho bệnh nhân đang đứng ở sảnh.
        """
        from clinicai.services.dispatch_service import _STATIONS_SQL

        for bad in ("coalesce(r.floor", "COALESCE(r.floor"):
            assert bad not in _STATIONS_SQL, (
                "đừng lấp NULL bằng giá trị mặc định — 'chưa khai tầng' và "
                "'tầng 1' là hai chuyện khác nhau"
            )


class TestARoomServesManySteps:
    """Chuyên khoa do BÁC SĨ ngồi trong phòng quyết định, không phải bốn bức tường.

    Bốn phòng khám KB01–KB04 đều ghim vào `KHAM-PHUKHOA` trong khi phòng khám
    có năm chuyên khoa. Hệ quả: `move_visit_to_station` TỪ CHỐI chuyển một ca
    Nam khoa vào KB02 vì "phòng không phục vụ bước KHAM-NAMKHOA".

    Đã chạy trên prod (rollback): Nam khoa → KB02 nay cho qua; Nam khoa → Nhà
    thuốc VẪN bị chặn; và đặt bước chính là một bước phòng không phục vụ cũng
    bị chặn.
    """

    def test_the_station_query_returns_every_step_a_room_serves(self) -> None:
        from clinicai.services.dispatch_service import _STATIONS_SQL

        assert "clinic_room_node" in _STATIONS_SQL
        assert "serves_nodes" in _STATIONS_SQL

    def test_it_aggregates_instead_of_joining_and_duplicating_rooms(
        self,
    ) -> None:
        """Join thẳng bảng nối vào câu chính sẽ nhân KB01 thành năm dòng, và
        bảng tải từng phòng đếm sai gấp năm."""
        from clinicai.services.dispatch_service import _STATIONS_SQL

        assert "array_agg(rn.node_code" in _STATIONS_SQL

    def test_an_empty_list_is_an_empty_array_not_null(self) -> None:
        """Phòng chưa khai bước nào phải ra `[]`, không phải NULL — giao diện
        gọi `.includes()` trên nó, và NULL thì nổ."""
        from clinicai.services.dispatch_service import _STATIONS_SQL

        assert "coalesce(array_agg(rn.node_code" in _STATIONS_SQL
