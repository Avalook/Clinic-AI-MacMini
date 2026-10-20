"""Integrate Round 51's static appointment reschedule concurrency review."""
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


def proof(path: str, start: int, end: int, detail: str) -> dict:
    raw = subprocess.check_output(["git", "show", f"{SHA}:{path}"], cwd=REPO)
    lines = raw.decode("utf-8").splitlines()
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
    if any(item["id"] == "CLIN-059" for item in findings):
        raise ValueError("CLIN-059 already exists; refusing duplicate integration")

    specs = [
        ("src/clinicai/services/booking_service.py", 955, 1004,
         "Each action reads the appointment by ID and clinic but does not lock the row before building its transition from the observed status and slot."),
        ("src/clinicai/services/booking_service.py", 1036, 1102,
         "A reschedule checks that the status is allowed, builds a patch from the earlier read, and only detects a race when the later UPDATE returns no row."),
        ("src/clinicai/services/booking_service.py", 2102, 2132,
         "The compare-and-update predicate checks only appointment ID, clinic and allowed status; it does not compare the previously read slot or a version token."),
        ("src/clinicai/services/booking_service.py", 2880, 2923,
         "The history row and appointment.rescheduled event use the earlier `appt` snapshot plus this request's patch, so a concurrent second writer can record stale `from` values."),
        ("src/clinicai/services/booking_service.py", 1209, 1323,
         "Quick reschedule runs the same reschedule transition inside one transaction and preserves status when check-in is false."),
        ("src/clinicai/api/v1/routers/booking.py", 747, 802,
         "The endpoint acquires idempotency by key, then executes the service; separate target-specific keys are independent requests."),
        ("src/clinicai/api/idempotency.py", 72, 180,
         "Idempotency uniqueness is scoped to key, endpoint and actor; different keys do not serialize conflicting appointment edits."),
        ("src/dashboard/app/(dashboard)/_lam-viec/DoiLichTaiCho.tsx", 132, 206,
         "The quick-reschedule key includes the chosen doctor, slot and check-in choice, so two different target slots create different keys; the key is component-session scoped."),
        ("src/dashboard/app/api/appointments/doi-lich-nhanh/route.ts", 1, 61,
         "The BFF forwards the per-choice idempotency key to the backend header while forwarding the selected target fields."),
        ("src/clinicai/events/catalogue.py", 1938, 1946,
         "Rescheduled events have a timeline consumer but no required aggregate sequence configured here."),
        ("src/tests/services/test_doi_lich_nhanh_db.py", 1, 351,
         "Full DB test file: same-key replay, capacity, check-in permission and outside-shift cases; no concurrent different-target reschedule test. Tests were read-not-run."),
        ("src/tests/unit/test_doi_lich_nhanh.py", 1, 98,
         "Full pure test file: slot labels, current-time slot and reasons; no concurrent transition coverage. Tests were read-not-run."),
    ]
    finding = {
        "id": "CLIN-059",
        "title": "Hai lệnh đổi lịch đồng thời có thể ghi đè nhau và làm sai lịch sử chuyển tiếp",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "clinical/booking-concurrency",
        "summary": "Hai yêu cầu đổi cùng một lịch sang hai khung khác nhau có thể cùng đọc một trạng thái đầu. `BookingService._update` chỉ yêu cầu status còn thuộc tập cho phép; nó không so giờ cũ hoặc phiên bản mà yêu cầu đã đọc. Nếu cả hai đều giữ status `CONFIRMED`/`SCHEDULED`, UPDATE thứ hai vẫn thỏa điều kiện sau khi chờ khóa dòng và có thể ghi đè khung thứ nhất. Mỗi lệnh sau đó ghi `appointment_doi_lich`/`appointment.rescheduled` từ snapshot `appt` cũ, nên lịch sử có thể ghi hai lần từ cùng giờ ban đầu, bỏ mất chuyển tiếp thực tế qua khung thứ nhất. Với đổi lịch nhanh, key chứa slot đích nên hai lựa chọn khác nhau cũng không được idempotency gộp thành một lệnh.",
        "trigger": "Hai nhân viên hoặc hai phiên trình duyệt cùng mở một lịch còn trạng thái trước check-in, rồi gần như đồng thời chọn hai khung đích khác nhau. Hai lệnh mang idempotency key khác nhau và cả hai transaction đọc trước khi lệnh đầu cập nhật xong.",
        "impact": "Cả hai thao tác có thể trả thành công trong khi lịch cuối chỉ giữ lựa chọn ghi sau. Người bấm trước có thể tưởng lịch đã chuyển sang khung mình chọn; sổ đổi lịch có thể không ghi chuỗi giờ cũ → đích A → đích B. Lịch cuối vẫn là một lịch hẹn duy nhất; chưa chứng minh bệnh nhân bị đặt trùng hoặc có thông báo bên ngoài sai. Đây là rủi ro concurrency suy ra từ câu UPDATE và không được tái hiện bằng DB.",
        "evidence": [],
        "validation": {
            "method": "read_only_exact_main_static_reschedule_transition_and_idempotency_trace",
            "command": None,
            "result": "Đối chiếu lần đọc appointment, predicate UPDATE, ghi nhật ký/sự kiện trong transaction, endpoint idempotency và khóa từ UI. Predicate UPDATE không có expected slot/version; status không đổi khi chỉ dời lịch. Các test hiện có kiểm same-key replay và luật nghiệp vụ theo thứ tự, không có hai connection với hai target khác nhau; tests were read-not-run.",
            "limitations": "Static exact-main inference only. Không chạy ClinicAI tests, DB hay hai transaction đồng thời. Không kết luận lỗi đã xuất hiện ở production. Cần xác nhận bằng test synthetic trên disposable DB để chốt mức độ và đúng quy tắc nghiệp vụ khi nhiều nhân viên cùng sửa.",
        },
        "recommendation": "Thêm optimistic concurrency cho lịch hẹn: GET trả `updated_at`/version hoặc slot hiện tại làm expected state; POST/PATCH chỉ cập nhật nếu trạng thái và expected version/slot vẫn khớp. Nếu không khớp, trả 409 yêu cầu tải lại và chọn lại. Ghi from→to và phát event từ dòng đã khóa/đọc mới trong cùng transaction; idempotency tiếp tục xử lý replay cùng một ý định.",
        "acceptance": "Trên disposable DB với dữ liệu synthetic, dùng hai connection và barrier để hai lệnh dời cùng appointment sang hai slot khác nhau cùng bắt đầu từ một expected version. Một lệnh thành công, lệnh còn lại nhận 409; appointment giữ slot của lệnh thắng; lịch sử chỉ có một transition contiguous từ slot cũ tới slot thắng; một event được phát. Thêm ca cùng payload/key để xác nhận replay vẫn trả cùng response mà không nhân đôi history/event.",
        "alignment": [
            "Reality lịch hẹn và lựa chọn của nhân viên không bị ghi đè im lặng",
            "Ownership của lần đổi và lịch sử trước–sau rõ ràng",
            "Bệnh nhân không bị đưa về khung khác với khung nhân viên vừa xác nhận",
        ],
        "related_tests": [
            "src/tests/services/test_doi_lich_nhanh_db.py:135-185 — đọc, không chạy; cùng key được phát lại và không nhân đôi; chưa kiểm hai key/target đồng thời.",
            "src/tests/services/test_doi_lich_nhanh_db.py:188-351 — đọc, không chạy; capacity, check-in quyền và ngoài ca; không kiểm lost update concurrency.",
            "src/tests/unit/test_doi_lich_nhanh.py — đọc, không chạy; pure slot display cases, không kiểm transition concurrency.",
        ],
        "source_hashes": {},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "The update predicate checks only allowed status rather than the expected old schedule/version. Concurrent same-status reschedules can therefore overwrite and log a stale from-slot; no runtime reproduction is claimed.",
            "evidence": [],
        },
        "related_findings": ["CLIN-057"],
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
        ("src/clinicai/services/doi_lich_nhanh.py", 1, 292,
         "Full-file read: quick-reschedule option construction and capacity/status presentation."),
        ("src/clinicai/services/booking_service.py", 955, 1004,
         "Targeted read: appointment state read and transition preconditions."),
        ("src/clinicai/services/booking_service.py", 1036, 1102,
         "Targeted read: status check, patch build and optimistic-update outcome."),
        ("src/clinicai/services/booking_service.py", 1209, 1323,
         "Targeted read: quick reschedule plus optional check-in transaction."),
        ("src/clinicai/services/booking_service.py", 2102, 2132,
         "Targeted read: SQL update predicate and exclusion/check error mapping."),
        ("src/clinicai/services/booking_service.py", 2880, 2923,
         "Targeted read: appointment reschedule history and domain event side effects."),
        ("src/clinicai/api/v1/routers/booking.py", 747, 802,
         "Targeted read: HTTP schema, permission and idempotency boundary."),
        ("src/clinicai/api/idempotency.py", 72, 180,
         "Targeted read: per-key actor/endpoint reservation and replay behavior."),
        ("src/dashboard/app/(dashboard)/_lam-viec/DoiLichTaiCho.tsx", 132, 206,
         "Targeted read: request key lifecycle, target-specific key and response handling."),
        ("src/dashboard/app/api/appointments/doi-lich-nhanh/route.ts", 1, 61,
         "Full-file read: BFF validation and idempotency header forwarding."),
        ("src/clinicai/events/catalogue.py", 1938, 1946,
         "Targeted read: reschedule event consumer configuration."),
        ("src/clinicai/events/emit.py", 118, 228,
         "Targeted read: event append path and delivery fan-out; no request-level dedupe in this function."),
        ("src/tests/services/test_doi_lich_nhanh_db.py", 1, 351,
         "Full-file read: database tests for quick-reschedule, same-key replay, capacity and check-in; not run."),
        ("src/tests/unit/test_doi_lich_nhanh.py", 1, 98,
         "Full-file read: pure quick-reschedule slot and clock tests; not run."),
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
        "round": 51,
        "report_version": "v0.74",
        "snapshot_sha": SHA,
        "mode": "read_only_exact_main_scoped_semantic_review",
        "scope": [
            "quick reschedule UI, BFF and API idempotency-key flow",
            "shared appointment transition read/update/history/event path",
            "current unit and database tests for quick rescheduling",
        ],
        "method": "Immutable pinned Git blobs via git show. Recorded source ranges are line-checked and file SHA-256 checked. Tests were read-not-run. No ClinicAI application/runtime/API/DB/provider/VPS/production/secrets/PHI was accessed.",
        "result": {
            "new_findings": ["CLIN-059"],
            "extended_findings": [],
            "deduplicated": [
                "The same-key response-loss replay remains CLIN-057; CLIN-059 is the distinct lost-update case where two different requested target slots each use a different key and race on the same still-eligible appointment status.",
                "The GET screen's slot capacity is advisory and the shared service/DB guard rechecks it on write; this review does not certify capacity concurrency beyond existing database guards.",
            ],
            "held_candidates": [
                "Whether the desired product policy is last-write-wins or conflict-on-stale-edit should be confirmed; an explicit optimistic concurrency token is recommended for truthful transition history even if the user may retry after refresh.",
            ],
            "full_source_audit_complete": False,
        },
        "full_files": [x for x in coverage_items if x["full_read"]],
        "targeted_traces": [x for x in coverage_items if not x["full_read"]],
        "reviewer_note": "Round 51 is a scoped static review of appointment rescheduling and not a concurrency reproduction or full booking audit. CLIN-059 is separated from CLIN-057 because a stable replay receipt does not prevent two different intents from overwriting a still-eligible row.",
    }
    save("blocks/round51.coverage.json", coverage)
    (ROOT / "blocks/round51.md").write_text(
        f"""# Round 51 — concurrent appointment reschedule

Source SHA: `{SHA}`. Review used immutable Git blobs via `git show`. Tests were read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- **Added CLIN-059 MEDIUM:** the appointment transition reads an appointment without locking it, builds a reschedule patch from that snapshot, and updates with a predicate that checks only appointment ID, clinic and allowed status. Two concurrent reschedules to different target slots can both start from `CONFIRMED`/`SCHEDULED`; because the status stays eligible, the later UPDATE can overwrite the earlier one.
- Both transactions write `appointment_doi_lich` and `appointment.rescheduled` using the original in-memory `appt` snapshot. The second history row may therefore say old slot → target B even though target A was already committed before B. The quick-reschedule UI's idempotency key includes the chosen target, so different targets do not share one key.
- This is distinct from CLIN-057's same-intent replay after a lost response. A stable receipt prevents duplicate execution of one command; it does not detect two different commands based on the same stale appointment version. No database interleaving or production occurrence was reproduced.

## Recommendation and validation

Return an appointment version or `updated_at` with the GET projection and require it on reschedule. Under a row lock or compare-and-swap predicate, reject a stale expected version with 409 before writing. Build the from→to history and event from the locked/current row. A deterministic two-connection test should race two different targets, assert one wins and one gets 409, then verify the current appointment, contiguous history and single accepted event. Keep same-key replay covered separately.

Exact source ranges, hashes and read coverage are in `blocks/round51.coverage.json` and `PHAT-HIEN.json`. Tests were read-not-run. Full source audit remains incomplete.
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
        note = f"Round 51 exact-main {ranges}; see blocks/round51.coverage.json."
        if "Round 51 exact-main" not in record.get("method", ""):
            record["method"] = (record.get("method", "") + " | " + note).strip(" |")
        record["round51_note"] = item["outcome"]
    manifest["last_updated_round"] = 51
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
        "report_version": "v0.74",
        "phase": "round51_v074_reschedule_concurrency_audit_open",
        "report_round_summary": "Round 51 adds CLIN-059: concurrent reschedules to different targets can overwrite a still-eligible appointment and record stale from-slots; this is static and not runtime reproduced.",
        "next_action": "Continue exact-main review of unread/structurally scanned code, prioritizing object authorization, payment/refund/reconciliation invariants, clinical transitions, migrations/restore, retry receipts, freshness and worker recovery. Keep full_source_audit_complete=false until scope and validation gaps are actually closed.",
        "report_status": "Round 51 evidence integrated; v0.74 report-only QA and portable package refresh pending; full source audit remains incomplete.",
        "full_source_audit_complete": False,
        "round51": {
            "status": "integrated_static_review_report_qa_pending_audit_open",
            "notes": "blocks/round51.md",
            "coverage": "blocks/round51.coverage.json",
            "new_findings": ["CLIN-059"],
            "extended_findings": [],
            "tests": "Quick-reschedule unit and DB tests read-not-run; no concurrent different-target test executed.",
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
    state["artifacts"]["integration_script"] = "Round51 integrated; v0.74 report-only QA and audit-only ZIP refresh pending."
    state["artifacts"]["qa"] = "Pending v0.74 report-only validator and browser check; application behavior not validated."
    state["package"].update({"status": "pending", "file_count": None, "integrity": "Pending v0.74 audit-only package rebuild after report QA."})
    state["portable_bundle_status"] = "Pending final v0.74 audit-only package rebuild and verification."
    save("STATE.json", state)

    summary = "Round 51 adds CLIN-059 about concurrent reschedules to different targets overwriting a still-eligible appointment and misrecording the transition. Static inference only; tests read-not-run."
    (ROOT / "TIEP-TUC.md").write_text(
        "# CURRENT HANDOFF — v0.74, Round 51\n\n"
        f"Evidence source: immutable Git SHA `{SHA}` in `{REPO}`. Read source only with `git show <SHA>:<path>`; do not use working-tree WIP as evidence. Only edit audit artifacts here. Do not run ClinicAI runtime/API/DB/provider/VPS/production or inspect secrets/PHI.\n\n"
        f"{summary} Evidence and test limits are in `blocks/round51.md`, `blocks/round51.coverage.json`, `PHAT-HIEN.json` and `MAIN-PHAM-VI.json`.\n\n"
        "Full source audit remains incomplete. Path counters are inventory states, not semantic coverage. v0.74 report-only QA and audit-only ZIP refresh are pending. Resume from `BAT-DAU-TU-DAY.md` and `STATE.json`.\n"
    )
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(
        "# Bắt đầu từ đây — checkpoint v0.74, Round 51\n\n"
        "Đọc `TIEP-TUC.md`, `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `blocks/round51.md` và `blocks/round51.coverage.json`. Source chỉ từ SHA `" + SHA + "` qua `git show` trong worktree audit.\n\n"
        f"{summary} Không chạy runtime/DB; tests read-not-run. v0.74 report/package QA pending.\n\n"
        "**Full source audit chưa hoàn tất.** Path counters không phải phần trăm đã hiểu hành vi; chỉ sửa audit artifacts. Tiếp tục theo `STATE.json.next_action`.\n"
    )
    with (ROOT / "NHAT-KY.md").open("a") as handle:
        handle.write(
            "\n\n## Round 51 — 20/10/2026, v0.74 integration\n\n"
            f"Static exact-main review at SHA `{SHA}`. Added CLIN-059: simultaneous reschedules to different targets can both pass while status remains eligible, allowing a later write to overwrite the earlier target and recording stale from-slot history. No runtime/production occurrence is claimed. Related tests were read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact ranges are in `blocks/round51.coverage.json`; full source audit remains incomplete. Report-only QA/package refresh pending.\n"
        )
    print(f"Integrated Round 51: {len(findings)} findings; {len(coverage_items)} path coverage records; full audit remains open")


if __name__ == "__main__":
    main()
