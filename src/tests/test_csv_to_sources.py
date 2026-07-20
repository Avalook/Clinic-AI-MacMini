"""Unit tests for the CSV → sources adapter (``csv_to_sources``).

The full bundle PK sent lives outside the repo, so these tests build a
tiny synthetic CSV tree in a temp dir to exercise:

* the 5 expected folders and the ``_all.csv`` preference,
* row-level normalisation (missing cells → empty strings),
* the ``limit_per_source`` cap.

End-to-end (real CSV → real Supabase) is verified by running
``scripts/data_import/sync_to_supabase.py --source csv``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from data_import.csv_to_sources import (  # noqa: E402
    DATASETS,
    _pick_all_csv,
    csv_to_sources,
)


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        fh.write(",".join(header) + "\n")
        for r in rows:
            fh.write(",".join(r) + "\n")


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """Build the minimal folder shape PK ships."""
    for key, folder in DATASETS.items():
        d = tmp_path / folder
        _write_csv(
            d / f"sample_{key}_all.csv",
            ["*ID", "Name"],
            [[f"{key}-1", f"sample {key}"]],
        )
        # Also a base CSV so ``_pick_all_csv`` proves it picks ``_all``.
        _write_csv(d / "sample_base.csv", ["*ID"], [["should-be-ignored"]])
    return tmp_path


def test_pick_all_csv_prefers_all_suffix(bundle: Path) -> None:
    folder = bundle / DATASETS["admin"]
    chosen = _pick_all_csv(folder)
    assert chosen.name.endswith("_all.csv")


def test_pick_all_csv_falls_back_to_any_csv(tmp_path: Path) -> None:
    folder = tmp_path / "fallback"
    _write_csv(folder / "only_base.csv", ["x"], [["1"]])
    assert _pick_all_csv(folder).name == "only_base.csv"


def test_pick_all_csv_no_files_raises(tmp_path: Path) -> None:
    folder = tmp_path / "empty"
    folder.mkdir()
    with pytest.raises(FileNotFoundError):
        _pick_all_csv(folder)


def test_csv_to_sources_returns_five_keys(bundle: Path) -> None:
    sources = csv_to_sources(csv_root=bundle)
    assert set(sources.keys()) == set(DATASETS.keys())
    for key in DATASETS:
        assert len(sources[key]) == 1
        assert sources[key][0]["*ID"] == f"{key}-1"


def test_csv_to_sources_limit_caps_per_source(tmp_path: Path) -> None:
    for key, folder in DATASETS.items():
        rows = [[f"{key}-{i}", "x"] for i in range(50)]
        _write_csv(tmp_path / folder / "data_all.csv", ["*ID", "Name"], rows)
    sources = csv_to_sources(csv_root=tmp_path, limit_per_source=10)
    for k, v in sources.items():
        assert len(v) == 10, f"{k} should be capped at 10"


def test_csv_to_sources_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        csv_to_sources(csv_root=tmp_path / "does-not-exist")


def test_csv_to_sources_missing_dataset_folder_raises(
    tmp_path: Path,
) -> None:
    """Only some folders present — clear error, not silent skip."""
    _write_csv(
        tmp_path / DATASETS["admin"] / "x_all.csv",
        ["*ID"],
        [["a-1"]],
    )
    with pytest.raises(FileNotFoundError, match="missing dataset folder"):
        csv_to_sources(csv_root=tmp_path)


def test_csv_to_sources_normalises_missing_cells(tmp_path: Path) -> None:
    """A row shorter than the header should give empty strings, not Nones."""
    for key, folder in DATASETS.items():
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
        with (tmp_path / folder / "data_all.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as fh:
            fh.write("a,b,c\n")
            fh.write("1,2\n")  # row missing 'c'
    sources = csv_to_sources(csv_root=tmp_path)
    for key, rows in sources.items():
        # csv.DictReader sets the missing column's value to None by
        # default — the adapter must coerce it to "".
        assert rows[0].get("c") == "", (
            f"{key}: expected empty string for missing column, got {rows[0]!r}"
        )
