"""Recreate the pinned read-only source snapshot from existing local Git objects.

No fetch, checkout, reset, application edits, database calls or secret loading.
"""

from __future__ import annotations

import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
PATHS = [
    "src",
    "supabase",
    "scripts",
    "caddy",
    "docker",
    "monitoring",
    "CLAUDE.md",
    "AGENTS.md",
    "pyproject.toml",
    "poetry.lock",
    "pytest.ini",
    "docker-compose.yml",
    "docker-compose.supabase.yml",
    "docker-compose.staging.yml",
    ".env.prod.example",
    "docs/DANG-LAM.md",
    "docs/KIEM-TOAN-API-ROUTES-20261019.md",
    "docs/KIEM-TOAN-KHO-THUOC-VAT-TU-20261019.md",
]


def main() -> None:
    """Extract only the recorded paths from an immutable, locally available SHA."""
    manifest = json.loads((AUDIT / "MAIN-PHAM-VI.json").read_text())
    target = Path(manifest["snapshot"])
    if target.exists():
        raise RuntimeError(
            "Snapshot path already exists; verify its hashes instead of overwriting it"
        )
    subprocess.run(["git", "cat-file", "-e", SHA + "^{commit}"], cwd=ROOT, check=True)
    archive = subprocess.check_output(["git", "archive", SHA, "--", *PATHS], cwd=ROOT)
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(target, filter="data")
    print(target)


if __name__ == "__main__":
    main()
