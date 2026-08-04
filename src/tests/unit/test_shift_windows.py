"""Ca SÁNG/CHIỀU đổi thành khoảng phút — mốc 12:00, nửa mở.

Luật lịch trực bản đầu chỉ dừng ở mức NGÀY, nên BS Thành chỉ trực ca sáng ngày
08/08 vẫn được lưới mời đặt lúc 18:00. Một luật đúng nửa vời còn khó chịu hơn
không có: nó tạo cảm giác đã được kiểm.

Mốc 12:00 là quyết định của phòng khám (Quang, 2026-08-04), không suy ra được
từ dữ liệu — nên nó phải nằm ở đúng một chỗ và được khoá lại ở đây.
"""

from __future__ import annotations

import pytest

from clinicai.core.shifts import (
    MORNING_END_MIN,
    covers,
    describe,
    merge_windows,
    shift_window,
)

OPEN, CLOSE = 8 * 60, 23 * 60  # ngày cuối tuần của Dr4Women: 08:00–23:00


class TestOneShiftBecomesOneWindow:
    def test_full_covers_the_whole_opening_hours(self) -> None:
        assert shift_window("FULL", OPEN, CLOSE) == (OPEN, CLOSE)

    def test_morning_stops_at_noon(self) -> None:
        assert shift_window("SANG", OPEN, CLOSE) == (OPEN, MORNING_END_MIN)

    def test_afternoon_starts_at_noon(self) -> None:
        assert shift_window("CHIEU", OPEN, CLOSE) == (MORNING_END_MIN, CLOSE)

    def test_noon_belongs_to_the_afternoon(self) -> None:
        """Nửa mở: 12:00 là khung đầu của ca chiều, không phải khung cuối ca sáng.

        Nếu cả hai ca cùng nhận mốc 12:00 thì một bác sĩ trực ca sáng sẽ nhận
        được một khung mà mình đã về — đúng một khung, mỗi ngày, mãi mãi.
        """
        morning = shift_window("SANG", OPEN, CLOSE)
        afternoon = shift_window("CHIEU", OPEN, CLOSE)
        assert morning is not None and afternoon is not None
        assert not covers([morning], MORNING_END_MIN)
        assert covers([afternoon], MORNING_END_MIN)

    def test_a_morning_shift_on_an_evening_only_day_is_empty(self) -> None:
        """Ngày thường mở 17:00–23:00 thì ca SÁNG không còn phút nào.

        Trả None chứ không trả một khoảng ngược (17:00–12:00), thứ mà `covers`
        sẽ lặng lẽ coi là rỗng ở một chỗ và có thể coi là cả ngày ở chỗ khác.
        """
        assert shift_window("SANG", 17 * 60, 23 * 60) is None

    def test_an_unknown_label_is_treated_as_all_day(self) -> None:
        """Sai theo hướng cho phép: một nhãn lạ không được khoá lịch của người
        đang thật sự đi làm."""
        assert shift_window("KHONG_BIET", OPEN, CLOSE) == (OPEN, CLOSE)


class TestADoctorIsTheUnionOfTheirShifts:
    def test_morning_at_one_station_and_afternoon_at_another_is_a_full_day(
        self,
    ) -> None:
        """Có thật trong dữ liệu: BS Thành 09/08 có cả SANG lẫn CHIEU."""
        windows = merge_windows(
            [
                w
                for s in ("SANG", "CHIEU")
                if (w := shift_window(s, OPEN, CLOSE)) is not None
            ]
        )
        # Hai ca kề nhau đúng mốc 12:00 ⇒ phải gộp thành MỘT khoảng liền, nếu
        # không thì đúng khung 12:00 rơi vào khe giữa hai khoảng.
        assert windows == [(OPEN, CLOSE)]
        assert covers(windows, MORNING_END_MIN)

    def test_duplicate_shifts_do_not_multiply(self) -> None:
        """Bác sĩ có ba dòng FULL (ba trạm) vẫn chỉ là một khoảng."""
        full = shift_window("FULL", OPEN, CLOSE)
        assert full is not None
        assert merge_windows([full, full, full]) == [(OPEN, CLOSE)]

    def test_no_shift_means_no_window(self) -> None:
        assert merge_windows([]) == []


class TestTheSentenceShownToTheUser:
    @pytest.mark.parametrize(
        "shift,expected",
        [("SANG", "08:00–12:00"), ("CHIEU", "12:00–23:00")],
    )
    def test_a_window_reads_like_a_clock(self, shift: str, expected: str) -> None:
        w = shift_window(shift, OPEN, CLOSE)
        assert w is not None
        assert describe([w]) == expected
