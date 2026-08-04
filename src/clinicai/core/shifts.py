"""Ca trực SÁNG/CHIỀU/CẢ NGÀY đổi thành khoảng phút trong ngày.

``work_roster.shift`` là một trong ba nhãn: ``FULL``, ``SANG``, ``CHIEU``. Ba
nhãn đó nói về thời gian, nhưng KHÔNG có chỗ nào trong hệ thống nói sáng kết
thúc lúc mấy giờ — nên trước đây luật lịch trực chỉ dừng ở mức NGÀY, và một bác
sĩ chỉ trực ca sáng vẫn được mời đặt lịch lúc 18:00.

MỐC 12:00 LÀ QUYẾT ĐỊNH CỦA PHÒNG KHÁM (Quang, 2026-08-04), không phải một con
số suy ra được từ dữ liệu. Nó nằm ở đúng một chỗ — hằng số ngay dưới — vì nó sẽ
là thứ đầu tiên phòng khám thứ hai muốn đổi.

Đầu và cuối ngày lấy theo GIỜ MỞ CỬA của phòng khám hôm đó, không phải 00:00 và
24:00: ca sáng của một ngày mở cửa lúc 17:00 là một khoảng rỗng, và nói ra điều
đó đúng hơn là lặng lẽ cho phép đặt lúc 8 giờ sáng.
"""

from __future__ import annotations

# Sáng kết thúc — cũng là lúc chiều bắt đầu. Nửa mở, cùng quy ước với mọi
# khoảng phút khác trong hệ thống: một khung bắt đầu đúng 12:00 là ca CHIỀU.
MORNING_END_MIN = 12 * 60

Window = tuple[int, int]


def shift_window(shift: str, open_min: int, close_min: int) -> Window | None:
    """Khoảng phút mà một ca trực phủ, trong giờ mở cửa của ngày đó.

    Trả về ``None`` khi ca đó không còn phút nào — ví dụ ca SÁNG của một ngày
    chỉ mở cửa từ 17:00. Không phải lỗi, chỉ là một ca không có giờ nào.
    """
    if shift == "FULL":
        lo, hi = open_min, close_min
    elif shift == "SANG":
        lo, hi = open_min, min(close_min, MORNING_END_MIN)
    elif shift == "CHIEU":
        lo, hi = max(open_min, MORNING_END_MIN), close_min
    else:
        # Nhãn lạ: coi như cả ngày thay vì lặng lẽ bỏ qua. Một ca không đọc
        # được mà biến mất sẽ khoá lịch của một bác sĩ đang thật sự đi làm —
        # sai theo hướng đó tệ hơn hẳn.
        lo, hi = open_min, close_min
    return (lo, hi) if hi > lo else None


def merge_windows(windows: list[Window]) -> list[Window]:
    """Gộp các khoảng chồng/kề nhau thành danh sách rời nhau, đã sắp xếp.

    Một bác sĩ có thể có nhiều dòng trong lịch trực cùng một ngày — ở nhiều
    trạm khác nhau, và ca có thể khác nhau (SÁNG ở trạm này, CHIỀU ở trạm kia).
    Bác sĩ đó có mặt trong HỢP của các ca, nên phải gộp trước khi hỏi.
    """
    if not windows:
        return []
    out: list[Window] = []
    for lo, hi in sorted(windows):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def covers(windows: list[Window], minute: int) -> bool:
    """Mốc phút này có nằm trong ca trực nào không (nửa mở ``[lo, hi)``)."""
    return any(lo <= minute < hi for lo, hi in windows)


def describe(windows: list[Window]) -> str:
    """Các ca thành câu đọc được, để đưa thẳng vào thông báo cho người dùng."""

    def hhmm(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    return ", ".join(f"{hhmm(lo)}–{hhmm(hi)}" for lo, hi in windows)
