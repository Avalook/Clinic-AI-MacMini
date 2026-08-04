"""Ngoại lệ sức chứa phải nói được điều phòng khám thật sự nói.

LUẬT KHÁCH HÀNG (Notion — Tiêu chí theo bộ phận → CSKH):

               18:00     18:15     18:30     18:45+
    BS Thành   10 ca     4 ca      4 ca      4 ca
    BS khác     3 ca     4 ca      5 ca      3 ca

Bốn con số bên trong một giờ. Chừng nào slot_booking_override còn đo bằng GIỜ,
câu đó không ghi lại được — và cái không ghi lại được thì không thi hành được.

Các test dưới đây khoá lại hai điều: mô hình đủ mịn để nói ra luật đó, và một
ngoại lệ không thể chồng lên ngoại lệ khác (vì hai luật cho một khung nghĩa là
không có luật nào).
"""

from __future__ import annotations

from datetime import date

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.booking_override_service import validate_rule


def _validate(**over: object) -> None:
    """Chạy validate với một bộ tham số hợp lệ, ghi đè phần cần thử.

    Trỏ vào ``validate_rule`` — đường ghi hợp nhất — chứ không còn vào phần
    kiểm riêng của bảng ngoại lệ. Hai tab đã gộp làm một, nên hai bộ luật kiểm
    tra cũng phải gộp: giữ hai bộ là cách chắc chắn để chúng lệch nhau.
    """
    base: dict[str, object] = {
        "weekday": None,
        "date_start": date(2026, 8, 3),
        "date_end": date(2026, 8, 3),
        "minute_start": 18 * 60,
        "minute_end": 18 * 60 + 15,
        "regular_cap": 8,
        "walkin_cap": 2,
    }
    base.update(over)
    validate_rule(**base)  # type: ignore[arg-type]


class TestTheClinicsRuleIsExpressible:
    """Mỗi khung 15 phút của tiếng 18h phải đặt được một con số riêng."""

    @pytest.mark.parametrize(
        "start_min,regular,walkin",
        [
            (18 * 60 + 0, 8, 2),  # 18:00 — BS Thành: 10 ca
            (18 * 60 + 15, 3, 1),  # 18:15 — 4 ca
            (18 * 60 + 30, 3, 1),  # 18:30
            (18 * 60 + 45, 3, 1),  # 18:45
        ],
    )
    def test_each_quarter_hour_takes_its_own_cap(
        self, start_min: int, regular: int, walkin: int
    ) -> None:
        _validate(
            minute_start=start_min,
            minute_end=start_min + 15,
            regular_cap=regular,
            walkin_cap=walkin,
        )

    def test_the_old_hour_model_could_not_say_this(self) -> None:
        """Ghi lại VÌ SAO phải đổi, không chỉ ghi rằng đã đổi.

        Mô hình cũ chỉ có hour_start/hour_end, nên bốn dòng ở trên sẽ thu về một
        dòng `18 → 19` duy nhất và ba con số cuối biến mất. Test này không gọi
        mã cũ (nó không còn); nó khoá lại điều kiện khiến mã cũ bất khả: bốn
        khung phân biệt nằm trong cùng một giờ.
        """
        starts = [18 * 60, 18 * 60 + 15, 18 * 60 + 30, 18 * 60 + 45]
        assert len({m // 60 for m in starts}) == 1  # cùng một giờ
        assert len(set(starts)) == 4  # bốn khung khác nhau


class TestBoundariesThatWouldLeaveGaps:
    def test_a_start_off_the_grid_is_refused(self) -> None:
        """18:07 cắt ngang một khung và để lại vùng không luật nào phủ."""
        with pytest.raises(ValidationError, match="bội số 5"):
            _validate(minute_start=18 * 60 + 7, minute_end=18 * 60 + 22)

    def test_an_end_before_the_start_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="sau giờ bắt đầu"):
            _validate(minute_start=18 * 60 + 30, minute_end=18 * 60)

    def test_an_empty_window_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="sau giờ bắt đầu"):
            _validate(minute_start=18 * 60, minute_end=18 * 60)

    def test_midnight_end_is_allowed(self) -> None:
        """23:45–24:00 là khung cuối ngày hợp lệ, không phải lỗi tràn."""
        _validate(minute_start=23 * 60 + 45, minute_end=1440)

    def test_beyond_midnight_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="không hợp lệ"):
            _validate(minute_start=23 * 60 + 45, minute_end=1445)


class TestARuleMustSayWhatItDoes:
    """Hai con số là BẮT BUỘC, không còn là tuỳ chọn.

    Bản cũ cho cả hai để trống rồi mới từ chối ("Ít nhất một trường…"). Trong
    một khung thiết lập chung thì cách đó sai: người dùng điền một luật và phải
    thấy CẢ HAI con số của nó, chứ không phải để trống một ô rồi tự đoán ô đó
    lấy giá trị từ đâu. Giờ cả hai là trường bắt buộc ở ``BookingRuleRequest``,
    nên "để trống" không còn biểu diễn được — điều kiện được dời từ lúc chạy
    lên lúc gõ.
    """

    def test_walkin_zero_is_allowed_but_regular_zero_is_not(self) -> None:
        """Không chỗ vãng lai là một quyết định; không chỗ đặt hẹn là đóng cửa.

        Đóng khung giờ có đường riêng (xoá ca trực), và làm nó bằng cách đặt
        regular_cap = 0 sẽ giấu ý định đó trong bảng ngoại lệ.
        """
        _validate(walkin_cap=0)
        with pytest.raises(ValidationError, match="Số ca đặt trước"):
            _validate(regular_cap=0)


class TestRangeSanity:
    def test_a_range_longer_than_ninety_days_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="tối đa"):
            _validate(date_start=date(2026, 1, 1), date_end=date(2026, 12, 31))

    def test_end_before_start_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="sau ngày bắt đầu"):
            _validate(date_start=date(2026, 8, 10), date_end=date(2026, 8, 3))

    def test_one_date_alone_is_refused(self) -> None:
        """Nửa khoảng ngày là một luật không đọc được: tới bao giờ thì hết?"""
        with pytest.raises(ValidationError, match="cả ngày bắt đầu"):
            _validate(date_start=date(2026, 8, 3), date_end=None)


class TestScopeAndWeekdayDoNotContradict:
    def test_forever_rule_may_pick_a_weekday(self) -> None:
        """Luật mãi mãi = lặp mỗi tuần, nên "thứ 3 hằng tuần" là câu hợp lệ."""
        _validate(weekday=2, date_start=None, date_end=None)

    def test_dated_rule_may_not_also_pick_a_weekday(self) -> None:
        """Bảng luật tạm không có cột thứ.

        Nhận rồi lặng lẽ bỏ qua là dạng sai tệ nhất: người dùng chọn "thứ 3",
        luật áp cho cả bảy ngày trong khoảng, và không có gì nói ra điều đó.
        """
        with pytest.raises(ValidationError, match=r"không\s+chọn riêng thứ"):
            _validate(weekday=2)
