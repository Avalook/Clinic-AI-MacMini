"""Verify the portable audit ZIP against its SHA-256 manifest."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "tiep-quan-clinicai-2026-10-19.zip"
MANIFEST = ROOT / "MANIFEST-GOI.json"
ARCHIVE_ROOT = "kiem-toan-2026-10-19"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    archive_hash = sha256(BUNDLE.read_bytes())
    if archive_hash != manifest["bundle_sha256"]:
        raise SystemExit("Outer ZIP SHA-256 does not match manifest")
    with zipfile.ZipFile(BUNDLE) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"ZIP CRC failure: {bad}")
        members = set(archive.namelist())
        expected = {f"{ARCHIVE_ROOT}/{x['path']}" for x in manifest["files"]}
        if members != expected:
            missing = sorted(expected - members)
            extra = sorted(members - expected)
            raise SystemExit(f"ZIP member mismatch; missing={missing[:5]} extra={extra[:5]}")
        for item in manifest["files"]:
            name = f"{ARCHIVE_ROOT}/{item['path']}"
            data = archive.read(name)
            if len(data) != item["bytes"] or sha256(data) != item["sha256"]:
                raise SystemExit(f"Member size/hash mismatch: {item['path']}")
    print(f"Verified {len(manifest['files'])} files; CRC and member SHA-256 pass; outer SHA-256 {archive_hash}")


if __name__ == "__main__":
    main()
