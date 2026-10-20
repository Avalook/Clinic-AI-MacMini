"""Create a deterministic, portable bundle of audit artifacts only."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "tiep-quan-clinicai-2026-10-19.zip"
MANIFEST = ROOT / "MANIFEST-GOI.json"
ARCHIVE_ROOT = "kiem-toan-2026-10-19"


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    """Archive all audit artifacts except the self-referential outputs."""
    files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path not in {BUNDLE, MANIFEST}
        and ".DS_Store" not in path.parts
        and "__pycache__" not in path.parts
    )
    entries = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files
    ]
    with zipfile.ZipFile(
        BUNDLE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in files:
            info = zipfile.ZipInfo(
                f"{ARCHIVE_ROOT}/{path.relative_to(ROOT).as_posix()}",
                date_time=(2026, 10, 19, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bundle_sha256": sha256(BUNDLE),
        "scope": (
            "Audit artifacts, selected synthetic probes and logs only; no repository, "
            "Git history, environment files, secrets, patient data, or production payloads. "
            "The manifest and ZIP exclude themselves. Keep repository/history separately "
            "to continue source review on another machine."
        ),
        "self_excluded": True,
        "files": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Created {BUNDLE} with {len(entries)} files")


if __name__ == "__main__":
    main()
