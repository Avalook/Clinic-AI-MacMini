"""Integrate the Round 49 read-only payment-ledger review."""
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
    if any(item["id"] == "FIN-020" for item in findings):
        raise ValueError("FIN-020 already exists; refusing duplicate integration")

    specs = [
        ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 123, 141,
         "The split check permits either both amounts NULL or both greater than zero, but SQL CHECK treats a NULL result as passing; one-sided NULL with method_moi='TRANSFER' yields NULL."),
        ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 143, 182,
         "The trigger only checks the total when tien_mat is non-NULL; when the transfer leg is NULL, the sum comparison is NULL and PL/pgSQL IF does not raise."),
        ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 186, 204,
         "The effective-payment reader emits a split whenever tien_mat is non-NULL, including a NULL transfer amount; with cash leg NULL it instead emits one full-amount method."),
        ("supabase/migrations/20260930500000_doi_hinh_thuc_thu.sql", 130, 138,
         "The table grants INSERT to service_role, so the database constraint/trigger is the final protection for privileged internal writers."),
        ("src/clinicai/api/v1/routers/payment.py", 322, 355,
         "The public API accepts the two split values as optional floats and forwards them to the service."),
        ("src/clinicai/services/doi_hinh_thuc_service.py", 105, 125,
         "The current service path correctly requires both split values to be numeric and positive and their rounded sum to equal the cycle amount."),
        ("src/clinicai/services/doi_hinh_thuc_service.py", 255, 312,
         "The API service calls doc_chia before INSERT, so this malformed one-sided row is not reachable through the reviewed normal endpoint."),
        ("src/clinicai/services/doi_hinh_thuc_service.py", 326, 343,
         "The only application INSERT reviewed writes both split columns from the validated tuple, or NULL for both."),
        ("src/clinicai/services/phan_thu.py", 149, 178,
         "The read parser converts a NULL so_tien to zero; a malformed persisted split can therefore present as an incomplete tender breakdown."),
        ("src/tests/services/test_doi_hinh_thuc_db.py", 263, 310,
         "The DB test checks append-only, stale-method and cancelled-cycle guards, but has no direct INSERT test for either one-sided split shape; read-not-run."),
        ("src/tests/services/test_thu_nhieu_hinh_thuc_db.py", 204, 218,
         "A valid two-leg change is tested with both positive amounts; no malformed one-sided leg is exercised; read-not-run."),
        ("src/tests/unit/test_doi_hinh_thuc.py", 10, 50,
         "The pure unit test covers validation helpers but does not import or test doc_chia; read-not-run."),
    ]

    finding = {
        "id": "FIN-020",
        "title": "Ràng buộc DB có thể nhận sổ đổi hình thức chỉ có một phần tiền",
        "severity": "LOW",
        "evidence_level": "confirmed_static",
        "category": "finance/database-invariant",
        "summary": "CHECK payment_cycle_doi_hinh_thuc_chia cho phép (tien_mat=NULL, chuyen_khoan>0) hoặc (tien_mat>0, chuyen_khoan=NULL) khi method_moi='TRANSFER': nhánh thứ hai của CHECK thành UNKNOWN thay vì FALSE, mà PostgreSQL CHECK chấp nhận UNKNOWN. Trigger chỉ kiểm tổng khi tien_mat IS NOT NULL; nếu chuyen_khoan NULL, phép cộng/so sánh cũng UNKNOWN nên không raise. Đường API hiện tại gọi doc_chia và chặn thiếu một vế trước INSERT, vì vậy chưa thấy request hiện hành tạo được hàng lỗi; đây là lỗ hổng của invariant cuối ở DB đối với service_role/internal writer.",
        "trigger": "Một writer có quyền service_role INSERT trực tiếp bản ghi đổi hình thức sang TRANSFER nhưng chỉ truyền một trong hai cột tien_mat/chuyen_khoan.",
        "impact": "DB có thể lưu split không đầy đủ dù migration mô tả trigger là lưới cuối. Nếu tien_mat có giá trị nhưng chuyen_khoan NULL, phan_thu_hieu_luc trả một leg chuyển khoản với so_tien NULL và doc_phan_db quy leg đó về 0; nếu tien_mat NULL, reader coi dòng là một hình thức đơn với toàn bộ amount. Các phép tính/hiển thị breakdown sau đó có thể không phản ánh ý định split. Chưa có đường API hiện tại được chứng minh đi qua hàng lỗi, và chưa tái hiện trên DB.",
        "evidence": [],
        "validation": {
            "method": "read_only_exact_main_static_database_constraint_and_writer_trace",
            "command": None,
            "result": "Đối chiếu CHECK, trigger, grant service_role INSERT, writer API/service và projection đọc. Writer API hiện tại validate cả hai phần; lỗi nằm ở khả năng DB constraint/trigger chấp nhận shape lệch khi một privileged writer bypasses helper. DB tests hiện có kiểm một số guard nhưng không có negative case one-sided split.",
            "limitations": "Static exact-main; không chạy SQL/DB test, không thử direct service_role INSERT, không quan sát production. Chưa thấy writer ứng dụng hiện hành ngoài service đã validate; vì vậy không kết luận đã có dữ liệu lỗi hoặc người dùng có thể gọi trực tiếp đường này.",
        },
        "recommendation": "Sửa CHECK để bắt buộc hai cột cùng NULL hoặc cùng NOT NULL và đều >0, đồng thời chỉ cho phép method_moi='TRANSFER' khi có split. Trong trigger, kiểm tra NULL hai vế tường minh và dùng IS DISTINCT FROM cho tổng so với amount. Thêm DB tests khẳng định mỗi shape một-vế bị từ chối, hai-vế hợp lệ được nhận, tổng sai bị từ chối.",
        "acceptance": "Trên disposable DB, INSERT với (tien_mat=NULL, chuyen_khoan>0), (tien_mat>0, chuyen_khoan=NULL), split không phải TRANSFER và split sai tổng đều bị từ chối; hai NULL cho một hình thức đơn và hai phần dương có tổng đúng vẫn hợp lệ. API hiện tại tiếp tục trả validation error cho input thiếu một vế.",
        "alignment": [
            "Bằng chứng tài chính nhất quán ở mọi lớp",
            "Lỗi lặp lại biến thành rào chắn dữ liệu",
            "Đối soát không phải suy đoán từ projection sai",
        ],
        "related_tests": [
            "src/tests/services/test_doi_hinh_thuc_db.py:263-310 — đọc, không chạy; kiểm append-only/stale method/status/clinic nhưng không kiểm hai shape split một-vế.",
            "src/tests/services/test_thu_nhieu_hinh_thuc_db.py:204-218 — đọc, không chạy; kiểm split hai vế hợp lệ, chưa kiểm một vế NULL.",
            "src/tests/unit/test_doi_hinh_thuc.py:10-50 — đọc, không chạy; không import/test doc_chia.",
        ],
        "source_hashes": {},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "The exact-main CHECK/trigger expression can pass a one-sided NULL split. The reviewed API/service path validates both values, so no current route-level reproduction or production observation is claimed.",
            "evidence": [],
        },
        "related_findings": ["FIN-010"],
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
        ("src/clinicai/services/doi_hinh_thuc_service.py", 1, 396, "Full-file read: current payment-method-change service."),
        ("src/clinicai/api/v1/routers/payment.py", 322, 355, "Targeted read: split-payment request schema and route."),
        ("src/dashboard/app/api/payment/route.ts", 113, 122, "Targeted read: Next proxy mapping."),
        ("src/dashboard/app/(dashboard)/thu-ngan/DoiHinhThuc.tsx", 1, 225, "Full-file read: cashier UI and request lifecycle."),
        ("src/dashboard/lib/hinh-thuc-thu.ts", 1, 73, "Full-file read: VND input parser and tender helpers."),
        ("src/tests/unit/test_doi_hinh_thuc.py", 1, 180, "Full-file read: pure helper tests; not run."),
        ("src/tests/services/test_doi_hinh_thuc_db.py", 1, 329, "Full-file read: DB integration cases for payment-method changes; not run."),
        ("src/tests/services/test_thu_nhieu_hinh_thuc_db.py", 204, 218, "Targeted read: valid two-part method-change case; not run."),
        ("supabase/migrations/20260930500000_doi_hinh_thuc_thu.sql", 1, 138, "Full-file read: ledger schema, base guard and grants."),
        ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 1, 40, "Targeted read: migration intent and invariant design."),
        ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 123, 208, "Targeted read: nullable split columns, CHECK, trigger and effective tender projection."),
        ("src/clinicai/services/phan_thu.py", 149, 178, "Targeted read: NULL amount normalization in tender parser."),
    ]
    coverage_by_path: dict[str, dict] = {}
    for path, start, end, detail in coverage_specs:
        item = proof(path, start, end, detail)
        row = coverage_by_path.setdefault(path, {
            "path": path,
            "sha256": item["sha256"],
            "lines": item["lines"],
            "read_ranges": [],
            "full_read": False,
            "outcomes": [],
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
        "round": 49,
        "report_version": "v0.72",
        "snapshot_sha": SHA,
        "mode": "read_only_exact_main_scoped_semantic_review",
        "scope": [
            "payment method change transaction and authorization",
            "split tender DB constraints, trigger and effective-payment projection",
            "current API writer and existing tests for valid/invalid operations",
        ],
        "method": "Immutable pinned Git blobs via git show. Recorded source ranges are line-checked and file SHA-256 checked. Tests were read-not-run. No application code, ClinicAI tests/runtime/API/DB/provider/VPS/production/secrets/PHI was touched.",
        "result": {
            "new_findings": ["FIN-020"],
            "extended_findings": [],
            "deduplicated": [
                "Fractional VND values are rounded by the service and the UI parser; absent a policy showing that this changes a valid whole-VND operation, it remains a held input-contract observation rather than a second finding.",
                "The current service validates both split legs before INSERT; the FIN-020 impact is limited to the DB guard's privileged-writer boundary and is not described as a current API exploit.",
                "Method-change locking, stale-method conflict handling, refund/void restrictions and same-command replay were present in the reviewed path; no separate race/replay finding was added from this slice.",
            ],
            "held_candidates": [
                "doc_chia accepts floats and rounds them although its docstring says integer amounts; current UI also rounds VND input. No material whole-VND loss or owner policy was established, so no finding was added.",
            ],
            "full_source_audit_complete": False,
        },
        "full_files": [x for x in coverage_items if x["full_read"]],
        "targeted_traces": [x for x in coverage_items if not x["full_read"]],
        "reviewer_note": "Round 49 is a scoped static payment-integrity review, not a full finance audit or runtime validation. FIN-020 identifies an incomplete database invariant; the current FastAPI path validates the omitted case.",
    }
    save("blocks/round49.coverage.json", coverage)
    (ROOT / "blocks/round49.md").write_text(
        f"""# Round 49 — payment method-change ledger guard

Source SHA: `{SHA}`. Review used immutable Git blobs via `git show`. Tests were read only and not run. No ClinicAI app, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- **Added FIN-020 LOW:** the split-payment CHECK can evaluate to SQL `UNKNOWN` for a one-sided NULL row; PostgreSQL accepts a CHECK result that is not false. The trigger checks the total only when `tien_mat` is non-NULL, and a NULL transfer leg makes the sum comparison unknown too. The effective-payment reader can then surface a NULL/zero transfer leg or interpret the row as a single tender. The table grants INSERT to `service_role`, so the database guard does not fully enforce the intended invariant for privileged writers.
- The reviewed HTTP route calls `doc_chia`, which requires both legs positive before INSERT. No current user/API path to malformed rows was found, and no DB reproduction or production issue is claimed. Severity is LOW because the defect is at the privileged-writer/defense-in-depth boundary.
- This shares PostgreSQL NULL-in-CHECK mechanics with FIN-010 but protects a distinct tender-breakdown invariant and requires a separate migration/test, so it remains a separate record.

## Dedupe and limits

The method-change transaction locks the payment cycle, checks current effective tender/refund/status, and records the event and audit row in the same transaction. Existing tests cover valid split writes, replay of the current tender, stale method, void/refund guards and clinic scope. Tests were read-not-run. Fractional VND rounding is held because both UI and service round whole-dong input and no material loss was established. Full source audit remains incomplete.

Exact code ranges, hashes and test coverage are in `blocks/round49.coverage.json`; the main finding includes excerpts in `PHAT-HIEN.json`.
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
        note = f"Round 49 exact-main {ranges}; see blocks/round49.coverage.json."
        if "Round 49 exact-main" not in record.get("method", ""):
            record["method"] = (record.get("method", "") + " | " + note).strip(" |")
        record["round49_note"] = item["outcome"]
    manifest["last_updated_round"] = 49
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
        "report_version": "v0.72",
        "phase": "round49_v072_payment_split_db_guard_audit_open",
        "report_round_summary": "Round 49 adds FIN-020: a one-sided NULL split can pass the payment-change DB CHECK/trigger, though the reviewed API writer validates both legs.",
        "next_action": "Continue exact-main review of unread/structurally scanned code, prioritizing high-impact object authorization, payment/refund/reconciliation invariants, clinical transitions, migrations/restore, retry receipts and freshness. Keep full_source_audit_complete=false until scope and validation gaps are actually closed.",
        "report_status": "Round 49 evidence integrated; v0.72 report-only QA and portable package refresh pending; full source audit remains incomplete.",
        "full_source_audit_complete": False,
        "round48": {**state.get("round48", {}), "status": "report_qa_and_package_verified_audit_open"},
        "round49": {
            "status": "integrated_static_review_report_qa_pending_audit_open",
            "notes": "blocks/round49.md",
            "coverage": "blocks/round49.coverage.json",
            "new_findings": ["FIN-020"],
            "extended_findings": [],
            "tests": "Payment method-change unit/DB tests read-not-run; no ClinicAI tests executed in Round 49.",
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
    state["artifacts"]["integration_script"] = "Round49 integrated; v0.72 report-only QA and audit-only ZIP refresh pending."
    state["artifacts"]["qa"] = "Pending v0.72 report-only validator and browser check; application behavior not validated."
    state["package"].update({"status": "pending", "file_count": None, "integrity": "Pending v0.72 rebuild after report QA and final handoff checkpoint."})
    state["portable_bundle_status"] = "Pending final v0.72 audit-only package rebuild and verification."
    save("STATE.json", state)
    (ROOT / "TIEP-TUC.md").write_text(
        "# CURRENT HANDOFF — v0.72, Round 49\n\n"
        f"Evidence source: immutable Git SHA `{SHA}` in `{REPO}`. The primary checkout may contain user WIP; do not use it as evidence. Read source only with `git show <SHA>:<path>`. Only edit audit artifacts in this directory; do not run ClinicAI tests/runtime/API/DB/provider/VPS/production or inspect secrets/PHI.\n\n"
        "Round 49 adds FIN-020 (one-sided NULL split can pass the payment ledger DB guard; current API service validates both legs). Exact ranges/hashes and the held fractional-input observation are in `blocks/round49.md`, `blocks/round49.coverage.json`, `PHAT-HIEN.json` and `MAIN-PHAM-VI.json`. Tests read-not-run.\n\n"
        "Full source audit remains incomplete. Path counters are inventory states, not semantic coverage. v0.72 report-only QA and audit-only ZIP refresh are pending. Resume with `BAT-DAU-TU-DAY.md`, then read `STATE.json` and continue from exact pinned main.\n"
    )
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(
        "# Bắt đầu từ đây — checkpoint v0.72, Round 49\n\n"
        "Đọc `TIEP-TUC.md`, `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `blocks/round49.md` và `blocks/round49.coverage.json`. Source evidence chỉ từ SHA `" + SHA + "` qua `git show` trong worktree audit; không dùng working-tree WIP làm bằng chứng.\n\n"
        "Round 49 thêm FIN-020; hiện API/service kiểm tra cả hai chân split nhưng constraint/trigger DB còn nhận shape một chân khi privileged writer bypasses service. Tests read-not-run; không runtime/production. v0.72 QA/package pending.\n\n"
        "**Full source audit chưa hoàn tất.** Path counters không phải phần trăm đã hiểu hành vi; chỉ sửa audit artifacts. Tiếp tục theo `STATE.json.next_action`.\n"
    )
    with (ROOT / "NHAT-KY.md").open("a") as handle:
        handle.write(
            "\n\n## Round 49 — 20/10/2026, v0.72 integration\n\n"
            f"Static exact-main review at SHA `{SHA}`. Added FIN-020: the nullable split-payment CHECK/trigger does not fully reject one-sided NULL rows for privileged DB writers; the current service path validates both legs. No new runtime/production incident is claimed. Related tests were read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact coverage is in `blocks/round49.coverage.json`; full source audit remains incomplete. Report-only QA/package refresh pending.\n"
        )
    print(f"Integrated Round 49: {len(findings)} findings; {len(coverage_items)} path coverage records; full audit remains open")


if __name__ == "__main__":
    main()
