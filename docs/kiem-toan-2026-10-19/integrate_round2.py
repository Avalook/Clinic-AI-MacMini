"""Merge durable round-two records after checking exact source evidence.

No network, probe execution or application changes. DB-002 stays in the canonical
PHAT-HIEN.json and is not overwritten by this round-two merge.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    """Validate source hashes and merge records by stable identifier."""
    manifest = json.loads((ROOT / "MAIN-PHAM-VI.json").read_text())
    source = Path(manifest["snapshot"])
    additions = json.loads((ROOT / "blocks/round2.findings.json").read_text())
    identifiers = [item["id"] for item in additions]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate round-two identifiers")
    for item in additions:
        if item["main_validation"]["sha"] != manifest["sha"]:
            raise ValueError("Mismatched reference version")
        for evidence in item["main_validation"]["evidence"]:
            path = (source / evidence["path"]).resolve()
            if not path.is_relative_to(source.resolve()):
                raise ValueError("Evidence outside snapshot")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != evidence["sha256"]:
                raise ValueError(f"Source changed: {evidence['path']}")
    findings = json.loads((ROOT / "PHAT-HIEN.json").read_text())
    retained = [item for item in findings if item["id"] not in identifiers]
    merged = retained + additions
    (ROOT / "PHAT-HIEN.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Integrated {len(merged)} evidence records")


if __name__ == "__main__":
    main()
