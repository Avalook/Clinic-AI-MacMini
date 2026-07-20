"""Unit tests for the pure helpers in ``sync_to_supabase``.

The integration end (Notion pull + Supabase writes) is verified by running
``scripts/data_import/sync_to_supabase.py --dry-run`` against the live
clone — these tests cover only the parts that have no I/O so a CI run
without secrets can still catch regressions.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from data_import.sync_to_supabase import (  # noqa: E402
    _STATUS_MAP,
    _nn,
    _parse_date,
    _parse_dt,
    _resolve_doctor,
    _resolve_service,
)

# --------------------------------------------------------------------------- #
# _nn — null-or-trimmed                                                       #
# --------------------------------------------------------------------------- #


def test_nn_none() -> None:
    assert _nn(None) is None


def test_nn_empty_string() -> None:
    assert _nn("") is None


def test_nn_whitespace_only() -> None:
    assert _nn("   \n\t") is None


def test_nn_strips_and_returns() -> None:
    assert _nn("  hello  ") == "hello"


# --------------------------------------------------------------------------- #
# _parse_date / _parse_dt                                                     #
# --------------------------------------------------------------------------- #


def test_parse_date_iso() -> None:
    assert _parse_date("1986-06-26") == date(1986, 6, 26)


def test_parse_date_iso_with_time_truncates() -> None:
    assert _parse_date("2026-05-28T18:00:00+07:00") == date(2026, 5, 28)


def test_parse_date_garbage_returns_none() -> None:
    assert _parse_date("oops") is None


def test_parse_date_none_passes_through() -> None:
    assert _parse_date(None) is None


def test_parse_dt_iso_with_tz() -> None:
    parsed = _parse_dt("2026-05-28T18:00:00+07:00")
    assert isinstance(parsed, datetime)
    assert parsed.year == 2026 and parsed.month == 5 and parsed.day == 28
    assert parsed.hour == 18


def test_parse_dt_garbage_returns_none() -> None:
    assert _parse_dt("not-a-datetime") is None


# --------------------------------------------------------------------------- #
# Master-data resolvers                                                       #
# --------------------------------------------------------------------------- #


def _master() -> dict[str, object]:
    """Build a tiny master-lookup dict shaped like ``_resolve_master`` output."""
    phu_khoa = uuid.uuid4()
    free = uuid.uuid4()
    bs_thanh = uuid.uuid4()
    bs_hung = uuid.uuid4()
    return {
        "location_id": uuid.uuid4(),
        "service_by_name": {"phụ khoa": phu_khoa, "free": free},
        "default_service": free,
        "doctor_by_name": {"bs thành": bs_thanh, "bs hùng": bs_hung},
    }


def test_resolve_service_hit() -> None:
    m = _master()
    out = _resolve_service("Phụ khoa", m)
    assert out == m["service_by_name"]["phụ khoa"]


def test_resolve_service_case_insensitive() -> None:
    m = _master()
    assert _resolve_service("PHỤ KHOA", m) == m["service_by_name"]["phụ khoa"]


def test_resolve_service_unknown_falls_back_to_default() -> None:
    m = _master()
    assert _resolve_service("Loại lạ", m) == m["default_service"]


def test_resolve_service_empty_falls_back_to_default() -> None:
    m = _master()
    assert _resolve_service("", m) == m["default_service"]


def test_resolve_doctor_hit() -> None:
    m = _master()
    assert _resolve_doctor("BS Thành", m) == m["doctor_by_name"]["bs thành"]


def test_resolve_doctor_case_insensitive_with_spaces() -> None:
    m = _master()
    assert _resolve_doctor("  bs hùng ", m) == m["doctor_by_name"]["bs hùng"]


def test_resolve_doctor_empty_returns_none() -> None:
    m = _master()
    assert _resolve_doctor("", m) is None


def test_resolve_doctor_unknown_returns_none() -> None:
    """Unknown doctor → NULL (the appointment FK is nullable)."""
    m = _master()
    assert _resolve_doctor("BS Không Tồn Tại", m) is None


# --------------------------------------------------------------------------- #
# _STATUS_MAP — sanity                                                        #
# --------------------------------------------------------------------------- #


def test_status_map_known_labels() -> None:
    assert _STATUS_MAP["Đã đến"] == "COMPLETED"
    assert _STATUS_MAP["Không đến"] == "NO_SHOW"
    assert _STATUS_MAP["Chưa đến"] == "SCHEDULED"


def test_status_map_empty_defaults_scheduled() -> None:
    # An empty cell on Notion should not get a non-scheduled status.
    assert _STATUS_MAP[""] == "SCHEDULED"
