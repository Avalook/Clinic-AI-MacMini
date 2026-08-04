"""Luật thứ tự bắt buộc: "phải qua đây trước khi được đi tiếp".

Yêu cầu của Quang: *"đặt lịch để bác sĩ Thành là người mà khách nào đến cũng gặp
đầu tiên rồi mới được chỉ định gặp bác sĩ khác"* — khai thành LUẬT theo từng
phòng khám, không viết cứng cho Dr4Women.

Đây là một chốt an toàn: nó nói "không" với thao tác con người đang muốn làm,
giữa ca trực, với bệnh nhân đang đứng đó. Sai hướng chặn nhầm thì phòng khám
tắc; sai hướng buông lỏng thì luật vô nghĩa. Nên mọi tổ hợp đều có mặt ở đây.
"""

from __future__ import annotations

from clinicai.services.gate_rule_service import (
    GateRule,
    VisitFacts,
    applies_to,
    blocks,
    first_block,
    may_override,
    satisfied,
)

THANH = "staff-thanh"
HOA = "staff-hoa"
KHAM = ("KHAM-PHUKHOA", "KHAM-SANKHOA", "KHAM-NAMKHOA")


def dr4women(**over: object) -> GateRule:
    """Luật thật của Dr4Women: BS Thành gặp trước, rồi mới sang bác sĩ khác."""
    base: dict[str, object] = dict(
        id="r1",
        name="BS Thành khám trước",
        location_id=None,
        patient_kind=None,
        service_type_id=None,
        required_node_code="KHAM-PHUKHOA",
        required_staff_id=THANH,
        blocked_node_codes=KHAM,
        only_when_other_staff=True,
        override_roles=("TRUONG_CA", "MANAGEMENT"),
    )
    base.update(over)
    return GateRule(**base)  # type: ignore[arg-type]


def sang_loc(**over: object) -> GateRule:
    """Luật của một phòng khám KHÁC: điều dưỡng sàng lọc trước khi gặp bác sĩ.

    Cùng một khuôn, không thêm cột nào — đây là điểm của cả thiết kế.
    """
    base: dict[str, object] = dict(
        id="r2",
        name="Sinh hiệu trước khi khám",
        location_id=None,
        patient_kind=None,
        service_type_id=None,
        required_node_code="LUOTKHAM-03",
        required_staff_id=None,
        blocked_node_codes=KHAM,
        only_when_other_staff=False,
        override_roles=("TRUONG_CA",),
    )
    base.update(over)
    return GateRule(**base)  # type: ignore[arg-type]


def facts(**over: object) -> VisitFacts:
    base: dict[str, object] = dict(
        location_id="loc-kim-nguu",
        patient_kind="NEW",
        service_type_id="sv-phukhoa",
        completed=(),
        target_staff_id=None,
    )
    base.update(over)
    return VisitFacts(**base)  # type: ignore[arg-type]


class TestTheDr4womenCase:
    def test_another_doctor_is_blocked_before_the_gate_doctor_has_seen_them(
        self,
    ) -> None:
        assert blocks(dr4women(), facts(target_staff_id=HOA), "KHAM-PHUKHOA")

    def test_the_gate_doctor_himself_is_never_blocked(self) -> None:
        """ĐÂY LÀ CHỖ LUẬT DỄ TỰ CHẶN CHÍNH NÓ NHẤT.

        Bước bị chặn (khám) TRÙNG với bước bắt buộc (cũng là khám). Không phân
        biệt theo người thì bệnh nhân không vào nổi phòng BS Thành để làm đúng
        cái việc mà luật đang đòi — phòng khám đứng im.
        """
        assert not blocks(dr4women(), facts(target_staff_id=THANH), "KHAM-PHUKHOA")

    def test_once_the_gate_doctor_has_seen_them_anyone_may(self) -> None:
        seen = facts(completed=(("KHAM-PHUKHOA", THANH),), target_staff_id=HOA)
        assert not blocks(dr4women(), seen, "KHAM-PHUKHOA")

    def test_the_same_step_done_by_someone_else_does_not_count(self) -> None:
        """Luật nói ĐÍCH DANH BS Thành. BS Hoa khám xong không mở cổng."""
        seen = facts(completed=(("KHAM-PHUKHOA", HOA),), target_staff_id=HOA)
        assert blocks(dr4women(), seen, "KHAM-PHUKHOA")

    def test_an_unassigned_room_is_not_blocked_yet(self) -> None:
        """Chưa xếp ai thì chưa biết là "bác sĩ khác".

        Chặn ở đây là chặn cả nước đi hợp lệ vào phòng của chính người gác cổng
        — Trưởng ca thường chuyển vào phòng trước, bác sĩ nhận sau.
        """
        assert not blocks(dr4women(), facts(target_staff_id=None), "KHAM-PHUKHOA")

    def test_steps_outside_the_blocked_list_are_untouched(self) -> None:
        """Đi siêu âm, lấy máu, mua thuốc không liên quan gì tới luật này."""
        for node in ("DICHVU-SIEUAM", "DICHVU-LAYMAU-MAU", "THUOC-04"):
            assert not blocks(dr4women(), facts(target_staff_id=HOA), node)


