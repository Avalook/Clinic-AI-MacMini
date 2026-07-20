"""Pure unit tests for the T-TRANSFORM-01 core helpers.

These tests exercise the three identity-parsing functions the whole migration
hinges on — ``norm_phone``, ``norm_dob`` and ``extract_phone`` — with normal,
boundary, and malformed inputs. No DB, no filesystem, no network.

The transform module lives under ``scripts/`` (not an installed package), so it
is loaded by absolute path via ``importlib``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_transform() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "data_migration" / "transform.py"
    spec = importlib.util.spec_from_file_location("dm_transform", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve the module by name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


transform = _load_transform()


# --------------------------------------------------------------------------- #
# norm_phone                                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0988501997", "+84988501997"),  # canonical 10-digit national form
        ("84 988 501 997", "+84988501997"),  # 84 country code + spaces
        ("  0988-501-997 ", "+84988501997"),  # punctuation & padding stripped
        ("091125078", None),  # edge: only 9 digits (truncated) -> invalid
        ("8587173899", None),  # edge: foreign number, not VN 0-prefixed
        ("", None),  # edge: empty
        (None, None),  # edge: None
    ],
)
def test_norm_phone(raw: str | None, expected: str | None) -> None:
    assert transform.norm_phone(raw) == expected


# --------------------------------------------------------------------------- #
# norm_dob                                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20/06/1997 12:00 AM (GMT+7)", "1997-06-20"),  # full Notion timestamp
        ("01/01/1991", "1991-01-01"),  # bare date
        ("9/2/1985", "1985-02-09"),  # single-digit day/month
        ("32/13/2000", None),  # edge: impossible calendar date
        ("not a date", None),  # edge: no date token
        ("", None),  # edge: empty
        (None, None),  # edge: None
    ],
)
def test_norm_dob(raw: str | None, expected: str | None) -> None:
    assert transform.norm_dob(raw) == expected


# --------------------------------------------------------------------------- #
# extract_phone                                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[Reg 31] Vũ Thuý Phượng 0983473216 (https://x)", "+84983473216"),
        ("PK3350-1411-Tiến Thị Hải Yến  0917947099", "+84917947099"),
        (
            "first 0988501997 then 0911222333",
            "+84988501997",
        ),  # edge: returns the FIRST match only
        ("no number at all", None),  # edge: nothing to extract
        ("", None),  # edge: empty
        (None, None),  # edge: None
    ],
)
def test_extract_phone(text: str | None, expected: str | None) -> None:
    assert transform.extract_phone(text) == expected
