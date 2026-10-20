"""Integrate the round-9 AI runtime audit into the durable ledger."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SNAPSHOT = Path("/tmp/clinicai-audit-main-956ba4f2")
SNAPSHOT_SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
FULL_READ_DIRS = (
    "src/clinicai/tools",
    "src/clinicai/graphs",
    "src/clinicai/orchestrator",
    "src/clinicai/llm",
    "src/clinicai/event_bus",
)
PROOF_SPANS = {
    "AI-004": [
        ("src/clinicai/main.py", 154, 163),
        ("src/clinicai/main.py", 174, 181),
        ("src/clinicai/llm/anthropic_client.py", 73, 75),
        ("src/clinicai/llm/anthropic_client.py", 117, 155),
        ("src/clinicai/llm/chi_phi.py", 114, 127),
        ("src/clinicai/llm/chi_phi.py", 144, 174),
        ("src/clinicai/api/v1/routers/lab.py", 214, 219),
        ("src/clinicai/api/v1/routers/lab.py", 240, 258),
        ("src/clinicai/api/v1/routers/ops.py", 341, 351),
        ("src/tests/services/test_llm_chi_phi_db.py", 45, 53),
        ("src/tests/services/test_llm_chi_phi_db.py", 91, 111),
    ]
}
TARGETED_FILES = {
    "src/clinicai/main.py": ("targeted_semantic_read", ["154-163", "174-181"], "Lifespan client wiring and singleton injection; not a full file read."),
    "src/clinicai/api/v1/routers/lab.py": ("targeted_semantic_read", ["214-219", "240-258"], "LLM singleton dependency and triage callsite; router not fully reviewed."),
    "src/clinicai/api/v1/routers/ops.py": ("targeted_semantic_read", ["341-351"], "LLM cost dashboard data source; router not fully reviewed."),
    "src/tests/services/test_llm_chi_phi_db.py": ("full_semantic_read", ["1-198"], "Full test-file read; database tests not executed."),
    "src/tests/unit/test_llm_chi_phi.py": ("full_semantic_read", ["1-end"], "Full unit-test read; no app/DB integration implied."),
    "src/tests/llm/test_anthropic_client_unit.py": ("targeted_test_review", ["entire relevant LLM client suite scanned/read selectively"], "Client behavior tests reviewed for pool/no-pool distinction; no live provider."),
    "src/tests/graphs/lab_triage/test_lab_triage_skeleton.py": ("full_semantic_read", ["1-end"], "Full lab-triage skeleton test read; no production behavior implied."),
    "src/tests/services/orchestrator/test_orchestrator_endpoint.py": ("full_semantic_read", ["1-end"], "Full orchestrator API boundary test read."),
    "src/tests/services/orchestrator/test_graph_routing.py": ("full_semantic_read", ["1-end"], "Full graph-routing test read."),
    "src/tests/services/orchestrator/test_e2e_lab_triage.py": ("partial_semantic_read", ["main flow and related assertions"], "Selected test flow read; not full test-file review."),
    "src/tests/services/orchestrator/test_e2e_scheduling.py": ("partial_semantic_read", ["main flow and related assertions"], "Selected test flow read; not full test-file review."),
    "src/tests/graphs/task_manager/test_task_manager_graph.py": ("partial_semantic_read", ["main flow and related assertions"], "Selected test flow read; not full test-file review."),
    "supabase/migrations/20261009870000_llm_chi_phi.sql": ("targeted_semantic_read", ["1-35", "49-56"], "Cost ledger schema, comments, RLS and grants; migration not fully reviewed in this slice."),
}


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_evidence(path: str, start: int, end: int) -> dict:
    raw = (SNAPSHOT / path).read_bytes()
    lines = raw.decode("utf-8").splitlines()
    if start < 1 or end < start or end > len(lines):
        raise ValueError(f"invalid pinned-main span: {path}:{start}-{end}")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "excerpt": "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1)),
    }


def make_coverage() -> None:
    rows: dict[str, dict] = {}
    for directory in FULL_READ_DIRS:
        for path in sorted((SNAPSHOT / directory).rglob("*.py")):
            rel = path.relative_to(SNAPSHOT).as_posix()
            lines = path.read_text().splitlines()
            rows[rel] = {
                "path": rel,
                "sha256": file_hash(path),
                "lines": len(lines),
                "status": "full_semantic_read",
                "ranges": [f"1-{len(lines)}"],
                "notes": "Đọc trọn file trong lát AI runtime; không suy rộng sang caller ngoài danh sách.",
            }
    if len(rows) != 61:
        raise ValueError(f"expected 61 full-read AI runtime files, found {len(rows)}")

    for rel, (status, ranges, note) in TARGETED_FILES.items():
        path = SNAPSHOT / rel
        if not path.is_file():
            raise ValueError(f"missing targeted source: {rel}")
        prior = rows.get(rel)
        if prior is not None and prior["status"] == "full_semantic_read":
            continue
        rows[rel] = {
            "path": rel,
            "sha256": file_hash(path),
            "lines": len(path.read_text().splitlines()),
            "status": status,
            "ranges": ranges,
            "notes": note,
        }

    coverage = {
        "schema_version": 1,
        "snapshot_sha": SNAPSHOT_SHA,
        "snapshot_path": str(SNAPSHOT),
        "status": "complete_for_assigned_ai_runtime_slice",
        "scope": [
            "All Python files in tools, graphs, orchestrator, llm and event_bus were read in full.",
            "Selected FastAPI, migration and test paths were read at the spans noted below.",
            "Static source review only; no app, provider, DB, production or patient data access.",
        ],
        "findings_count": 1,
        "files": sorted(rows.values(), key=lambda row: row["path"]),
    }
    write_json("blocks/round9_ai_runtime.coverage.json", coverage)


def integrate_findings() -> list[dict]:
    canonical = read_json("PHAT-HIEN.json")
    by_id = {item["id"]: item for item in canonical}
    candidates = read_json("blocks/round9_ai_runtime.findings.json")
    if len({item["id"] for item in candidates}) != len(candidates):
        raise ValueError("duplicate candidate IDs in round9 AI findings")
    inserted = []
    for candidate in candidates:
        existing = by_id.get(candidate["id"])
        if existing:
            if existing.get("title") == candidate.get("title") and existing.get("source_hashes") == candidate.get("source_hashes") and existing.get("reference_version") == "pinned_main":
                continue
            raise ValueError(f"conflicting finding ID: {candidate['id']}")
        item = copy.deepcopy(candidate)
        item["evidence_level"] = "confirmed_static"
        item["reference_version"] = "pinned_main"
        item["status"] = "open"
        for path, expected in item["source_hashes"].items():
            actual = file_hash(SNAPSHOT / path)
            if actual != expected:
                raise ValueError(f"source hash mismatch: {item['id']} {path}")
        proofs = [source_evidence(*span) for span in PROOF_SPANS[item["id"]]]
        for proof in proofs:
            if item["source_hashes"].get(proof["path"]) != proof["sha256"]:
                raise ValueError(f"proof hash absent/mismatched: {item['id']} {proof['path']}")
        item["main_validation"] = {
            "sha": SNAPSHOT_SHA,
            "status": "still_present_on_main",
            "note": "Đối chiếu wiring và code exact-main cho thấy shared client production được khởi tạo không có pool; chưa xác minh cấu hình hoặc hành vi production.",
            "evidence": sorted(proofs, key=lambda proof: (proof["path"], proof["line"])),
            "production_verified": False,
        }
        canonical.append(item)
        by_id[item["id"]] = item
        inserted.append(item)
    write_json("PHAT-HIEN.json", canonical)
    return inserted


def merge_coverage() -> None:
    manifest = read_json("MAIN-PHAM-VI.json")
    by_path = {item["path"]: item for item in manifest["files"]}
    coverage = read_json("blocks/round9_ai_runtime.coverage.json")
    if coverage["snapshot_sha"] != SNAPSHOT_SHA:
        raise ValueError("AI coverage uses wrong snapshot")
    rank = {"inventoried": 0, "scanned": 1, "traced": 2, "read": 3}
    for row in coverage["files"]:
        item = by_path.get(row["path"])
        if item is None:
            continue
        if item.get("sha256") != row["sha256"]:
            raise ValueError(f"coverage hash mismatch: {row['path']}")
        target = "read" if row["status"] in {"full_semantic_read", "read", "traced_full"} else "traced"
        if item["status"] != "excluded" and rank[target] > rank.get(item["status"], 0):
            item["status"] = target
        method = f"Round 9: {row['status']}; slice-only, see blocks/round9_ai_runtime.coverage.json."
        if method not in item.get("method", ""):
            item["method"] = (item.get("method", "").rstrip(" |") + " | " + method).strip(" |")
    write_json("MAIN-PHAM-VI.json", manifest)


def update_checks(inserted: list[dict]) -> None:
    checks = read_json("KIEM-CHUNG.json")
    existing = {(row.get("id"), row.get("path")) for row in checks["checks"]}
    for finding in inserted:
        for path in finding["source_hashes"]:
            key = (finding["id"], path)
            if key not in existing:
                checks["checks"].append({"id": finding["id"], "path": path, "valid": True})
                existing.add(key)
    write_json("KIEM-CHUNG.json", checks)


def replace_section(text: str, heading_prefix: str, heading: str, body: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(heading_prefix)}.*?(?=^## |\Z)", re.S)
    replacement = f"{heading}\n\n{body.strip()}\n\n"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    return text.rstrip() + "\n\n" + replacement


def update_notes(findings: list[dict]) -> None:
    ids = ", ".join(item["id"] for item in findings) or "AI-004"
    note = (
        f"Checkpoint round 9 trên snapshot main ghim ({ids}). Đã đọc trọn 61 file trong "
        "tools, graphs, orchestrator, llm và event_bus; trace thêm wiring app, router "
        "lab/ops, migration và tests liên quan. AI-004 xác nhận bằng static trace rằng "
        "shared LLM client không được nối với meter; chưa kiểm app, DB, provider hay "
        "production. HTML v0.27 đã qua kiểm cấu trúc và browser QA; ZIP sẽ dựng lại sau khi "
        "nhập các lát đang chạy. Snapshot tiếp tục: " + SNAPSHOT_SHA + ". Full source audit vẫn đang làm."
    )
    diary = ROOT / "NHAT-KY.md"
    diary.write_text(replace_section(diary.read_text(), "## Round 9 —", "## Round 9 — AI runtime và ranh giới agent", note))

    for name in ("TIEP-TUC.md", "BAT-DAU-TU-DAY.md"):
        path = ROOT / name
        contents = path.read_text()
        contents = re.sub(r"(?m)^## Checkpoint mới nhất — round 9\n.*\Z", "", contents, flags=re.S)
        next_step = note + " Đọc `blocks/round9_ai_runtime.md`, `round9_ai_runtime.coverage.json` và `STATE.json`; sau đó tiếp tục các block agent, rồi rà phần code chưa kiểm. Không gọi trạng thái hiện tại là đã đọc hết code."
        if name == "TIEP-TUC.md":
            old = re.compile(r"(?m)^# CURRENT HANDOFF —.*?\n\n.*?(?=^## |\Z)", re.S)
            summary = (
                f"# CURRENT HANDOFF — v0.27 (19/10/2026)\n\n"
                f"Trạng thái canonical ở `STATE.json`: {len(read_json('PHAT-HIEN.json'))} hồ sơ; "
                "main exact SHA `" + SNAPSHOT_SHA + "`. v0.27 thêm AI-004 về metering/trần chi phí LLM; "
                "lát AI đọc trọn 61 file runtime được liệt kê, nhưng source audit toàn repo chưa xong. "
                "HTML và ZIP cần được dựng/kiểm lại sau khi nhập các block đang chạy. Khi đổi tài khoản, "
                "giữ repo cùng Git history tại SHA ghim; vào từ `BAT-DAU-TU-DAY.md` và dùng `STATE.json` "
                "làm nguồn tiến độ.\n\n"
            )
            contents = old.sub(summary, contents, count=1)
            if "## v0.27 mới tích hợp" not in contents:
                contents = contents.replace("## v0.25 mới tích hợp", "## v0.27 mới tích hợp\n\n" + next_step.strip() + "\n\n## v0.25 mới tích hợp", 1)
            else:
                contents = replace_section(contents, "## v0.27 mới tích hợp", "## v0.27 mới tích hợp", next_step)
        else:
            contents = re.sub(r"(?m)^# Trạng thái hiện hành —.*$", "# Trạng thái hiện hành — 19/10/2026, checkpoint v0.27", contents, count=1)
            first = re.compile(r"(?m)^Audit toàn code chưa xong\..*?(?=^## )", re.S)
            summary = (
                "Audit toàn code chưa xong. Canonical state: `docs/kiem-toan-2026-10-19/STATE.json`; "
                "findings: `PHAT-HIEN.json`; exact-main ledger: `MAIN-PHAM-VI.json`. Snapshot ghim `"
                + SNAPSHOT_SHA + "`; nguồn ở `/tmp/clinicai-audit-main-956ba4f2`, không dùng WIP làm bằng chứng main. "
                "v0.27 đã tích hợp AI-004 và 61 file AI runtime đọc trọn. Phải rebuild/QA HTML và ZIP sau khi "
                "nhập các lát còn chạy. Tài khoản Codex khác cần cùng repo và Git history tại SHA ghim; prompt tiếp quản nằm trong file này.\n\n"
            )
            contents = first.sub(summary, contents, count=1)
            if "## Checkpoint v0.27 — tiếp quản audit" not in contents:
                contents = contents.replace("## Checkpoint v0.25 — tiếp quản audit", "## Checkpoint v0.27 — tiếp quản audit\n\n" + next_step.strip() + "\n\n## Checkpoint v0.25 — tiếp quản audit", 1)
            else:
                contents = replace_section(contents, "## Checkpoint v0.27 — tiếp quản audit", "## Checkpoint v0.27 — tiếp quản audit", next_step)
        path.write_text(contents)


def update_state(inserted: list[dict], audit_content_changed: bool) -> None:
    state = read_json("STATE.json")
    manifest = read_json("MAIN-PHAM-VI.json")
    findings = read_json("PHAT-HIEN.json")
    files = manifest["files"]
    coverage = Counter(item["status"] for item in files)
    suffixes = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html"}
    code_files = [item for item in files if Path(item["path"]).suffix.lower() in suffixes]
    code_coverage = Counter(item["status"] for item in code_files)
    severity = Counter(item["severity"] for item in findings)
    levels = Counter(item["evidence_level"] for item in findings)
    main_status = Counter(item["main_validation"]["status"] for item in findings)
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")

    state["updated_at"] = now
    state["status"] = "in_progress"
    state["phase"] = "round9_ai_runtime_and_parallel_source_audit"
    state["next_action"] = (
        "Round 9 AI runtime slice is integrated. Merge only exact-main, hash-verified outputs from the active API, dashboard and migration blocks; then continue unreviewed modules. Rebuild and verify HTML/ZIP after the parallel blocks land. Full source audit remains incomplete."
    )
    if audit_content_changed:
        state["report_status"] = f"v0.27_{len(findings)}_findings_report_QA_pending_after_round9; full source audit incomplete"
    state["limits"][0] = (
        f"Full source audit incomplete: {coverage['inventoried']} inventoried, {coverage['traced']} partial traces, "
        f"{coverage['scanned']} scanned, {coverage['excluded']} excluded; traced is not full-file semantic review."
    )
    round9_limit = (
        "Round 9 AI-004 is a confirmed static trace of the FastAPI shared LLM client wiring and meter guard; no app/provider/DB/production call was made. Concurrency overrun is inferred from separate check-before-call and write-after-call operations, not dynamically reproduced. The 61 full-file reads cover AI tools/graphs/orchestration/LLM/event_bus only."
    )
    if round9_limit not in state["limits"]:
        state["limits"].append(round9_limit)
    state["summary"].update(
        findings=len(findings),
        severity=dict(severity),
        evidence_levels=dict(levels),
        main_status=dict(main_status),
        main_files=len(files),
        main_partial_traces=coverage["traced"],
        main_coverage=dict(coverage),
        main_read_files=coverage["read"],
        new_findings_v027=["AI-004"],
        code_like_source_files={
            "definition": state["summary"]["code_like_source_files"]["definition"],
            "total": len(code_files),
            "coverage": dict(code_coverage),
            "traced_is_partial": True,
        },
    )
    state["blocks"]["integration"].update(
        status="round9_ai_runtime_static_slice_complete_full_integration_audit_open",
        findings="PHAT-HIEN.json (AI-001..AI-004)",
        coverage="blocks/round9_ai_runtime.coverage.json",
        next="AI-004: app singleton does not receive DB meter; pool-enabled guard is non-atomic. Validate startup wiring/concurrency on isolated tests after audit; continue cross-module failure paths.",
    )
    state["blocks"]["ai_runtime"] = {
        "status": "round9_assigned_slice_complete_repository_audit_incomplete",
        "notes": "blocks/round9_ai_runtime.md",
        "findings": "PHAT-HIEN.json (AI-004; AI-001..003 remain prior integration findings)",
        "coverage": "blocks/round9_ai_runtime.coverage.json",
        "next": "Add startup wiring, concurrent reservation and meter-failure tests; review unexamined API/UI callers before claiming complete AI behavior coverage.",
    }
    state["artifacts"]["integration_script"] = "integrate_v027.py"
    if audit_content_changed:
        state["artifacts"]["qa"] = "HTML-QA.json; pending v0.27 build/structural/browser QA and ZIP regeneration"
        for key in ("html_sha256", "html_checked_at", "bundle_verified_at", "bundle_entries", "bundle_outer_sha256"):
            state["artifacts"].pop(key, None)
        state["artifacts"]["bundle_integrity"] = "Pending regeneration after active audit blocks are integrated."
    write_json("STATE.json", state)


def update_report_template() -> None:
    path = ROOT / "report.template.html"
    contents = path.read_text()
    contents = contents.replace("Bản 0.25; audit toàn code còn tiếp tục.", "Bản 0.27; audit toàn code còn tiếp tục.")
    contents = contents.replace("v0.25", "v0.27")
    contents = contents.replace("BẢN 0.24 — CHƯA PHẢI", "BẢN 0.27 — CHƯA PHẢI")
    contents = re.sub(
        r"Checkpoint v0\.27 thêm INF-017.*?</p>",
        "Checkpoint v0.27 thêm AI-004: shared LLM client trong app không nhận DB meter, nên trần và ledger không áp dụng; check-then-call cũng có race khi chạy đồng thời. Đây là static trace trên main ghim, chưa kiểm bằng app/DB/provider/production. Toàn cây đã được kiểm kê/quét; chỉ một phần code được đọc trọn hoặc truy vết sâu. Có probe local và đối chiếu main ở các lát trước; chưa chạy full CI, E2E toàn ứng dụng hoặc phục hồi đầy đủ. Trang ghi giới hạn để người tiếp quản thấy phần còn thiếu.</p>",
        contents,
        count=1,
        flags=re.S,
    )
    contents = contents.replace("file trace một phần; 12 file khác đã được đọc trọn", "file trace một phần; @@P28@@ file đã được đọc trọn")
    contents = contents.replace("Bản 0.25; audit toàn code chưa hoàn tất.", "Bản 0.27; audit toàn code chưa hoàn tất.")
    path.write_text(contents)


def main() -> None:
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"pinned source snapshot is missing: {SNAPSHOT}")
    before_findings = file_hash(ROOT / "PHAT-HIEN.json")
    before_manifest = file_hash(ROOT / "MAIN-PHAM-VI.json")
    make_coverage()
    inserted = integrate_findings()
    merge_coverage()
    audit_content_changed = (
        bool(inserted)
        or before_findings != file_hash(ROOT / "PHAT-HIEN.json")
        or before_manifest != file_hash(ROOT / "MAIN-PHAM-VI.json")
    )
    update_checks(inserted)
    update_state(inserted, audit_content_changed)
    update_notes(inserted)
    update_report_template()
    print(f"Integrated {len(inserted)} findings: {', '.join(item['id'] for item in inserted) or '(already integrated)'}")


if __name__ == "__main__":
    main()