class TestTheOtherClinicCase:
    """Cùng một khuôn, luật hoàn toàn khác — không thêm dòng code nào."""

    def test_a_doctor_is_blocked_until_vitals_are_done(self) -> None:
        assert blocks(sang_loc(), facts(), "KHAM-PHUKHOA")

    def test_anyone_may_do_the_required_step(self) -> None:
        """Luật này KHÔNG chỉ đích danh ai, nên điều dưỡng nào làm cũng được."""
        done = facts(completed=(("LUOTKHAM-03", "staff-bat-ky"),))
        assert not blocks(sang_loc(), done, "KHAM-PHUKHOA")

    def test_it_does_not_care_who_the_next_doctor_is(self) -> None:
        done = facts(completed=(("LUOTKHAM-03", None),), target_staff_id=HOA)
        assert not blocks(sang_loc(), done, "KHAM-PHUKHOA")


class TestWhoTheRuleAppliesTo:
    """NULL = MỌI GIÁ TRỊ, không phải "chỉ khớp NULL".

    Hiểu ngược lại thì một luật khai cho mọi bệnh nhân sẽ không áp cho ai cả —
    và đó là kiểu hỏng im lặng: luật vẫn nằm đó, vẫn bật, và không chặn gì.
    """

    def test_an_empty_scope_applies_to_everyone(self) -> None:
        assert applies_to(dr4women(), facts(patient_kind="RETURN"))
        assert applies_to(dr4women(), facts(location_id="loc-khac"))

    def test_a_new_patient_rule_skips_returning_patients(self) -> None:
        rule = dr4women(patient_kind="NEW")
        assert applies_to(rule, facts(patient_kind="NEW"))
        assert not applies_to(rule, facts(patient_kind="RETURN"))

    def test_a_location_rule_stays_in_its_building(self) -> None:
        """Kim Ngưu và Hào Nam là hai toà nhà; luật của nơi này không áp cho
        nơi kia."""
        rule = dr4women(location_id="loc-kim-nguu")
        assert applies_to(rule, facts(location_id="loc-kim-nguu"))
        assert not applies_to(rule, facts(location_id="loc-hao-nam"))

    def test_a_service_rule_only_touches_that_service(self) -> None:
        rule = dr4women(service_type_id="sv-phukhoa")
        assert applies_to(rule, facts(service_type_id="sv-phukhoa"))
        assert not applies_to(rule, facts(service_type_id="sv-namkhoa"))


class TestWhichRuleBlocks:
    def test_it_names_the_rule_instead_of_just_saying_no(self) -> None:
        """Người dùng cần biết luật NÀO chặn — để ghi lý do đúng chỗ, và để
        màn hình nói được tên luật thay vì "không được phép"."""
        hit = first_block(
            [sang_loc(), dr4women()], facts(target_staff_id=HOA), "KHAM-PHUKHOA"
        )
        assert hit is not None
        assert hit.name == "Sinh hiệu trước khi khám"

    def test_no_rules_means_nothing_is_blocked(self) -> None:
        assert first_block([], facts(target_staff_id=HOA), "KHAM-PHUKHOA") is None

    def test_a_rule_that_does_not_apply_never_blocks(self) -> None:
        rule = dr4women(patient_kind="RETURN")
        assert (
            first_block([rule], facts(patient_kind="NEW", target_staff_id=HOA),
                        "KHAM-PHUKHOA")
            is None
        )


class TestWhoMaySkipIt:
    """Ngoại lệ KHÔNG phải phần phụ.

    Phòng khám thật luôn có ca ngoại lệ; hệ thống nào không cho ngoại lệ sẽ bị
    vượt mặt bằng giấy tay, và lúc đó nó mất luôn khả năng biết chuyện gì đã
    xảy ra. Nên ngoại lệ được PHÉP — nhưng bắt ghi lý do và ghi vào sổ.
    """

    def test_the_shift_lead_may(self) -> None:
        assert may_override(dr4women(), "TRUONG_CA")

    def test_reception_may_not(self) -> None:
        assert not may_override(dr4women(), "RECEPTION")

    def test_each_rule_names_its_own_list(self) -> None:
        """Luật sàng lọc chỉ cho Trưởng ca, không cho Quản lý — mỗi phòng khám
        tự quyết ai được bỏ qua luật của mình."""
        assert may_override(sang_loc(), "TRUONG_CA")
        assert not may_override(sang_loc(), "MANAGEMENT")


class TestTheRequiredStepItself:
    def test_nothing_done_means_not_satisfied(self) -> None:
        assert not satisfied(dr4women(), facts())

    def test_a_different_step_does_not_satisfy_it(self) -> None:
        assert not satisfied(
            dr4women(), facts(completed=(("DICHVU-SIEUAM", THANH),))
        )

    def test_an_unattributed_step_satisfies_a_rule_with_no_named_staff(
        self,
    ) -> None:
        """work_item.assigned_to hôm nay mới điền 1/7 dòng. Luật không chỉ đích
        danh ai thì vẫn phải chạy được với dữ liệu đó."""
        assert satisfied(sang_loc(), facts(completed=(("LUOTKHAM-03", None),)))

    def test_an_unattributed_step_does_not_satisfy_a_named_rule(self) -> None:
        """Ngược lại: luật đòi đích danh BS Thành mà không biết ai làm thì coi
        như CHƯA qua. Chặn thừa còn hơn buông lỏng ở một chốt an toàn."""
        assert not satisfied(
            dr4women(), facts(completed=(("KHAM-PHUKHOA", None),))
        )
