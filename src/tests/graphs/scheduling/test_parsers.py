from datetime import date, timedelta

import pytest

from clinicai.graphs.scheduling.parsers import (
    parse_date,
    parse_time_slot,
    parse_yes_no,
)


@pytest.mark.parametrize(
    "phrase, delta_days",
    [
        ("mai", 1),
        ("hôm nay", 0),
        ("ngày kia", 2),
    ],
)
def test_parse_date_relative(phrase: str, delta_days: int):
    expected = (date.today() + timedelta(days=delta_days)).isoformat()
    assert parse_date(phrase) == expected


@pytest.mark.parametrize(
    "phrase, expected",
    [
        ("25/05", f"{date.today().year}-05-25"),
        ("25-05-2026", "2026-05-25"),
    ],
)
def test_parse_date_explicit(phrase: str, expected: str):
    assert parse_date(phrase) == expected


def test_parse_date_fail():
    assert parse_date("lúc nào cũng được") is None


@pytest.mark.parametrize(
    "phrase, expected",
    [
        ("sáng", "morning"),
        ("chiều mai", "afternoon"),
        ("9h", "morning"),
        ("14h30", "afternoon"),
    ],
)
def test_parse_time_slot(phrase: str, expected: str):
    assert parse_time_slot(phrase) == expected


def test_parse_time_slot_fail():
    assert parse_time_slot("không biết") is None


@pytest.mark.parametrize(
    "phrase, expected",
    [
        ("có", True),
        ("ok", True),
        ("không", False),
        ("hủy", False),
        ("abc", None),
    ],
)
def test_parse_yes_no(phrase: str, expected):
    assert parse_yes_no(phrase) is expected
