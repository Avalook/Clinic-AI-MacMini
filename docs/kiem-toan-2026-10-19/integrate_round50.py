"""Integrate Round 50's static roster-history concurrency review."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
CODE_SUFFIXES = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html",
}


def load(name: str):
    return json.loads((ROOT / name).read_text())


def save(name: str, data) -> None:
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def source(path: str) -> tuple[bytes, list[str]]:
    raw = subprocess.check_output(["git", "show", f"{SHA}:{path}"], cwd=REPO)
    return raw, raw.decode("utf-8").splitlines()


def proof(path: str, start: int, end: int, detail: str) -> dict:
    raw, lines = source(path)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid pinned range {path}:{start}-{end} ({len(lines)} lines)")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "excerpt": "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1)),
        "detail": detail,
        "lines": len(lines),
    }


def main() -> None:
    findings = load("PHAT-HIEN.json")
    if any(item["id"] == "OPS-013" for item in findings):
        raise ValueError("OPS-013 already exists; refusing duplicate integration")

    specs = [
        ("supabase/migrations/20261006300000_lich_truc_phien_ban.sql", 30, 61,
         "Both immutable roster snapshots and per-row change records use txid_current() as the replay-order key."),
        ("supabase/migrations/20261006300000_lich_truc_phien_ban.sql", 94, 153,
         "Every work_roster INSERT/UPDATE/DELETE is logged by a trigger in its writer transaction, with txid assigned to the audit row."),
        ("supabase/migrations/20261006300000_lich_truc_phien_ban.sql", 155, 181,
         "Applying a roster week creates a whole-week snapshot from the statement's visible work_roster rows; the trigger does not take a shared per-week lock with row writers."),
        ("src/clinicai/services/lich_truc_phien_ban_service.py", 17, 20,
         "The service documents one version per transaction and explicitly reconstructs state by txid order."),
        ("src/clinicai/services/lich_truc_phien_ban_service.py", 139, 189,
         "Replay sorts snapshots and changes by transaction ID, then applies the resulting state in that order."),
        ("src/clinicai/services/lich_truc_phien_ban_service.py", 302, 317,
         "Both database reads order the history by txid and row ID."),
        ("src/clinicai/services/config_service.py", 187, 245,
         "A roster-row insert runs in its own transaction and locks a station row, but the reviewed path takes no lock shared with apply_week for this clinic/week."),
        ("src/clinicai/services/config_service.py", 1027, 1071,
         "apply_week reads the current roster then upserts roster_week, whose trigger snapshots work_roster; no per-week lock is taken before the read/snapshot."),
        ("src/tests/services/test_lich_truc_phien_ban_db.py", 82, 130,
         "The integration test covers sequential apply/add/change/remove/reapply history, not overlapping writers."),
        ("src/tests/services/test_lich_truc_phien_ban_db.py", 225, 388,
         "Remaining DB tests cover actor setting, moved weeks, auto-assignment, invalid weeks and route authorization; no concurrent transaction/history-order test is present. Tests were read-not-run."),
    ]

    finding = {
        "id": "OPS-013",
        "title": "Lịch sử lịch trực có thể sắp phiên bản sai thứ tự khi giao dịch chồng lấn",
        "severity": "LOW",
        "evidence_level": "confirmed_static",
        "category": "operations/roster-history-concurrency",
        "summary": "Sổ lịch trực và ảnh tuần được dựng theo txid_current() tăng dần. PostgreSQL cấp xid khi giao dịch ghi lần đầu, không theo thứ tự commit. Trong khi đó, sửa work_roster và thao tác apply_week không dùng cùng khóa theo clinic/week: nếu giao dịch sửa ca được cấp xid trước nhưng commit sau, còn apply_week chụp trạng thái cũ và commit trước, replay theo txid sẽ đặt sửa ca trước ảnh chụp. Ảnh chụp sau đó xóa thay đổi khỏi trạng thái dựng lại; phiên bản mới nhất trên màn lịch sử có thể không khớp work_roster hiện hành.",
        "trigger": "Hai giao dịch đồng thời trên cùng phòng khám/tuần: một giao dịch sửa hoặc xóa ca; giao dịch kia áp dụng lại tuần trong lúc thay đổi đầu chưa commit. Lỗi chỉ xuất hiện nếu thứ tự cấp xid khác thứ tự commit/ảnh chụp.",
        "impact": "Màn lịch sử có thể dựng ra thứ tự trạng thái không từng nhìn thấy như trạng thái đã commit, và ảnh mới nhất có thể cũ hơn lịch chính thức hiện hành. Điều này làm giảm độ tin cậy của dấu vết ai đổi gì và khi nào. Đây là khả năng suy ra từ mã và ngữ nghĩa giao dịch; chưa tái hiện bằng hai connection hay thấy xảy ra ở production.",
        "evidence": [],
        "validation": {
            "method": "read_only_exact_main_static_transaction_order_and_replay_trace",
            "command": None,
            "result": "Đối chiếu thứ tự replay, khóa giao dịch của hai nhóm writer, trigger chụp snapshot và các test lịch sử. PostgreSQL 17 docs xác nhận xid được cấp tuần tự khi giao dịch thực hiện lần ghi đầu tiên; xid thấp chỉ cho biết bắt đầu ghi trước, không chứng minh commit trước. Test DB hiện có là tuần tự và không có ca concurrency/history-order.",
            "limitations": "Static exact-main inference only. Không chạy DB, không mô phỏng hai giao dịch, không kết luận production đã gặp lỗi. Sự kiện cần giao dịch cùng tuần chồng lấn và thứ tự xid/commit đảo nhau; mức ảnh hưởng phụ thuộc tần suất áp dụng tuần đồng thời với sửa lịch.",
        },
        "recommendation": "Dùng một khóa giao dịch theo (clinic_id, week_start) cho tất cả thao tác sửa/xóa/thêm ca và apply/reapply tuần; lấy khóa trước khi đọc hoặc ghi roster để tuần tự hóa cả snapshot lẫn delta. Hoặc thay txid bằng thứ tự phiên bản được cấp dưới cùng khóa tuần tự hóa. Không dựa vào sequence hoặc timestamp cấp trước commit như thể đó là commit order.",
        "acceptance": "Trên DB dùng hoàn toàn dữ liệu synthetic, tạo hai connection có barrier để một ca sửa lịch đã ghi nhưng chưa commit trong khi thao tác apply tuần chạy; xác nhận thao tác được tuần tự hóa hoặc phiên bản phản ánh đúng commit order. Sau mỗi interleaving, so sánh trạng thái mới nhất của service lịch sử với work_roster và kiểm các mốc ảnh/reapply. Kiểm thêm hai writer độc lập cùng tuần; không chỉ test tuần tự.",
        "alignment": [
            "Lịch sử vận hành phản ánh đúng reality đã commit",
            "Ownership và thời điểm sửa lịch có thể tin cậy",
            "Phát hiện sớm lỗi phối hợp khi có thao tác đồng thời",
        ],
        "related_tests": [
            "src/tests/unit/test_lich_truc_phien_ban.py — pure replay tests were read; they validate sequential txid ordering, not concurrent commit order; not run.",
            "src/tests/services/test_lich_truc_phien_ban_db.py:82-130,225-388 — DB cases read; sequential writes, triggers and route authorization, no concurrency/history-order case; not run.",
        ],
        "source_hashes": {},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "History replay uses xid order while row writers and week snapshots are not serialized by one clinic/week lock. Concurrent commit-order inversion is inferred from PostgreSQL transaction semantics; no runtime reproduction is claimed.",
            "evidence": [],
        },
        "related_findings": ["INF-011"],
        "external_reference": "https://www.postgresql.org/docs/17/transaction-id.html",
    }
    for path, start, end, detail in specs:
        item = proof(path, start, end, detail)
        finding["evidence"].append({k: item[k] for k in ("path", "line", "end_line", "detail")})
        finding["main_validation"]["evidence"].append(
            {k: item[k] for k in ("path", "line", "end_line", "sha256", "excerpt")}
        )
        finding["source_hashes"][path] = item["sha256"]
    findings.append(finding)
    save("PHAT-HIEN.json", findings)

    coverage_specs = [
        ("src/clinicai/services/lich_truc_phien_ban_service.py", 1, 487,
         "Full-file read: version reconstruction and response projection; tests not run."),
        ("src/clinicai/services/config_service.py", 187, 245,
         "Targeted read: roster row writer transaction and station lock."),
        ("src/clinicai/services/config_service.py", 1027, 1088,
         "Targeted read: apply/reapply transaction and roster_week snapshot trigger."),
        ("src/clinicai/services/booking_service.py", 1625, 1645,
         "Targeted read: appointment auto-assignment roster writer uses transaction helper."),
        ("src/clinicai/api/v1/routers/config.py", 372, 395,
         "Targeted read: roster-history endpoint and authorization guard."),
        ("supabase/migrations/20261006300000_lich_truc_phien_ban.sql", 1, 201,
         "Full-file read: audit tables, txid fields, row triggers and whole-week snapshot trigger."),
        ("src/tests/unit/test_lich_truc_phien_ban.py", 1, 324,
         "Full-file read: pure sequential reconstruction and diff tests; not run."),
        ("src/tests/services/test_lich_truc_phien_ban_db.py", 1, 130,
         "Targeted read: fixtures and sequential apply/add/change/remove/reapply history test; not run."),
        ("src/tests/services/test_lich_truc_phien_ban_db.py", 225, 388,
         "Targeted read: remaining actor, move-week, auto-assignment, invalid-input and route tests; not run."),
    ]
    coverage_by_path: dict[str, dict] = {}
    for path, start, end, detail in coverage_specs:
        item = proof(path, start, end, detail)
        row = coverage_by_path.setdefault(path, {
            "path": path, "sha256": item["sha256"], "lines": item["lines"],
            "read_ranges": [], "full_read": False, "outcomes": [],
        })
        interval = {"start": start, "end": end}
        if interval not in row["read_ranges"]:
            row["read_ranges"].append(interval)
        if start == 1 and end == item["lines"]:
            row["full_read"] = True
        row["outcomes"].append(detail)
    coverage_items = []
    for row in coverage_by_path.values():
        row["read_ranges"].sort(key=lambda x: (x["start"], x["end"]))
        row["outcome"] = " ".join(row.pop("outcomes"))
        coverage_items.append(row)
    coverage = {
        "schema_version": 1,
        "round": 50,
        "report_version": "v0.73",
        "snapshot_sha": SHA,
        "mode": "read_only_exact_main_scoped_semantic_review",
        "scope": [
            "roster version audit tables and trigger ordering",
            "all identified roster-row writers compared with apply/reapply snapshot path",
            "history reconstruction and sequential tests",
        ],
        "method": "Immutable pinned Git blobs via git show. Recorded source ranges are line-checked and file SHA-256 checked. Tests were read-not-run. No ClinicAI application/runtime/API/DB/provider/VPS/production/secrets/PHI was accessed.",
        "result": {
            "new_findings": ["OPS-013"],
            "extended_findings": [],
            "deduplicated": [
                "The concern is specifically ordering between an uncommitted row delta and a concurrent whole-week snapshot; it is distinct from actor attribution, RLS and normal sequential replay coverage.",
                "The application may still display the current roster correctly from work_roster; OPS-013 is about the reconstructed history/latest-history view, and no current production mismatch is claimed.",
            ],
            "held_candidates": [],
            "full_source_audit_complete": False,
        },
        "full_files": [x for x in coverage_items if x["full_read"]],
        "targeted_traces": [x for x in coverage_items if not x["full_read"]],
        "reviewer_note": "Round 50 is a scoped static concurrency review of roster history, not runtime proof or a full roster audit. The possible order inversion is based on PostgreSQL xid semantics and the absence of a shared clinic/week lock in the reviewed writer paths.",
        "supporting_references": [
            {
                "title": "PostgreSQL 17 — Transactions and Identifiers",
                "url": "https://www.postgresql.org/docs/17/transaction-id.html",
                "supports": "Non-virtual xids are assigned sequentially when a transaction first writes; lower xids mean an earlier first write, not an earlier commit.",
            }
        ],
    }
    save("blocks/round50.coverage.json", coverage)
    (ROOT / "blocks/round50.md").write_text(
        f"""# Round 50 — roster-history ordering under concurrent writes

