"""Integrate the Round 48 read-only exact-main review into audit artifacts."""
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


def add_proofs(finding: dict, specs: list[tuple[str, int, int, str]]) -> None:
    for path, start, end, detail in specs:
        item = proof(path, start, end, detail)
        key = (path, start, end)
        if not any((x["path"], x["line"], x["end_line"]) == key for x in finding["evidence"]):
            finding["evidence"].append({k: item[k] for k in ("path", "line", "end_line", "detail")})
        main_items = finding["main_validation"].setdefault("evidence", [])
        if not any((x["path"], x["line"], x["end_line"]) == key for x in main_items):
            main_items.append({k: item[k] for k in ("path", "line", "end_line", "sha256", "excerpt")})
        finding.setdefault("source_hashes", {})[path] = item["sha256"]


def append_once(text: str, addition: str) -> str:
    return text if addition in text else text + addition


def main() -> None:
    findings = load("PHAT-HIEN.json")
    by_id = {item["id"]: item for item in findings}
    fe002_specs = [
        ("src/dashboard/app/(dashboard)/_lam-viec/dung-chip-lieu-trinh.ts", 18, 40,
         "The hook stores the query key with the last successful chip, but after a new batch or failed refresh it keeps the prior value; the returned value is not checked against the current key and has no stale/error marker."),
        ("src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx", 354, 356,
         "The doctor examination queue mounts the shared treatment-plan chip hook for its currently displayed visits."),
        ("src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx", 245, 247,
         "The service-room screen mounts the same hook for its arriving and queued visits."),
        ("src/dashboard/app/(dashboard)/reception/queue/QueueBoard.tsx", 261, 268,
         "The reception board derives a current visit batch and mounts the same hook for it."),
        ("src/dashboard/tests/lieu-trinh-c2-boundary.test.mts", 153, 175,
         "The boundary test checks one batched request and the three callers, but this test contains no stale-key or rejected-refresh assertion; read only, not run."),
    ]
    sec11_specs = [
        ("src/dashboard/app/api/lieu-trinh/chip/route.ts", 1, 19,
         "The complete Next route accepts a caller-provided visit-id batch, caps the text, and proxies it to FastAPI; it adds no patient-assignment check."),
        ("src/clinicai/api/v1/routers/lieu_trinh.py", 53, 61,
         "The FastAPI GET depends on authenticated identity and forwards the supplied visit-id list to the service."),
        ("src/clinicai/services/lieu_trinh_service.py", 54, 59,
         "QUYEN_DOC includes clinical/registration capabilities as well as service collection and reception check-in; the read gate is capability-based."),
        ("src/clinicai/services/lieu_trinh_service.py", 152, 166,
         "The service parses at most 300 unique UUIDs and drops malformed values; this is an input bound, not an assignment check."),
        ("src/clinicai/services/lieu_trinh_service.py", 453, 456,
         "The shared read guard checks QUYEN_DOC only."),
        ("src/clinicai/services/lieu_trinh_service.py", 672, 713,
         "The chip query scopes to identity.clinic_id and supplied visit IDs, then reads service-order and patient IDs without calling the secretary/doctor assignment helper."),
        ("src/clinicai/services/lieu_trinh_service.py", 715, 746,
         "The response maps treatment/service name, session count, completion state and prepaid remainder back to each supplied visit."),
        ("src/tests/services/test_lieu_trinh_c2_db.py", 58, 76,
         "The integration test exercises a receptionist reading a valid chip and malformed ID, but does not test an unassigned secretary or another doctor's visit; read only, not run."),
    ]
    coverage_specs = [
        ("src/dashboard/app/(dashboard)/_lam-viec/dung-chip-lieu-trinh.ts", 1, 41,
         "Full-file read: shared chip hook."),
        ("src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx", 354, 356,
         "Active caller range: doctor examination queue."),
        ("src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx", 245, 247,
         "Active caller range: service-room queue."),
        ("src/dashboard/app/(dashboard)/reception/queue/QueueBoard.tsx", 261, 268,
         "Active caller range: reception queue and hook invocation."),
        ("src/dashboard/tests/lieu-trinh-c2-boundary.test.mts", 1, 192,
         "Full-file read: boundary coverage for the hook and its three callers; not run."),
        ("src/dashboard/app/api/lieu-trinh/chip/route.ts", 1, 19,
         "Full-file read: Next BFF route."),
        ("src/clinicai/api/v1/routers/lieu_trinh.py", 53, 61,
         "Targeted route trace: FastAPI identity and forwarding."),
        ("src/clinicai/services/lieu_trinh_service.py", 54, 59,
         "Targeted trace: treatment-plan read capability set."),
        ("src/clinicai/services/lieu_trinh_service.py", 152, 166,
         "Targeted trace: visit UUID-list parsing and cap."),
        ("src/clinicai/services/lieu_trinh_service.py", 453, 456,
         "Targeted trace: shared read guard."),
        ("src/clinicai/services/lieu_trinh_service.py", 672, 746,
         "Targeted trace: chip query, clinic/visit scoping, and returned data."),
        ("src/dashboard/lib/lieu-trinh-cskh.ts", 65, 85,
         "Targeted read: frontend chip response contract."),
        ("src/tests/services/test_lieu_trinh_c2_db.py", 1, 172,
         "Full-file read: DB test setup and assertions; not run."),
        ("src/tests/services/test_lieu_trinh_db.py", 294, 298,
         "Targeted read: UUID-list parser tests; not run."),
    ]

    fe002 = by_id["FE-002"]
    fe002["summary"] = append_once(
        fe002["summary"],
        " Round 48 bổ sung chip liệu trình dùng chung ở hàng chờ bàn khám, phòng dịch vụ và tiếp đón: khi tập lượt đổi hoặc refresh bị lỗi, hook giữ response thành công trước đó; state có lưu key nhưng giá trị trả ra không so key hiện tại và không có dấu freshness.",
    )
    fe002["trigger"] = append_once(
        fe002["trigger"],
        " Một trong ba màn vận hành đổi batch lượt hoặc nhận refresh event, rồi request chip liệu trình lỗi sau khi trước đó đã tải thành công.",
    )
    fe002["impact"] = append_once(
        fe002["impact"],
        " Nhân viên có thể thấy chip buổi liệu trình/trả trước cũ như dữ liệu mới trên lượt còn giữ nguyên trong batch; khi batch đổi, hook cũng có thể trả state của batch trước cho tới khi một response mới thành công. Chưa tái hiện trên browser/runtime.",
    )
    fe002["validation"]["result"] = append_once(
        fe002["validation"]["result"],
        " Round 48 đọc hook, ba caller và boundary test tại exact-main: catch biến lỗi thành null, state chỉ cập nhật khi có data, còn giá trị trả về không so sánh key lưu với key hiện tại. Test boundary chỉ kiểm tra batch-call/caller, không có assertion cho freshness/rejected refresh; test được đọc, không chạy.",
    )
    fe002["validation"]["limitations"] = append_once(
        fe002["validation"]["limitations"],
        " Round 48 là static-only; chưa fault-inject React fetch, chưa quan sát thời gian stale hoặc hành vi production.",
    )
    fe002["recommendation"] = append_once(
        fe002["recommendation"],
        " Với chip theo batch, chỉ trả data gắn đúng key hiện tại; khi giữ data cũ để tránh nhấp nháy, hiển thị freshness và lỗi refresh. Thêm component test đổi key, trả lỗi, và xác nhận chip cũ không được gán cho batch mới.",
    )
    fe002["acceptance"] = append_once(
        fe002["acceptance"],
        " Cho hook tải batch A thành công, đổi sang batch B rồi làm request B reject: không hiển thị chip của A cho B; nếu lượt chung còn trong batch, dữ liệu cũ phải có nhãn stale và lỗi refresh. Response B thành công thay đúng state và gỡ nhãn stale.",
    )
    fe002["related_tests"].append(
        "src/dashboard/tests/lieu-trinh-c2-boundary.test.mts:153-175 — xác nhận batch-call và ba caller, nhưng không kiểm key đổi hoặc refresh reject; đọc, không chạy."
    ) if not any("lieu-trinh-c2-boundary.test.mts" in x for x in fe002["related_tests"]) else None
    add_proofs(fe002, fe002_specs)

    sec11 = by_id["SEC-011"]
    sec11["summary"] = append_once(
        sec11["summary"],
        " Round 48 bổ sung GET chip liệu trình theo lô visit_id: route chỉ yêu cầu identity; service gate QUYEN_DOC rồi query theo clinic + danh sách visit caller gửi, trả tên dịch vụ/số buổi/đã làm/còn trả trước, không gọi assignment helper. Đây cùng invariant patient/visit assignment, không kết luận cross-clinic.",
    )
    sec11["trigger"] = append_once(
        sec11["trigger"],
        " Tài khoản có một capability trong QUYEN_DOC gửi visit ID cùng clinic không thuộc bệnh nhân/bác sĩ được phân tới GET /lieu-trinh/chip.",
    )
    sec11["impact"] = append_once(
        sec11["impact"],
        " Có thể đọc metadata liệu trình theo visit cùng clinic ngoài assignment: dịch vụ, số buổi, trạng thái đã làm và số buổi đã trả trước. Không thấy query vượt clinic_id; chưa kiểm JWT/runtime hoặc chứng minh production.",
    )
    sec11["validation"]["result"] = append_once(
        sec11["validation"]["result"],
        " Round 48 trace đầy đủ BFF chip → FastAPI identity → QUYEN_DOC guard → truy vấn clinic_id + supplied visit IDs → response projection. UUID list có cap 300 và bỏ mã lỗi định dạng; các giới hạn này không thay assignment check. Test DB hiện chỉ xác nhận receptionist đọc được fixture hợp lệ, chưa có case secretary assignment âm; test đọc, không chạy.",
    )
    sec11["validation"]["limitations"] = append_once(
        sec11["validation"]["limitations"],
        " Round 48 chưa chạy JWT/DB matrix cho doctor/secretary A đọc visit của doctor B; đây là static dataflow cùng clinic, không phải khai thác đã tái hiện.",
    )
    sec11["recommendation"] = append_once(
        sec11["recommendation"],
        " Áp cùng patient/visit assignment guard cho chip batch trước khi trả thông tin liệu trình; giữ cap 300 như bảo vệ tài nguyên riêng, và kiểm quyền theo role/capability trên từng visit.",
    )
    sec11["acceptance"] = append_once(
        sec11["acceptance"],
        " JWT/DB matrix synthetic: người có QUYEN_DOC đọc được lượt trong scope; TKYK bác sĩ A bị từ chối hoặc chỉ nhận dữ liệu rỗng đối với lượt clinic cùng doctor B; batch hỗn hợp không làm rò metadata của lượt ngoài scope; scope toàn clinic theo chính sách vẫn hoạt động.",
    )
    add_proofs(sec11, sec11_specs)

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
        if detail not in row["outcomes"]:
            row["outcomes"].append(detail)
    coverage_items = []
    for row in coverage_by_path.values():
        row["read_ranges"].sort(key=lambda r: (r["start"], r["end"]))
        row["outcome"] = " ".join(row.pop("outcomes"))
        coverage_items.append(row)

    coverage = {
        "schema_version": 1,
        "round": 48,
        "report_version": "v0.71",
        "snapshot_sha": SHA,
        "mode": "read_only_exact_main_scoped_semantic_review",
        "scope": [
            "treatment-plan chip authorization from BFF through service and DB test",
            "stale batch-key behavior in shared treatment-plan chip hook and active callers",
        ],
        "method": "Immutable pinned Git blobs via git show. Every recorded range is line-checked and source SHA-256 checked. Tests were read-not-run. No application code, ClinicAI tests/runtime/API/DB/provider/VPS/production/secrets/PHI was touched.",
        "result": {
            "new_findings": [],
            "extended_findings": ["FE-002", "SEC-011"],
            "deduplicated": [
                "The chip assignment gap is part of existing SEC-011's patient/visit object-level authorization invariant; no duplicate finding was added.",
                "Stale chip data is folded into FE-002's existing stale-state/freshness finding; no duplicate finding was added.",
                "The 300-visit cap, UUID parsing and clinic_id filter are real controls but do not establish per-patient assignment; no resource-abuse or cross-clinic finding was added.",
            ],
            "held_candidates": [
                "No cross-clinic access or production exposure was established.",
                "No runtime stale interval was measured; stale UI conclusion is based on exact-main state transitions only.",
            ],
            "full_source_audit_complete": False,
        },
        "full_files": [x for x in coverage_items if x["full_read"]],
        "targeted_traces": [x for x in coverage_items if not x["full_read"]],
        "reviewer_note": "Round 48 is a narrow static review of one shared UI hook and one authorization dataflow, not a full repository read or runtime validation. Path states are inventory only.",
    }
    save("blocks/round48.coverage.json", coverage)
    (ROOT / "blocks/round48.md").write_text(
        f"""# Round 48 — treatment-plan chip authorization and freshness

Source SHA: `{SHA}`. All source evidence comes from immutable Git blobs via `git show`; no primary-checkout source was used. This is a narrow static review. Related tests were read, not run. No ClinicAI application, API, database, provider, VPS, production, secrets or PHI was accessed.

## Findings

- **Extended SEC-011 (HIGH):** the treatment-plan chip GET accepts a batch of caller-supplied visit IDs. FastAPI checks identity, and the service checks `QUYEN_DOC`, then scopes SQL by clinic and those visit IDs. It returns service, session and prepaid metadata without a patient/doctor-assignment check. The list is capped at 300 and malformed UUIDs are discarded, but neither bounds resource use nor establishes object assignment. This remains a same-clinic static authorization concern; cross-clinic access and production exposure are not claimed.
- **Extended FE-002 (MEDIUM):** the shared hook stores the batch key with the last successful response but returns its data without checking that key against the current batch. A rejected fetch leaves prior state in place and exposes no stale/error marker. The hook is used in doctor queue, service-room and reception screens. Boundary tests check batching/callers, not key changes or rejected refreshes.

## Dedupe and limits

Both observations extend existing findings, so Round 48 adds no new finding ID. The 300-visit cap, clinic filter and UUID validation were retained as controls. Tests were read only, not run; no JWT matrix, React fault injection or production observation was performed. Exact ranges, line counts and source hashes are in `blocks/round48.coverage.json`; relevant excerpts are embedded in `PHAT-HIEN.json`.

Full source audit remains incomplete. These path counters are not a semantic-completion percentage.
"""
    )

    manifest = load("MAIN-PHAM-VI.json")
    for record in manifest["files"]:
        item = coverage_by_path.get(record["path"])
        if not item:
            continue
        if item["sha256"] != record.get("sha256") and record.get("sha256"):
            raise ValueError(f"Manifest SHA mismatch for {record['path']}")
        if item["full_read"]:
            record["status"] = "read"
            record["full_file_read"] = True
        elif record["status"] in {"scanned", "inventoried"}:
            record["status"] = "traced"
        ranges = ", ".join(f"{r['start']}–{r['end']}" for r in item["read_ranges"])
        note = f"Round 48 exact-main {ranges}; see blocks/round48.coverage.json."
        if "Round 48 exact-main" not in record.get("method", ""):
            record["method"] = (record.get("method", "") + " | " + note).strip(" |")
        record["round48_note"] = item["outcome"]
    manifest["last_updated_round"] = 48
    save("MAIN-PHAM-VI.json", manifest)
    save("PHAT-HIEN.json", findings)

    main_counts = Counter(x["status"] for x in manifest["files"])
    code_files = [x for x in manifest["files"] if Path(x["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(x["status"] for x in code_files)
    finding_counts = Counter(x["main_validation"]["status"] for x in findings)
    severity_counts = Counter(x["severity"] for x in findings)
    state = load("STATE.json")
    state.update({
        "updated_at": "2026-10-20",
        "status": "in_progress",
        "report_version": "v0.71",
        "phase": "round48_v071_treatment_chip_auth_and_freshness_audit_open",
        "report_round_summary": "Round 48 adds no finding ID; extends FE-002 with treatment-plan chip stale-key behavior and SEC-011 with the chip endpoint's missing patient/doctor assignment check.",
        "next_action": "Continue exact-main review across unreviewed and structurally scanned code, prioritizing object-level authorization, clinical lifecycle transitions, migration/restore semantics, retry receipts, and UI freshness. Keep full_source_audit_complete=false until required source scope and validation gaps are actually closed.",
        "report_status": "Round 48 evidence integrated; v0.71 report-only QA and portable package refresh pending; full source audit remains incomplete.",
        "full_source_audit_complete": False,
        "round47": {**state.get("round47", {}), "status": "report_qa_and_package_verified_audit_open"},
        "round48": {
            "status": "integrated_static_review_report_qa_pending_audit_open",
            "notes": "blocks/round48.md",
            "coverage": "blocks/round48.coverage.json",
            "new_findings": [],
            "extended_findings": ["FE-002", "SEC-011"],
            "tests": "Treatment-plan DB and frontend boundary tests read-not-run; no ClinicAI tests executed in Round 48.",
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
    state["artifacts"]["integration_script"] = "Round48 integrated; v0.71 report-only QA and audit-only ZIP refresh pending."
    state["artifacts"]["qa"] = "Pending v0.71 report-only validator and browser check; application behavior not validated."
    state["package"].update({"status": "pending", "file_count": None, "integrity": "Pending rebuild after report QA and final handoff checkpoint."})
    state["portable_bundle_status"] = "Pending final v0.71 audit-only package rebuild and verification."
    save("STATE.json", state)

    handoff = (
        "# CURRENT HANDOFF — v0.71, Round 48\n\n"
        f"Evidence source: immutable Git SHA `{SHA}` in `{REPO}`. The primary checkout may contain user WIP; do not use it as evidence. Read source only with `git show <SHA>:<path>`. Only edit audit artifacts in this directory; do not run ClinicAI tests/runtime/API/DB/provider/VPS/production or inspect secrets/PHI.\n\n"
        "Round 48 extends FE-002 (stale treatment-plan chip batch) and SEC-011 (same-clinic visit assignment on chip GET); no new finding ID. Exact ranges/hashes and dedupe decisions are in `blocks/round48.md`, `blocks/round48.coverage.json`, `PHAT-HIEN.json` and `MAIN-PHAM-VI.json`. Tests read-not-run.\n\n"
        "Full source audit remains incomplete. Path counters are inventory states, not semantic coverage. Report-only QA and audit-only package refresh are pending. Resume with `BAT-DAU-TU-DAY.md`, then read `STATE.json` and continue from exact pinned main.\n"
    )
    (ROOT / "TIEP-TUC.md").write_text(handoff)
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(
        "# Bắt đầu từ đây — checkpoint v0.71, Round 48\n\n"
        "Đọc `TIEP-TUC.md`, `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `blocks/round48.md` và `blocks/round48.coverage.json`. Source evidence chỉ từ SHA `" + SHA + "` qua `git show` trong worktree audit; không dùng working-tree WIP làm bằng chứng.\n\n"
        "Round 48 mở rộng FE-002 và SEC-011; không thêm ID phát hiện mới. Tests read-not-run; không runtime/production. HTML QA và ZIP refresh pending.\n\n"
        "**Full source audit chưa hoàn tất.** Path counters không phải phần trăm đã hiểu hành vi; chỉ sửa audit artifacts. Tiếp tục theo `STATE.json.next_action`.\n"
    )
    with (ROOT / "NHAT-KY.md").open("a") as handle:
        handle.write(
            "\n\n## Round 48 — 20/10/2026, v0.71 integration\n\n"
            f"Static exact-main review at SHA `{SHA}`. No new finding ID; extended FE-002 with the shared treatment-plan chip's stale batch-key behavior and SEC-011 with the chip read endpoint's same-clinic object-assignment gap. Tests read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact coverage is in `blocks/round48.coverage.json`; full source audit remains incomplete. Report-only QA/package refresh pending.\n"
        )
    print(f"Integrated Round 48: {len(findings)} findings; {len(coverage_items)} path coverage records; full audit remains open")


if __name__ == "__main__":
    main()
