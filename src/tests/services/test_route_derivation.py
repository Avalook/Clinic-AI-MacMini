"""Tuyến điều phối suy ra từ chỉ định của bác sĩ.

Trước thay đổi này, `visit_route` chỉ được ghi khi có người bấm tay "Áp tuyến"
— và trên prod **0/25 lượt khám có tuyến**, nên cột "bước kế tiếp" của bảng
Trưởng ca trống với mọi bệnh nhân. Bác sĩ chỉ định gì thì bệnh nhân phải đi qua
đó, nên chỉ định ghi luôn tuyến.
"""

from __future__ import annotations

from clinicai.services.route_derivation import (
    canonical_order,
    common_suffix,
    derive_route,
)

# Ba tuyến mẫu thật trên prod: khác nhau đúng ở thứ tự siêu âm / lấy máu.
A = ["DICHVU-SIEUAM", "DICHVU-LAYMAU-MAU", "DICHVU-DUYET-KETQUA", "THUOC-04",
     "LUOTKHAM-14"]
B = ["DICHVU-LAYMAU-MAU", "DICHVU-SIEUAM", "DICHVU-DUYET-KETQUA", "THUOC-04",
     "LUOTKHAM-14"]
C = ["DICHVU-SIEUAM", "DICHVU-DUYET-KETQUA", "DICHVU-LAYMAU-MAU", "THUOC-04",
     "LUOTKHAM-14"]
TPL = [A, B, C]
TAIL = ["THUOC-04", "LUOTKHAM-14"]


class TestCommonSuffix:
    def test_it_reads_the_shared_tail_out_of_the_templates(self) -> None:
        """Đuôi tuyến KHÔNG được viết cứng trong code.

        Viết cứng "duyệt kết quả → thuốc → kết thúc" nghĩa là hôm nào Quang sửa
        tuyến mẫu, code lặng lẽ sai mà không ai biết.
        """
        assert common_suffix(TPL) == TAIL

    def test_identical_templates_share_everything(self) -> None:
        assert common_suffix([A, list(A)]) == A

    def test_nothing_in_common_gives_nothing(self) -> None:
        assert common_suffix([["X"], ["Y"]]) == []

    def test_no_templates_gives_nothing(self) -> None:
        assert common_suffix([]) == []

    def test_an_empty_template_does_not_crash(self) -> None:
        assert common_suffix([A, []]) == []


class TestCanonicalOrder:
    def test_a_step_that_ever_came_first_is_treated_as_first(self) -> None:
        """Tuyến A và B đảo siêu âm/lấy máu. Không tuyến nào là "tuyến chuẩn",
        nên lấy vị trí sớm nhất trên mọi tuyến — miễn là ổn định."""
        order = canonical_order(TPL)
        assert order[:2] == ["DICHVU-LAYMAU-MAU", "DICHVU-SIEUAM"]
        assert order[-1] == "LUOTKHAM-14"

    def test_it_is_deterministic_regardless_of_template_order(self) -> None:
        assert canonical_order(TPL) == canonical_order([C, B, A])


class TestDeriveRoute:
    def test_one_ultrasound_does_not_send_the_patient_to_the_blood_room(
        self,
    ) -> None:
        """ĐÂY LÀ LÝ DO KHÔNG DÙNG THẲNG TUYẾN MẪU.

        Cả ba tuyến mẫu đều chứa CẢ siêu âm LẪN lấy máu — chúng chỉ là ba hoán
        vị của cùng một danh sách. Áp bừa một tuyến cho người chỉ được chỉ định
        siêu âm là bảo Trưởng ca đẩy bệnh nhân sang phòng lấy máu mà bác sĩ
        không hề chỉ định.
        """
        assert derive_route(["DICHVU-SIEUAM"], TPL) == [
            "DICHVU-SIEUAM", "THUOC-04", "LUOTKHAM-14",
        ]

    def test_two_services_come_out_in_clinic_order_not_click_order(
        self,
    ) -> None:
        """Bác sĩ tích siêu âm trước hay lấy máu trước không đổi đường đi thật
        của bệnh nhân — thứ tự khoa phòng mới đổi."""
        clicked_backwards = derive_route(
            ["DICHVU-SIEUAM", "DICHVU-LAYMAU-MAU"], TPL
        )
        clicked_forwards = derive_route(
            ["DICHVU-LAYMAU-MAU", "DICHVU-SIEUAM"], TPL
        )
        assert clicked_backwards == clicked_forwards
        assert clicked_backwards[:2] == ["DICHVU-LAYMAU-MAU", "DICHVU-SIEUAM"]

    def test_the_tail_is_never_duplicated(self) -> None:
        """Chỉ định trúng một bước vốn nằm ở đuôi thì không được ra hai lần —
        `next_step_of` sẽ gợi ý đi lại đúng chỗ vừa xong."""
        route = derive_route(["DICHVU-SIEUAM", "THUOC-04"], TPL)
        assert route.count("THUOC-04") == 1

    def test_the_same_service_ordered_twice_appears_once(self) -> None:
        assert derive_route(["DICHVU-SIEUAM", "DICHVU-SIEUAM"], TPL) == [
            "DICHVU-SIEUAM", "THUOC-04", "LUOTKHAM-14",
        ]

    def test_a_service_no_template_mentions_still_gets_into_the_route(
        self,
    ) -> None:
        """Dịch vụ mới chưa được đưa vào tuyến mẫu nào vẫn phải đi qua.

        Bỏ nó ra khỏi tuyến là im lặng nuốt một chỉ định của bác sĩ — tệ hơn
        nhiều so với việc xếp nó sai chỗ.
        """
        route = derive_route(["DICHVU-DONGBANG-TRUNG"], TPL)
        assert "DICHVU-DONGBANG-TRUNG" in route
        assert route[-2:] == TAIL

    def test_unknown_services_keep_the_order_the_doctor_gave(self) -> None:
        """Không tuyến nào khai thứ tự cho chúng, nên không có gì để suy —
        đoán thứ tự cho một bước chưa ai khai là đoán bừa."""
        route = derive_route(["DICHVU-Z", "DICHVU-Y"], TPL)
        assert route[:2] == ["DICHVU-Z", "DICHVU-Y"]

    def test_nothing_pending_gives_no_route(self) -> None:
        """Không còn việc gì thì không có tuyến — và visit_route_has_steps đòi
        ít nhất một bước, nên trả rỗng chứ đừng ghi một dòng rỗng."""
        assert derive_route([], TPL) == []

    def test_it_works_before_any_template_exists(self) -> None:
        """Phòng khám mới chưa khai tuyến mẫu nào vẫn phải điều phối được."""
        assert derive_route(["DICHVU-SIEUAM"], []) == ["DICHVU-SIEUAM"]

    def test_a_null_node_code_is_dropped(self) -> None:
        """work_item.node_code có thể rỗng với việc tạo tay."""
        assert derive_route(["", "DICHVU-SIEUAM"], TPL) == [
            "DICHVU-SIEUAM", "THUOC-04", "LUOTKHAM-14",
        ]
