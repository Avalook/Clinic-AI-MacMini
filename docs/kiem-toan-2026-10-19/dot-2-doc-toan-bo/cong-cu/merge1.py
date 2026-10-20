"""Bước 1 gộp: đọc mọi out/<chunk>.json, kiểm dẫn chứng dòng theo Git blob ghim, ghi new-findings.json.

Kiểm dẫn chứng: mỗi evidence {path, line, end_line} phải nằm trong tệp ở SHA ghim. Gắn cờ `evidence_ok`
(đủ dẫn chứng hợp lệ) và lưu excerpt + sha256 của tệp cho dẫn chứng hợp lệ. Không sửa dữ liệu của agent.
"""
import hashlib, json, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

SP = Path(__file__).resolve().parent
OUT = SP / "out"
REPO = "/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini"
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
_cache: dict[str, tuple[str, list[str]] | None] = {}


def blob(path: str):
    if path not in _cache:
        try:
            raw = subprocess.check_output(["git", "-C", REPO, "show", f"{SHA}:{path}"], stderr=subprocess.DEVNULL)
            _cache[path] = (hashlib.sha256(raw).hexdigest(), raw.decode("utf-8", errors="replace").splitlines())
        except subprocess.CalledProcessError:
            _cache[path] = None
    return _cache[path]


def check_evidence(ev):
    good, bad = [], []
    for e in ev or []:
        p, a = e.get("path"), e.get("line")
        b = e.get("end_line") or a
        info = blob(p) if isinstance(p, str) else None
        if info is None or not isinstance(a, int) or not isinstance(b, int) or not (1 <= a <= b <= len(info[1])):
            bad.append(e)
            continue
        b = min(b, a + 59)  # trích tối đa 60 dòng
        good.append({**e, "end_line": e.get("end_line") or a, "sha256": info[0],
                     "excerpt": "\n".join(f"{n}: {info[1][n-1]}" for n in range(a, b + 1))})
    return good, bad


def main():
    files = sorted(p for p in OUT.glob("*.json") if p.stem[0] in "ST" and p.stem[1:].isdigit())
    findings, ext, held, good, cov = [], [], [], [], []
    per = Counter()
    for p in files:
        d = json.loads(p.read_text())
        ch = d.get("chunk") or p.stem
        for f in d.get("findings", []):
            f["tmp_id"] = f.get("tmp_id") or f"{ch}-?"
            f["chunk"] = ch
            g, b = check_evidence(f.get("evidence"))
            f["evidence_checked"] = g
            f["evidence_invalid"] = b
            f["evidence_ok"] = bool(g) and not b
            findings.append(f)
            per[ch] += 1
        ext += [{**x, "chunk": ch} for x in d.get("extensions", [])]
        held += [{**x, "chunk": ch} for x in d.get("held", [])]
        good += [{**x, "chunk": ch} for x in d.get("good_patterns", [])]
        cov += [{**x, "chunk": ch} for x in d.get("coverage", [])]
    (SP / "out" / "new-findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=1))
    (SP / "out" / "new-extensions.json").write_text(json.dumps(ext, ensure_ascii=False, indent=1))
    (SP / "out" / "new-held.json").write_text(json.dumps(held, ensure_ascii=False, indent=1))
    (SP / "out" / "new-good.json").write_text(json.dumps(good, ensure_ascii=False, indent=1))
    (SP / "out" / "new-coverage.json").write_text(json.dumps(cov, ensure_ascii=False, indent=1))
    sev = Counter(f.get("severity") for f in findings)
    n_ev = sum(len(f["evidence_checked"]) + len(f["evidence_invalid"]) for f in findings)
    n_ok = sum(len(f["evidence_checked"]) for f in findings)
    print(f"chunk đã có: {len(files)}; phát hiện thô: {len(findings)} {dict(sev)}")
    print(f"dẫn chứng: {n_ok}/{n_ev} khớp dòng/tệp ở SHA ghim; phát hiện có đủ dẫn chứng hợp lệ: {sum(f['evidence_ok'] for f in findings)}")
    print(f"extensions {len(ext)}, held {len(held)}, mẫu tốt {len(good)}, dòng coverage {len(cov)}")
    print("theo chunk:", dict(sorted(per.items())))


if __name__ == "__main__":
    main()
