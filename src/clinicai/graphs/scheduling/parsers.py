"""Pure Vietnamese natural input parsers — regex + keyword match, no LLM."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Literal, Optional

TimeSlot = Literal["morning", "afternoon", "evening"]

_EXPLICIT_DATE_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?")
_TIME_NUMERIC_RE = re.compile(r"(\d{1,2})[h:](\d{0,2})")

_WEEKDAY_MAP: dict[str, int] = {
    "thứ 2": 0,
    "thứ hai": 0,
    "thứ 3": 1,
    "thứ ba": 1,
    "thứ 4": 2,
    "thứ tư": 2,
    "thứ 5": 3,
    "thứ năm": 3,
    "thứ 6": 4,
    "thứ sáu": 4,
    "thứ 7": 5,
    "thứ bảy": 5,
    "chủ nhật": 6,
}

_POSITIVE_TOKENS: set[str] = {"có", "ok", "vâng", "ừ", "đúng", "yes", "y", "co"}
_NEGATIVE_TOKENS: set[str] = {"không", "no", "hủy", "thôi", "n", "khong"}


def parse_date(text: str) -> Optional[str]:
    """Parse Vietnamese date phrases → ISO YYYY-MM-DD. None nếu không nhận diện."""
    if not text:
        return None
    s = text.lower().strip()
    today = date.today()

    m = _EXPLICIT_DATE_RE.search(s)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    tokens = s.split()

    if "ngày kia" in s or "kia" in tokens:
        return (today + timedelta(days=2)).isoformat()
    if "ngày mai" in s or "mai" in tokens:
        return (today + timedelta(days=1)).isoformat()
    if "hôm nay" in s or "nay" in tokens:
        return today.isoformat()

    for kw, wd in _WEEKDAY_MAP.items():
        if kw in s:
            diff = (wd - today.weekday()) % 7
            if diff == 0:
                diff = 7
            return (today + timedelta(days=diff)).isoformat()

    return None


def parse_time_slot(text: str) -> Optional[TimeSlot]:
    """Parse khung giờ Vietnamese → 'morning'|'afternoon'|'evening'."""
    if not text:
        return None
    s = text.lower().strip()

    if "sáng" in s or "morning" in s:
        return "morning"
    if "chiều" in s or "afternoon" in s:
        return "afternoon"
    if "tối" in s or "evening" in s:
        return "evening"

    m = _TIME_NUMERIC_RE.search(s)
    if m:
        try:
            hour = int(m.group(1))
        except ValueError:
            return None
        if 0 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour <= 23:
            return "evening"

    return None


def parse_yes_no(text: str) -> Optional[bool]:
    """Parse xác nhận VN. True/False/None nếu không rõ."""
    if not text:
        return None
    s = text.lower().strip()
    tokens = set(s.split())

    if tokens & _NEGATIVE_TOKENS:
        return False
    if "đồng ý" in s:
        return True
    if tokens & _POSITIVE_TOKENS:
        return True
    return None
