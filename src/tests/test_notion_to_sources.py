"""Unit tests for the Notion → sources adapter.

The adapter has two seams worth covering deterministically without
hitting the real API:

* ``prop_to_str`` — the typed-property → string converter. One test per
  property type the live clone uses, plus the ``formula(string)`` nested
  case (the most common shape in the clone) and the unknown-type
  fallback.
* ``page_to_row`` — confirms every property name comes through verbatim
  AND that the two synthetic ``_notion_*`` keys are attached.

End-to-end pulls (``notion_to_sources``) are smoke-tested by running
``scripts/data_import/sync_to_supabase.py --dry-run`` — they need real
Notion creds, so they live outside pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from data_import.notion_to_sources import page_to_row, prop_to_str  # noqa: E402


def _title(text: str) -> dict[str, object]:
    return {"type": "title", "title": [{"plain_text": text}]}


def _rich(text: str) -> dict[str, object]:
    return {"type": "rich_text", "rich_text": [{"plain_text": text}]}


def _select(name: str) -> dict[str, object]:
    return {"type": "select", "select": {"name": name}}


def _date(iso: str | None) -> dict[str, object]:
    return {"type": "date", "date": {"start": iso} if iso else None}


def test_title_concats_segments() -> None:
    prop = {
        "type": "title",
        "title": [{"plain_text": "BS "}, {"plain_text": "Thành"}],
    }
    assert prop_to_str(prop) == "BS Thành"


def test_rich_text_concats() -> None:
    assert prop_to_str(_rich("Phụ khoa")) == "Phụ khoa"


def test_number_str() -> None:
    assert prop_to_str({"type": "number", "number": 42}) == "42"


def test_select_returns_name() -> None:
    assert prop_to_str(_select("Phụ khoa")) == "Phụ khoa"


def test_multi_select_joined() -> None:
    p = {
        "type": "multi_select",
        "multi_select": [{"name": "Điều dưỡng sản"}, {"name": "Lễ tân"}],
    }
    assert prop_to_str(p) == "Điều dưỡng sản, Lễ tân"


def test_date_only_iso_converts_to_csv_format() -> None:
    """ISO-8601 ``yyyy-mm-dd`` → ``dd/mm/yyyy`` for ``norm_dob`` compatibility."""
    assert prop_to_str(_date("1986-06-26")) == "26/06/1986"


def test_date_with_time_converts_to_vn_csv_format() -> None:
    """Datetime with offset → ``dd/mm/yyyy HH:MM (GMT+7)`` for
    ``parse_datetime_vn``."""
    assert prop_to_str(_date("2026-05-28T18:00:00+07:00")) == "28/05/2026 18:00 (GMT+7)"


def test_date_midnight_drops_time_component() -> None:
    assert prop_to_str(_date("2026-05-28T00:00:00+07:00")) == "28/05/2026"


def test_date_unparseable_passes_through() -> None:
    assert prop_to_str(_date("not-a-date")) == "not-a-date"


def test_date_empty() -> None:
    assert prop_to_str(_date(None)) == ""


def test_formula_string_unwrapped() -> None:
    p = {"type": "formula", "formula": {"type": "string", "string": "[A☀️] 11.00"}}
    assert prop_to_str(p) == "[A☀️] 11.00"


def test_formula_null_collapses_empty() -> None:
    p = {"type": "formula", "formula": {"type": "string", "string": None}}
    assert prop_to_str(p) == ""


def test_formula_number() -> None:
    p = {"type": "formula", "formula": {"type": "number", "number": 30}}
    assert prop_to_str(p) == "30"


def test_relation_lists_ids() -> None:
    p = {
        "type": "relation",
        "relation": [{"id": "uuid-a"}, {"id": "uuid-b"}],
    }
    assert prop_to_str(p) == "uuid-a, uuid-b"


def test_unique_id_concats() -> None:
    p = {
        "type": "unique_id",
        "unique_id": {"prefix": "PK", "number": 9871},
    }
    assert prop_to_str(p) == "PK9871"


def test_place_address_field() -> None:
    """File khách hàng / Địa chỉ is type=place — extract the address string."""
    p = {
        "type": "place",
        "place": {"address": "Bắc Ninh, Vietnam", "name": "Bắc Ninh"},
    }
    assert prop_to_str(p) == "Bắc Ninh, Vietnam"


def test_place_name_fallback_when_no_address() -> None:
    p = {"type": "place", "place": {"name": "Hà Nội"}}
    assert prop_to_str(p) == "Hà Nội"


def test_place_empty() -> None:
    assert prop_to_str({"type": "place", "place": None}) == ""


def test_unknown_type_returns_empty() -> None:
    # A future Notion type — adapter must not crash; just collapses to "".
    assert prop_to_str({"type": "synced_block", "synced_block": {}}) == ""


def test_page_to_row_includes_all_props_verbatim() -> None:
    page = {
        "id": "page-001",
        "last_edited_time": "2026-05-28T10:00:00.000Z",
        "properties": {
            "Name": _title("BS Thành"),
            "Phòng khám": _select("Kim Ngưu"),
            "Ngày giờ hẹn": _date("2026-05-28T18:00:00+07:00"),
        },
    }
    row = page_to_row(page)
    assert row["Name"] == "BS Thành"
    assert row["Phòng khám"] == "Kim Ngưu"
    # Adapter normalizes Notion ISO → CSV-shaped datetime for the
    # canonical transform.
    assert row["Ngày giờ hẹn"] == "28/05/2026 18:00 (GMT+7)"
    assert row["_notion_page_id"] == "page-001"
    assert row["_notion_last_edited"] == "2026-05-28T10:00:00.000Z"


def test_page_to_row_preserves_vietnamese_property_names() -> None:
    """``transform.py`` reads by exact key — emoji + tone marks must survive."""
    page = {
        "id": "p1",
        "last_edited_time": "",
        "properties": {
            "//sdt (neat)": _rich("0987654321"),
            "🔑File hành chính": {"type": "relation", "relation": []},
            "Tóm tắt bệnh nhân": {
                "type": "formula",
                "formula": {"type": "string", "string": "Notion 1"},
            },
        },
    }
    row = page_to_row(page)
    assert row["//sdt (neat)"] == "0987654321"
    assert row["🔑File hành chính"] == ""
    assert row["Tóm tắt bệnh nhân"] == "Notion 1"
