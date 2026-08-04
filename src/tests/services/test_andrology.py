"""Bộ khám Nam khoa — bốn phép tính, và cái ranh giới không được vượt.

docs/spec-form-nam-khoa.md §6.4: mọi thứ ở đây là GỢI Ý cho bác sĩ đọc, không
phải chẩn đoán và không phải chỉ định. Notion §13 của cả năm node khám đều cấm
rõ việc hệ thống tự kết luận.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from clinicai.services.andrology_service import (
    SemenRange,
    compute_bmi,
    flag_semen,
    score_iief5,
    suggest_genetic_tests,
)

WHO = [
    SemenRange("volume_ml", "Thể tích", Decimal("1.4"), "mL", "WHO_2021"),
    SemenRange("concentration_m_ml", "Nồng độ", Decimal("16"), "triệu/mL", "WHO_2021"),
    SemenRange("progressive_pct", "Di động tiến tới", Decimal("30"), "%", "WHO_2021"),
]


class TestIief5:
    def test_the_top_of_the_scale(self) -> None:
        assert score_iief5([5, 5, 5, 5, 5]) == {
            "score": 25,
            "severity": "Không rối loạn",
        }

    def test_the_bottom_of_the_scale(self) -> None:
        assert score_iief5([1, 1, 1, 1, 1])["severity"] == "Rối loạn nặng"

    @pytest.mark.parametrize(
        "total,band",
        [
            (25, "Không rối loạn"),
            (22, "Không rối loạn"),
            (21, "Rối loạn nhẹ"),
            (17, "Rối loạn nhẹ"),
            (16, "Rối loạn nhẹ – vừa"),
            (12, "Rối loạn nhẹ – vừa"),
            (11, "Rối loạn vừa"),
            (8, "Rối loạn vừa"),
            (7, "Rối loạn nặng"),
            (5, "Rối loạn nặng"),
        ],
    )
    def test_every_boundary_of_every_band(self, total: int, band: str) -> None:
        """Cả hai đầu của cả năm mức. Lệch một điểm ở ranh giới là đọc sai mức
        cho đúng những ca nằm sát ngưỡng — nhóm cần đọc đúng nhất."""
        answers = [1, 1, 1, 1, 1]
        remain = total - 5
        i = 0
        while remain > 0:
            add = min(4, remain)
            answers[i] += add
            remain -= add
            i += 1
        assert sum(answers) == total
        assert score_iief5(answers)["severity"] == band

    def test_a_half_finished_questionnaire_is_refused(self) -> None:
        """Cho điểm phần đã trả lời sẽ ra một tổng thấp giả tạo, và tổng đó đọc
        thành "rối loạn nặng" cho một người chưa trả lời hết."""
        with pytest.raises(ValueError, match="đúng 5 câu"):
            score_iief5([5, 5, 5])

    @pytest.mark.parametrize("bad", [0, 6, -1])
    def test_a_score_outside_the_scale_is_refused(self, bad: int) -> None:
        with pytest.raises(ValueError, match="từ 1 đến 5"):
            score_iief5([bad, 3, 3, 3, 3])


class TestSemenFlags:
    def test_a_value_below_the_limit_is_flagged(self) -> None:
        out = flag_semen({"concentration_m_ml": 12}, WHO)
        assert len(out) == 1
        assert out[0]["parameter"] == "concentration_m_ml"

    def test_exactly_at_the_limit_is_not_below_it(self) -> None:
        """WHO công bố ngưỡng DƯỚI. Đúng bằng ngưỡng là đạt — gắn cờ ở đây là
        báo động cho một kết quả bình thường."""
        assert flag_semen({"concentration_m_ml": 16}, WHO) == []

    def test_a_decimal_limit_is_compared_exactly(self) -> None:
        """1.39 < 1.4. So sánh bằng float có thể trượt ở đúng những ca sát
        ngưỡng, nên giá trị đi qua Decimal."""
        assert len(flag_semen({"volume_ml": 1.39}, WHO)) == 1
        assert flag_semen({"volume_ml": 1.4}, WHO) == []

    def test_a_missing_parameter_is_not_a_failing_one(self) -> None:
        """Không làm xét nghiệm và làm ra kết quả 0 là hai chuyện khác nhau."""
        assert flag_semen({"volume_ml": None}, WHO) == []
        assert flag_semen({}, WHO) == []

    def test_the_message_carries_the_number_and_the_source(self) -> None:
        """Một cái cờ đỏ không kèm con số và nguồn thì bác sĩ vẫn phải tra lại,
        và cái cờ ấy chỉ làm màn hình ồn hơn."""
        msg = flag_semen({"concentration_m_ml": 12}, WHO)[0]["message"]
        assert "12" in msg and "16" in msg and "WHO_2021" in msg

    def test_it_never_says_the_word_infertile(self) -> None:
        """RANH GIỚI: hàm này nói "dưới ngưỡng", không nói chẩn đoán."""
        out = flag_semen({"volume_ml": 0.5, "concentration_m_ml": 1}, WHO)
        joined = " ".join(f["message"] for f in out).lower()
        for cam in ("vô sinh", "hiếm muộn", "chẩn đoán", "bất thường"):
            assert cam not in joined


class TestGeneticSuggestions:
    def test_severe_oligospermia_suggests_karyotype_and_azf(self) -> None:
        out = suggest_genetic_tests(
            concentration_m_ml=2,
            fsh=None,
            testis_volume_ml=None,
            vas_palpable=None,
        )
        assert {x["test"] for x in out} == {"CLS_KARYOTYPE", "CLS_Y_MICRODELETION"}

    def test_every_suggestion_says_why(self) -> None:
        """Danh sách xét nghiệm không kèm lý do thì hoặc bác sĩ bỏ qua cả danh
        sách, hoặc chỉ định hết — cả hai đều tệ hơn không gợi ý gì."""
        out = suggest_genetic_tests(
            concentration_m_ml=0, fsh=3, testis_volume_ml=18, vas_palpable=False
        )
        assert out and all(x["reason"].strip() for x in out)

    def test_absent_vas_suggests_cftr(self) -> None:
        out = suggest_genetic_tests(
            concentration_m_ml=None,
            fsh=None,
            testis_volume_ml=None,
            vas_palpable=False,
        )
        assert [x["test"] for x in out] == ["CLS_CFTR"]

    def test_nothing_is_suggested_without_data(self) -> None:
        """None = chưa có kết quả. Một gợi ý dựng trên số liệu chưa có là một
        gợi ý sai."""
        assert (
            suggest_genetic_tests(
                concentration_m_ml=None,
                fsh=None,
                testis_volume_ml=None,
                vas_palpable=None,
            )
            == []
        )

    def test_a_normal_result_suggests_nothing(self) -> None:
        assert (
            suggest_genetic_tests(
                concentration_m_ml=45, fsh=4, testis_volume_ml=20, vas_palpable=True
            )
            == []
        )

    def test_the_same_test_is_never_suggested_twice(self) -> None:
        """Vô tinh + không sờ thấy ống dẫn tinh đều dẫn tới CFTR."""
        out = suggest_genetic_tests(
            concentration_m_ml=0, fsh=3, testis_volume_ml=18, vas_palpable=False
        )
        tests = [x["test"] for x in out]
        assert len(tests) == len(set(tests))


class TestBmi:
    def test_a_normal_pair(self) -> None:
        assert compute_bmi(170, 65) == 22.5

    @pytest.mark.parametrize(
        "h,w", [(None, 65), (170, None), (0, 65), (170, 0), (-170, 65)]
    )
    def test_missing_or_impossible_measurements_give_none(
        self, h: float | None, w: float | None
    ) -> None:
        """None chứ không phải 0: một BMI bằng 0 lọt vào biểu đồ và vào mọi phép
        so sánh, còn None thì màn hình hiện dấu gạch."""
        assert compute_bmi(h, w) is None
