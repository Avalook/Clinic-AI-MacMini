"""Tests for the (preferred_time, date) → session_type mapper."""

from __future__ import annotations

from datetime import date

import pytest

from clinicai.graphs.scheduling.session_mapper import map_to_session_type

# 2026-05-25 is a Monday (weekday=0); 2026-05-30 is a Saturday (weekday=5);
# 2026-05-31 is a Sunday (weekday=6).
_MONDAY = date(2026, 5, 25)
_SATURDAY = date(2026, 5, 30)
_SUNDAY = date(2026, 5, 31)


@pytest.mark.parametrize(
    ("preferred_time", "day", "expected"),
    [
        ("evening", _MONDAY, "EVENING"),
        ("morning", _MONDAY, None),
        ("afternoon", _MONDAY, None),
        ("morning", _SATURDAY, "WEEKEND_MORNING"),
        ("afternoon", _SUNDAY, "WEEKEND_AFTERNOON"),
        ("evening", _SATURDAY, None),
    ],
)
def test_map_to_session_type(
    preferred_time: str, day: date, expected: str | None
) -> None:
    assert map_to_session_type(preferred_time, day) == expected