Source SHA: `{SHA}`. Review used immutable Git blobs via `git show`. Tests were read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- **Added OPS-013 LOW:** roster history replays whole-week snapshots and row changes by `txid_current()` ascending. PostgreSQL assigns an xid when a transaction first writes; that value does not establish commit order. `apply_week` snapshots `work_roster`, while row writers record trigger deltas in separate transactions, and the reviewed paths do not acquire one shared per-clinic/week lock before reading or writing.
- If a row edit receives the lower xid but remains uncommitted while a concurrent reapply snapshots the old visible row and commits first, replay applies the edit and then the older snapshot. The latest history can therefore disagree with the current `work_roster` state. This is a static concurrency inference; no DB interleaving was run and no production occurrence is claimed.
- Existing DB history cases are sequential; the examined tests contain no concurrent snapshot/edit ordering case. Tests were read-not-run.

## Recommendation and validation

Serialize every edit/add/remove/reassignment and apply/reapply operation with one transaction-level lock keyed by clinic and week, acquired before the roster read/write and snapshot. Alternatively use a version sequence whose allocation and mutation are protected by that same lock. Add a deterministic two-connection test with barriers, then assert the latest reconstructed state equals `work_roster` across every commit ordering.

PostgreSQL reference: [Transactions and Identifiers](https://www.postgresql.org/docs/17/transaction-id.html) documents that xids are allocated at first write and that lower xids indicate an earlier first write. Exact code ranges, hashes and read coverage are in `blocks/round50.coverage.json` and `PHAT-HIEN.json`. Full source audit remains incomplete.
"""
    )

    manifest = load("MAIN-PHAM-VI.json")
    for record in manifest["files"]:
        item = coverage_by_path.get(record["path"])
        if not item:
            continue
        if record.get("sha256") and record["sha256"] != item["sha256"]:
            raise ValueError(f"Manifest SHA mismatch for {record['path']}")
        if item["full_read"]:
            record["status"] = "read"
            record["full_file_read"] = True
        elif record["status"] in {"scanned", "inventoried"}:
            record["status"] = "traced"
        ranges = ", ".join(f"{x['start']}–{x['end']}" for x in item["read_ranges"])
        note = f"Round 50 exact-main {ranges}; see blocks/round50.coverage.json."
        if "Round 50 exact-main" not in record.get("method", ""):
            record["method"] = (record.get("method", "") + " | " + note).strip(" |")
        record["round50_note"] = item["outcome"]
    manifest["last_updated_round"] = 50
    save("MAIN-PHAM-VI.json", manifest)

    main_counts = Counter(x["status"] for x in manifest["files"])
    code_files = [x for x in manifest["files"] if Path(x["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(x["status"] for x in code_files)
    finding_counts = Counter(x["main_validation"]["status"] for x in findings)
    severity_counts = Counter(x["severity"] for x in findings)
    state = load("STATE.json")
    state.update({
        "updated_at": "2026-10-20",
        "status": "in_progress",
        "report_version": "v0.73",
        "phase": "round50_v073_roster_history_order_audit_open",
        "report_round_summary": "Round 50 adds OPS-013: roster-history replay can order a concurrent whole-week snapshot and row change differently from commit visibility; this is static and not runtime reproduced.",
        "next_action": "Continue exact-main review of unread/structurally scanned code, prioritizing object authorization, payment/refund/reconciliation invariants, clinical transitions, migrations/restore, retry receipts, freshness and worker recovery. Keep full_source_audit_complete=false until scope and validation gaps are actually closed.",
        "report_status": "Round 50 evidence integrated; v0.73 report-only QA and portable package refresh pending; full source audit remains incomplete.",
        "full_source_audit_complete": False,
        "round50": {
            "status": "integrated_static_review_report_qa_pending_audit_open",
            "notes": "blocks/round50.md",
            "coverage": "blocks/round50.coverage.json",
            "new_findings": ["OPS-013"],
            "extended_findings": [],
            "tests": "Roster-history unit and DB tests read-not-run; no concurrency test executed.",
            "runtime": "No ClinicAI app/API/DB/provider/VPS/production/secrets/PHI access.",
            "full_source_audit_complete": False,
            "targeted_paths": len(coverage_items),
            "full_file_reads": sum(1 for x in coverage_items if x["full_read"]),
        },
    })
    state["summary"]["findings"] = len(findings)
    state["summary"]["severity"] = {k: severity_counts[k] for k in ("HIGH", "MEDIUM", "LOW")}
    state["summary"]["main_status"] = {
        "still_present_on_main": finding_counts["still_present_on_main"],
        "partially_addressed_on_main": finding_counts["partially_addressed_on_main"],
        "addressed_on_main": finding_counts["addressed_on_main"],
    }
    state["summary"]["main_files"] = len(manifest["files"])
    state["summary"]["main_partial_traces"] = main_counts["traced"]
    state["summary"]["main_coverage"] = {k: main_counts[k] for k in ("inventoried", "traced", "read", "scanned", "excluded")}
    state["summary"]["code_like_source_files"] = {
        "definition": "Pinned-tree code/web/sql/shell suffixes; includes app, tests, tooling and styles.",
        "total": len(code_files),
        "coverage": {k: code_counts[k] for k in ("inventoried", "traced", "scanned", "read")},
    }
    state["limits"][0] = (
        f"Full source audit incomplete: {main_counts['inventoried']} inventoried, {main_counts['traced']} partially traced, {main_counts['scanned']} scanned and {main_counts['excluded']} excluded paths out of {len(manifest['files'])}. Path state is not behavioral coverage."
    )
    state["limits"][1] = (
        f"Code-like suffix group includes runtime, tests, tooling and styles; current path ledger: {code_counts['read']} read, {code_counts['traced']} partially traced, {code_counts['scanned']} scanned, {code_counts['inventoried']} inventoried and {code_counts['excluded']} excluded out of {len(code_files)}. This is not a percent-complete or correctness score."
    )
    state["artifacts"]["integration_script"] = "Round50 integrated; v0.73 report-only QA and audit-only ZIP refresh pending."
    state["artifacts"]["qa"] = "Pending v0.73 report-only validator and browser check; application behavior not validated."
    state["package"].update({"status": "pending", "file_count": None, "integrity": "Pending v0.73 rebuild after report QA and final handoff checkpoint."})
    state["portable_bundle_status"] = "Pending final v0.73 audit-only package rebuild and verification."
    save("STATE.json", state)

    summary = "Round 50 adds OPS-013 about possible xid/commit ordering inversion in concurrent roster history. The finding is static and un-reproduced; tests were read-not-run."
    (ROOT / "TIEP-TUC.md").write_text(
        "# CURRENT HANDOFF — v0.73, Round 50\n\n"
        f"Evidence source: immutable Git SHA `{SHA}` in `{REPO}`. Read source only with `git show <SHA>:<path>`; do not use working-tree WIP as evidence. Only edit audit artifacts here. Do not run ClinicAI runtime/API/DB/provider/VPS/production or inspect secrets/PHI.\n\n"
        f"{summary} Exact evidence and the PostgreSQL reference are in `blocks/round50.md`, `blocks/round50.coverage.json`, `PHAT-HIEN.json` and `MAIN-PHAM-VI.json`.\n\n"
        "Full source audit remains incomplete. Path counters are inventory states, not semantic coverage. v0.73 report-only QA and audit-only ZIP refresh are pending. Resume from `BAT-DAU-TU-DAY.md` and `STATE.json`.\n"
    )
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(
        "# Bắt đầu từ đây — checkpoint v0.73, Round 50\n\n"
        "Đọc `TIEP-TUC.md`, `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `blocks/round50.md` và `blocks/round50.coverage.json`. Source chỉ từ SHA `" + SHA + "` qua `git show` trong worktree audit.\n\n"
        f"{summary} Không chạy runtime/DB; tests read-not-run. v0.73 report/package QA pending.\n\n"
        "**Full source audit chưa hoàn tất.** Path counters không phải phần trăm đã hiểu hành vi; chỉ sửa audit artifacts. Tiếp tục theo `STATE.json.next_action`.\n"
    )
    with (ROOT / "NHAT-KY.md").open("a") as handle:
        handle.write(
            "\n\n## Round 50 — 20/10/2026, v0.73 integration\n\n"
            f"Static exact-main review at SHA `{SHA}`. Added OPS-013: roster-history replay may order a concurrent snapshot and roster delta by xid rather than commit visibility; no runtime/production occurrence is claimed. Related tests were read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact ranges and PostgreSQL reference are in `blocks/round50.coverage.json`; full source audit remains incomplete. Report-only QA/package refresh pending.\n"
        )
    print(f"Integrated Round 50: {len(findings)} findings; {len(coverage_items)} path coverage records; full audit remains open")


if __name__ == "__main__":
    main()
