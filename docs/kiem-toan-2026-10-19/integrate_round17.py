"""Integrate the round-17 static audit slice into durable audit artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
SNAPSHOT = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
PINNED_SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
CODE_SUFFIXES = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html",
}


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def source(path: str) -> tuple[list[str], str]:
    data = (SNAPSHOT / path).read_bytes()
    return data.decode().splitlines(), hashlib.sha256(data).hexdigest()


def excerpt(path: str, start: int, end: int, detail: str) -> dict:
    lines, digest = source(path)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid source range: {path}:{start}-{end}")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": digest,
        "excerpt": "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1)),
        "detail": detail,
    }


def visible_evidence(path: str, start: int, end: int, detail: str) -> dict:
    _, digest = source(path)
    return {"path": path, "line": start, "end_line": end, "sha256": digest, "detail": detail}


def new_findings() -> list[dict]:
    sec_evidence = [
        visible_evidence("src/clinicai/services/permission_service.py", 218, 232,
                         "Cấp khối quyền được ghi thành capability.granted trong cùng transaction của capability_grant."),
        visible_evidence("src/clinicai/services/permission_service.py", 258, 286,
                         "Thu hồi khối quyền cập nhật người thu hồi rồi phát capability.revoked."),
        visible_evidence("src/clinicai/events/emit.py", 181, 213,
                         "emit_event ghi typed event vào domain_event; đây là nguồn khác event_log."),
        visible_evidence("src/clinicai/services/audit_log_service.py", 68, 129,
                         "SQL nhật ký chỉ hợp nhất v_audit_log và work_item_event; không đọc domain_event."),
        visible_evidence("src/clinicai/api/v1/routers/audit_log.py", 29, 38,
                         "GET /audit/events là API đọc nhật ký, lấy clinic từ identity đã xác thực."),
        visible_evidence("src/dashboard/app/(dashboard)/audit-log/page.tsx", 42, 46,
                         "Trang /audit-log chỉ tải endpoint /api/v1/audit/events."),
        visible_evidence("src/tests/services/test_permission_db.py", 276, 289,
                         "Test xác nhận sự kiện cấp quyền tồn tại trong domain_event và giữ actor; không kiểm projection lên màn audit."),
    ]
    sec_main = [
        excerpt("src/clinicai/services/permission_service.py", 218, 232,
                "Grant transaction emits the capability.granted domain event."),
        excerpt("src/clinicai/services/permission_service.py", 258, 286,
                "Revoke persists revoked_by and emits capability.revoked."),
        excerpt("src/clinicai/events/emit.py", 181, 213,
                "The event writer inserts domain_event and returns without writing event_log."),
        excerpt("src/clinicai/services/audit_log_service.py", 68, 129,
                "The complete audit query combines v_audit_log with work_item_event only."),
        excerpt("src/clinicai/api/v1/routers/audit_log.py", 29, 38,
                "The operator audit endpoint delegates to AuditLogService.events."),
        excerpt("src/dashboard/app/(dashboard)/audit-log/page.tsx", 42, 46,
                "The dashboard audit page consumes only the consolidated endpoint."),
        excerpt("src/tests/services/test_permission_db.py", 276, 289,
                "Existing test confirms durable domain_event and actor but not audit UI visibility."),
    ]
    sec = {
        "id": "SEC-026",
        "title": "Nhật ký thao tác không hiện sự kiện cấp và thu quyền nhân viên",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "security_audit_visibility",
        "summary": "PermissionService ghi capability.granted/capability.revoked vào domain_event trong transaction; API và trang /audit-log chỉ đọc v_audit_log (event_log) cùng work_item_event. Dữ liệu cấp/thu quyền vẫn được lưu trong domain_event và capability_grant, nhưng không xuất hiện trong nhật ký thao tác hợp nhất.",
        "trigger": "Quản lý cấp hoặc thu một khối quyền, sau đó người có audit.view mở /audit-log để xác định ai đổi quyền, cho ai và trong phạm vi nào.",
        "impact": "Người vận hành không thể tìm thay đổi quyền từ màn nhật ký tập trung, làm chậm việc rà soát hoặc điều tra. Đây là khoảng trống khám phá/đối chiếu; không phải bằng chứng mất bản ghi, vượt quyền hay rò dữ liệu chéo clinic.",
        "evidence": sec_evidence,
        "validation": {
            "method": "static_permission_event_to_audit_api_and_dashboard_trace_on_pinned_main",
            "command": None,
            "result": "Exact-main trace confirms grant/revoke are durable domain events while the audit SQL and UI read only event_log projection plus work_item_event. Existing permission test asserts the domain_event row and actor.",
            "limitations": "No database query, API/UI integration test, role matrix or production observation was performed. Finding is limited to visibility in the consolidated /audit-log surface; it does not claim the underlying permission history is absent.",
        },
        "recommendation": "Đưa các security event đã chọn vào read model nhật ký với actor, người nhận, quyền, phạm vi và thời điểm; giữ bộ lọc clinic lấy từ identity và quyền audit.view. Chỉ chiếu payload tối thiểu, không mở toàn bộ domain_event lâm sàng cho vai vận hành.",
        "acceptance": "Test cấp và thu quyền cho thấy đúng actor, nhân viên đích, capability, scope và thời gian trong audit API/UI của cùng clinic; clinic khác không nhìn thấy; payload lâm sàng không được đưa vào projection.",
        "related_tests": [
            {"path": "src/tests/services/test_permission_db.py", "scope": "Asserts capability.granted is persisted in domain_event with actor and is_public=false; does not assert audit API/UI projection."},
            {"path": "src/tests/test_audit_log_day_window.py", "scope": "Covers Vietnam day bounds and all rows for the selected day; does not exercise domain_event inclusion."},
        ],
        "source_hashes": {
            path: source(path)[1]
            for path in sorted({item["path"] for item in sec_evidence})
        },
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PINNED_SHA,
            "status": "still_present_on_main",
            "note": "Round 17 static trace: permission history is stored in domain_event/capability_grant but is not projected by the consolidated audit endpoint or page. No production or patient data was accessed.",
            "evidence": sec_main,
            "production_verified": False,
        },
        "dedup_note": "Khác SEC-013 (PII trong payload event_log) và INF-010 (thao tác không ghi audit bền vững): ở đây sự kiện cấp/thu quyền đã có trong domain_event nhưng bị bỏ khỏi read model /audit-log.",
    }

    floor_paths = {
        "src/clinicai/services/audit.py",
        "src/clinicai/services/clinic_floor_service.py",
        "src/tests/services/test_tang_va_vi_tri_moi_db.py",
    }
    floor_ranges = [
        ("src/clinicai/services/audit.py", 32, 35,
         "Audit writer documents atomicity: record row must share the caller's transaction."),
        ("src/clinicai/services/audit.py", 51, 75,
         "record_event inserts through the connection supplied by its caller."),
        ("src/clinicai/services/clinic_floor_service.py", 97, 114,
         "_audit acquires a fresh connection from the pool before calling record_event."),
        ("src/clinicai/services/clinic_floor_service.py", 124, 156,
         "create commits its mutation transaction before awaiting _audit."),
        ("src/clinicai/services/clinic_floor_service.py", 168, 185,
         "rename performs the update before awaiting _audit on a separate connection."),
        ("src/clinicai/services/clinic_floor_service.py", 192, 203,
         "set_active begins its state change in a transaction."),
        ("src/clinicai/services/clinic_floor_service.py", 253, 259,
         "set_active exits its transaction and then awaits _audit."),
        ("src/clinicai/services/clinic_floor_service.py", 272, 300,
         "reorder applies all order updates inside its transaction."),
        ("src/clinicai/services/clinic_floor_service.py", 301, 307,
         "reorder exits its transaction and then awaits _audit."),
        ("src/tests/services/test_tang_va_vi_tri_moi_db.py", 52, 100,
         "Related integration test exercises successful create/rename and room-label propagation; no audit-write failure is injected."),
    ]
    floor = {
        "id": "INF-021",
        "title": "Thay đổi danh mục tầng commit trước khi ghi nhật ký thao tác",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "post_commit_audit_consistency",
        "summary": "ClinicFloorService.create, rename, set_active và reorder thay đổi trạng thái rồi mới gọi _audit. _audit mở connection mới, trong khi record_event được thiết kế để ghi trên transaction của caller. Nếu lần ghi event lỗi sau mutation, trạng thái đã đổi nhưng API không trả thành công và event audit không có.",
        "trigger": "Một thao tác tạo/đổi tên/tắt-bật/sắp thứ tự tầng cập nhật thành công nhưng event_log insert thất bại ở bước audit kế tiếp.",
        "impact": "Người dùng có thể thấy lỗi dù cấu hình đã được áp dụng, phải tải lại để biết trạng thái thật; đồng thời nhật ký thiếu thay đổi đó. Tác động hiện được giới hạn ở cấu hình tầng; chưa có fault-injection hoặc bằng chứng production.",
        "evidence": [visible_evidence(path, start, end, detail) for path, start, end, detail in floor_ranges],
        "validation": {
            "method": "static_transaction_boundary_trace_for_clinic_floor_mutations_on_pinned_main",
            "command": None,
            "result": "Exact-main read confirms four mutation paths call _audit only after their write transaction/statement completes; _audit obtains a different pooled connection and record_event relies on the caller transaction.",
            "limitations": "No fault-injection test or runtime observation. Existing floor integration coverage checks successful operations and validation paths, not failure of event_log insertion after commit. No production behavior was checked.",
        },
        "recommendation": "Ghi mutation và event_log row trên cùng connection/transaction cho cả bốn lệnh. Nếu atomicity không thể bảo đảm trực tiếp, dùng outbox bền có trạng thái chưa ghi nhật ký nhìn thấy được và quy trình retry; không trả lỗi mơ hồ sau một mutation đã commit.",
        "acceptance": "Fault-injection tại event insert cho create/rename/set_active/reorder phải chứng minh mutation và audit cùng commit hoặc cùng rollback; kết quả API và UI phản ánh trạng thái thật; test thành công tiếp tục kiểm payload actor/object.",
        "related_tests": [
            {"path": "src/tests/services/test_tang_va_vi_tri_moi_db.py", "scope": "Happy-path DB tests cover create, rename, soft-delete/reactivation and reorder, but do not inject audit insert failure."},
        ],
        "source_hashes": {path: source(path)[1] for path in sorted(floor_paths)},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PINNED_SHA,
            "status": "still_present_on_main",
            "note": "Round 17 full service read confirms the transaction ends before audit append on all four floor mutation paths; static only, not fault-injected.",
            "evidence": [excerpt(path, start, end, detail) for path, start, end, detail in floor_ranges],
            "production_verified": False,
        },
    }

    fe_ranges = [
        ("src/dashboard/app/api/clinical/[visit_id]/[action]/route.ts", 23, 38,
         "The status GET converts a null backend result into a JSON error with the default HTTP 200."),
        ("src/dashboard/lib/backend-proxy.ts", 244, 267,
         "fetchFromBackend returns null for missing API config/session, non-2xx responses and network/JSON failures."),
        ("src/dashboard/app/(dashboard)/tasks/HoSoHoanTatPanel.tsx", 91, 100,
         "load trusts response.ok and casts any JSON body to Status."),
        ("src/dashboard/app/(dashboard)/tasks/HoSoHoanTatPanel.tsx", 158, 170,
         "Render indexes LABEL by the unvalidated state and dereferences tone.bg/tone.fg/text."),
        ("src/dashboard/app/(dashboard)/error.tsx", 26, 31,
         "The nearest dashboard segment error boundary is defined in the dashboard route group."),
        ("src/dashboard/app/(dashboard)/error.tsx", 48, 63,
         "The boundary renders a dashboard error panel; this does not imply the whole app shell fails."),
        ("src/dashboard/tests/hoan-tat-khong-ky-boundary.test.mts", 17, 30,
         "Existing related boundary test checks removal of the signing flow, not status GET error payloads."),
    ]
    fe_paths = {path for path, *_ in fe_ranges}
    fe = {
        "id": "FE-018",
        "title": "Lỗi đọc trạng thái bệnh án có thể làm panel lỗi khi render",
        "severity": "LOW",
        "evidence_level": "confirmed_static",
        "category": "clinical_status_error_handling",
        "summary": "Khi fetchFromBackend không lấy được trạng thái, BFF trả {error} với HTTP 200. HoSoHoanTatPanel chỉ kiểm tra response.ok, ép payload thành Status rồi truy cập LABEL[state].bg/text; state không hợp lệ làm tone undefined và render có thể throw.",
        "trigger": "Backend status trả non-2xx, lỗi mạng/JSON, thiếu session token hoặc API_BASE không cấu hình trong khi dashboard session vẫn có user.",
        "impact": "Panel có thể làm nội dung dashboard route hiện tại chuyển sang error boundary thay vì hiển thị lỗi tải trạng thái. Đây là đường đọc; không có bằng chứng thao tác hay dữ liệu bệnh án bị thay đổi. Chưa runtime-test.",
        "evidence": [visible_evidence(path, start, end, detail) for path, start, end, detail in fe_ranges],
        "validation": {
            "method": "static_bff_error_status_to_react_render_trace_on_pinned_main",
            "command": None,
            "result": "Exact-main trace confirms backend helper failure becomes HTTP 200 error JSON and the panel dereferences an absent LABEL entry. The nearest dashboard error boundary scopes the fallback to the route segment.",
            "limitations": "No component render, BFF request or browser test was run for this trigger. The finding is LOW and limited to the nearest dashboard segment; it does not claim a whole-app crash or any write/data-loss effect.",
        },
        "recommendation": "BFF phải giữ HTTP error status hoặc trả envelope có discriminant; component kiểm tra shape/state trước khi render và hiện trạng thái lỗi có nút thử lại.",
        "acceptance": "Test backend 401/503/network/invalid JSON và payload sai shape: API không trả success-shaped HTTP 200, panel không throw và hiển thị lỗi tải; payload hợp lệ vẫn render đúng nhãn.",
        "related_tests": [
            {"path": "src/dashboard/tests/hoan-tat-khong-ky-boundary.test.mts", "scope": "Covers no-signing flow; no error-status or response-shape assertion for the status BFF."},
        ],
        "source_hashes": {path: source(path)[1] for path in sorted(fe_paths)},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PINNED_SHA,
            "status": "still_present_on_main",
            "note": "Round 17 static UI/API trace; the nearest dashboard error boundary limits the likely failure surface. No runtime reproduction.",
            "evidence": [excerpt(path, start, end, detail) for path, start, end, detail in fe_ranges],
            "production_verified": False,
        },
    }
    return [sec, floor, fe]


def main() -> None:
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"Pinned source snapshot is unavailable: {SNAPSHOT}")
    actual_sha = __import__("subprocess").check_output(
        ["git", "-C", str(SNAPSHOT), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != PINNED_SHA:
        raise SystemExit(f"Pinned source mismatch: expected {PINNED_SHA}, got {actual_sha}")

    manifest = read_json("MAIN-PHAM-VI.json")
    if manifest["sha"] != PINNED_SHA:
        raise SystemExit("MAIN-PHAM-VI.json snapshot does not match round 17 source")
    by_path = {row["path"]: row for row in manifest["files"]}
    additions = new_findings()
    existing = {row["id"] for row in read_json("PHAT-HIEN.json")}
    duplicate_ids = sorted(existing.intersection(row["id"] for row in additions))
    if duplicate_ids:
        raise SystemExit(f"Round 17 finding IDs already exist: {duplicate_ids}; refusing re-integration")

    updates = {
        "src/clinicai/services/audit.py": ("read", "Round 17 full semantic read; record_event requires the caller transaction."),
        "src/clinicai/services/audit_log_service.py": ("read", "Round 17 full semantic read; audit SQL sources and day-window behavior."),
        "src/clinicai/api/v1/routers/audit_log.py": ("read", "Round 17 full route read; audit.view guard and identity-derived clinic."),
        "src/dashboard/app/(dashboard)/audit-log/page.tsx": ("read", "Round 17 full page read; consumes only /api/v1/audit/events."),
        "src/clinicai/services/clinic_floor_service.py": ("read", "Round 17 full service read; four post-mutation audit calls."),
        "src/tests/test_audit_log_day_window.py": ("read", "Round 17 full test read; day boundaries and >200 rows, no domain-event projection assertion."),
        "src/dashboard/app/api/clinical/[visit_id]/[action]/route.ts": ("read", "Round 17 full BFF route read; GET status error payload uses default HTTP 200."),
        "src/dashboard/app/(dashboard)/error.tsx": ("read", "Round 17 full dashboard segment error-boundary read; scopes render fallback to route segment."),
        "src/tests/services/test_tang_va_vi_tri_moi_db.py": ("traced", "Round 17 targeted happy-path floor tests; no audit-insert fault injection."),
        "src/dashboard/tests/hoan-tat-khong-ky-boundary.test.mts": ("traced", "Round 17 targeted boundary-test trace; no status-fetch error/shape assertion."),
    }
    coverage_rows = []
    for path, (status, note) in updates.items():
        row = by_path[path]
        lines, digest = source(path)
        if row["sha256"] != digest or row["lines"] != len(lines):
            raise SystemExit(f"Ledger fingerprint mismatch for {path}")
        row["status"] = status
        row["method"] = f"{row.get('method', '')} | {note}".strip(" |")
        coverage_rows.append({
            "path": path,
            "status": status,
            "method": "Full semantic read" if status == "read" else "Targeted semantic trace",
            "note": note,
            "sha256": digest,
            "git_blob_sha1": row["git_blob_sha1"],
            "full_file_read": status == "read",
            "line_count": len(lines),
        })
    write_json("MAIN-PHAM-VI.json", manifest)

    findings = read_json("PHAT-HIEN.json")
    findings.extend(additions)
    write_json("PHAT-HIEN.json", findings)
    write_json("blocks/round17_audit_visibility_commit_boundary.findings.json", additions)

    coverage_payload = {
        "schema_version": 1,
        "audit": "round17_audit_visibility_commit_boundary",
        "snapshot": {
            "path": str(SNAPSHOT),
            "sha": PINNED_SHA,
            "sha_verification": "Read from the active detached checkout at exact pinned Git SHA; application source is Git-exact.",
        },
        "review_mode": "static_read_only_cross_layer_trace",
        "scope": [
            "permission grant/revoke event stream and consolidated audit API/UI",
            "audit writer transaction contract and clinic-floor mutation boundaries",
            "clinical status BFF error mapping and consuming dashboard panel",
            "closest existing tests and dashboard error boundary",
        ],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "files": coverage_rows,
    }
    write_json("blocks/round17_audit_visibility_commit_boundary.coverage.json", coverage_payload)

    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    checks = read_json("KIEM-CHUNG.json")
    known = {(row["id"], row["path"]) for row in checks["checks"]}
    for finding in additions:
        for ev in finding["main_validation"]["evidence"]:
            key = (finding["id"], ev["path"])
            if key not in known:
                checks["checks"].append({"id": finding["id"], "path": ev["path"], "valid": True})
                known.add(key)
    write_json("KIEM-CHUNG.json", checks)

    state = read_json("STATE.json")
    all_counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    status_counts = Counter(row["main_validation"]["status"] for row in findings)
    severity_counts = Counter(row["severity"] for row in findings)
    level_counts = Counter(row["evidence_level"] for row in findings)
    state["updated_at"] = now
    state["phase"] = "round17_audit_visibility_commit_boundary_checkpoint"
    state["next_action"] = (
        "Tiếp tục semantic-read các luồng chưa phủ, ưu tiên clinical result lifecycle, "
        "worker recovery và finance reconciliation; sau đó kiểm thử fault-injection trên "
        "DB dùng một lần cho các finding còn static. Cập nhật ledger và evidence sau mỗi lát. "
        "Full source audit remains incomplete."
    )
    state["report_status"] = "v0.38_137_findings_HTML_and_portable_ZIP_pending_final_QA; full source audit incomplete"
    summary = state["summary"]
    summary["findings"] = len(findings)
    summary["severity"] = {key: severity_counts.get(key, 0) for key in ("HIGH", "MEDIUM", "LOW")}
    summary["evidence_levels"] = {key: level_counts.get(key, 0) for key in ("reproduced_local", "design_gap", "confirmed_static", "hypothesis")}
    summary["main_status"] = {key: status_counts.get(key, 0) for key in ("still_present_on_main", "partially_addressed_on_main", "addressed_on_main")}
    summary["main_coverage"] = {key: all_counts.get(key, 0) for key in ("inventoried", "read", "traced", "scanned", "excluded")}
    summary["main_read_files"] = all_counts["read"]
    summary["main_partial_traces"] = all_counts["traced"]
    summary["code_like_source_files"] = {
        "definition": "Pinned-tree files with common source-code/web/sql/shell suffixes used by the report generator; includes app, tests, tooling and styles, not only runtime code.",
        "total": len(code_files),
        "coverage": {key: code_counts.get(key, 0) for key in ("inventoried", "traced", "scanned", "read")},
        "traced_is_partial": True,
    }
    summary["reviewed_slice_v038"] = "round17_audit_visibility_commit_boundary; 8 full reads plus 2 targeted test traces; SEC-026, INF-021, FE-018 added; static only, no application tests run."
    summary["new_findings_v038"] = ["SEC-026", "INF-021", "FE-018"]
    state["blocks"]["round17_audit_visibility_commit_boundary"] = {
        "status": "round17 static slice triaged; SEC-026, INF-021 and FE-018 added",
        "scope": "Permission-event visibility, post-commit floor audit writes, and clinical status BFF/render failure path",
        "artifacts": "blocks/round17_audit_visibility_commit_boundary.md; blocks/round17_audit_visibility_commit_boundary.findings.json; blocks/round17_audit_visibility_commit_boundary.coverage.json",
        "findings": "SEC-026 and INF-021 MEDIUM; FE-018 LOW; all confirmed_static and still_present_on_main.",
        "next": "Fault-inject audit insert for all floor mutations and add typed permission-event projection tests; continue unread clinical result, worker recovery and finance reconciliation paths.",
    }
    state["artifacts"]["qa"] = "HTML-QA.json; v0.38 pending rebuild and desktop/mobile browser QA; report-only, not ClinicAI application validation."
    state["artifacts"]["integration_script"] = "integrate_round17.py; round17 evidence/coverage in blocks/round17_*; prior checkpoints retained."
    state["artifacts"]["bundle_integrity"] = "Pending v0.38 package regeneration and verification after HTML QA."
    state["artifacts"]["html_sha256"] = "pending v0.38 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.38 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.38 package verification"
    state["runtime_summary"]["audit_report_qc"] = "Pending v0.38 report regeneration and desktop/mobile QA; no ClinicAI application test was run for round 17."
    state["held_observations"].append({
        "id": "CLINIC-POLICY-001",
        "classification": "held_reliability_question_not_a_finding",
        "severity_assessment": "Chưa xếp mức; fallback có DB guard nhưng chưa có policy/fault test.",
        "snapshot_sha": PINNED_SHA,
        "question": "Khi đọc/parsing clinic policy hoặc resolver gặp exception, nhánh load_effective_policy có thể fallback về DEFAULT_POLICY/clinic policy. Cần owner nghiệp vụ xác nhận default có an toàn khi nguồn policy không đọc được; hiện chưa có bằng chứng overbooking vì DB CHECK/trigger vẫn chặn capacity.",
        "evidence": [
            {"path": "src/clinicai/services/clinic_policy.py", "lines": "158-164,183-199"},
            {"path": "src/clinicai/api/v1/routers/booking.py", "lines": "660-668"},
        ],
        "not_promoted_reason": "Static candidate from a separate service-scope review; exact hashes/trigger and business impact were not fully validated in this round.",
        "next": "Read the exact-main policy and booking route, identify which defaults affect patient-facing availability, and add a resolver failure test before promotion.",
    })
    write_json("STATE.json", state)

    block_md = f"""# Round 17 — audit visibility, transaction boundary, and status BFF\n\nSnapshot: pinned main `{PINNED_SHA}`. Coverage fingerprints are in `round17_audit_visibility_commit_boundary.coverage.json`.\n\n## SEC-026 — permission history is outside the consolidated audit page\n\n`PermissionService` writes typed `capability.granted` and `capability.revoked` events into `domain_event` in the permission transaction. The protected `/api/v1/audit/events` endpoint calls `AuditLogService`, whose SQL combines `v_audit_log` and `work_item_event`; the dashboard page consumes only that endpoint. The event and grant history remain durable. The finding is the operator discoverability gap in `/audit-log`, not missing storage or a tenant bypass.\n\nRecommendation: add a minimal, clinic-scoped projection for selected security events, with actor, target, capability, scope and time. Keep clinical event payloads outside the operations view. No DB/API/UI integration test or production data was used.\n\n## INF-021 — floor mutation commits before its audit append\n\n`create`, `rename`, `set_active` and `reorder` update state, then call `_audit`. `_audit` acquires a different pooled connection, while `record_event` documents that it relies on the caller transaction. An event insert failure can therefore leave committed configuration with an API error and no matching audit row. This is confirmed by source layout only; no fault injection or production occurrence is claimed.\n\nExisting floor DB tests cover successful mutation and validation, not audit-writer failure. Acceptance should inject event insert failure for each command and prove all-or-nothing behavior.\n\n## FE-018 — status read failure becomes success-shaped JSON\n\nThe clinical status BFF returns `{{error}}` with default HTTP 200 when `fetchFromBackend` returns `null`. `HoSoHoanTatPanel` trusts `response.ok`, casts the body to `Status`, and dereferences an absent label entry. The nearest dashboard error boundary limits the likely failure to the current route segment. This is LOW, static only; no render/BFF runtime test was run.\n\n## Limits and next work\n\nEight files received full semantic reads and two related test files were traced. No ClinicAI tests, database, Auth provider, production, secrets or patient data were touched in this slice. The three additions are `confirmed_static`; the complete source audit remains incomplete. Next inspect clinical-result lifecycle, worker recovery and finance reconciliation, then use a disposable database for targeted failure injection.\n"""
    (ROOT / "blocks/round17_audit_visibility_commit_boundary.md").write_text(block_md)

    log = ROOT / "NHAT-KY.md"
    old_log = log.read_text()
    heading = "## Round 17 — audit visibility, commit boundary and status BFF — 20/10/2026\n"
    if heading not in old_log:
        entry = f"""{heading}\n- Đọc trọn 8 file trên exact-main: audit writer/service/router/page, floor service, status BFF, dashboard error boundary và day-window test; trace thêm hai test liên quan. Fingerprints và giới hạn ở `blocks/round17_audit_visibility_commit_boundary.coverage.json`.\n- Thêm SEC-026 (quyền cấp/thu có trong domain_event nhưng chưa hiện ở nhật ký hợp nhất), INF-021 (4 mutation tầng commit trước audit append), FE-018 (lỗi status đọc bị BFF trả HTTP 200, panel có thể throw). Cả ba là confirmed_static; FE-018 xếp LOW vì error boundary gần nhất giữ phạm vi ở dashboard route.\n- Đã dedupe với SEC-013, INF-010, SEC-006 và FE-017; không trùng nguyên nhân/tác động. Candidate fallback clinic policy được giữ ở STATE.held_observations do cần xác minh policy/impact.\n- Không chạy app test/fault injection; không truy cập DB, Auth, production, secrets hay patient data. Full source audit còn dang dở.\n- QA HTML/ZIP v0.38 đang chờ build và verify sau cập nhật.\n\n"""
        log.write_text(heading + "\n" + entry.split("\n", 1)[1] + old_log)

    print(json.dumps({
        "findings": len(findings),
        "severity": dict(severity_counts),
        "coverage": dict(all_counts),
        "code_like_total": len(code_files),
        "code_like_coverage": dict(code_counts),
        "new_ids": [row["id"] for row in additions],
        "updated_at": now,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
