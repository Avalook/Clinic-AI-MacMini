"""Integrate round-23 clinical form validation trace on exact pinned main."""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import integrate_round23_pharmacy as r23

ROOT = Path(__file__).resolve().parent
SNAPSHOT = r23.SNAPSHOT
PINNED_SHA = r23.PINNED_SHA
prior = r23.prior
CODE_SUFFIXES = prior.CODE_SUFFIXES


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    actual = subprocess.check_output(["git", "-C", str(SNAPSHOT), "rev-parse", "HEAD"], text=True).strip()
    if actual != PINNED_SHA:
        raise SystemExit(f"Pinned source mismatch: expected {PINNED_SHA}, got {actual}")
    manifest = read_json("MAIN-PHAM-VI.json")
    if manifest["sha"] != PINNED_SHA:
        raise SystemExit("MAIN-PHAM-VI.json does not reference pinned main")
    by_path = {row["path"]: row for row in manifest["files"]}
    findings = read_json("PHAT-HIEN.json")
    by_id = {row["id"]: row for row in findings}
    if "CLIN-041" in by_id:
        raise SystemExit("CLIN-041 already exists; refusing duplicate integration")

    limits = (
        "Static exact-main trace only. The route requires normal authenticated clinical permission, but no malformed request was sent. "
        "No ClinicAI test, DB runtime, production, secret or patient record was used. No evidence shows the current UI emits an unknown key; "
        "the finding concerns server-side validation and persistence behavior if a client submits such a payload."
    )
    finding = prior.finding(
        id="CLIN-041",
        title="Form Engine lưu ô và giá trị ngoài khung biểu mẫu nhưng giao diện không hiển thị",
        severity="MEDIUM",
        level="confirmed_static",
        category="clinical_form_payload_validation",
        summary=(
            "Route nhận du_lieu dưới dạng dict[str, Any] và chuyển nguyên payload cho FormEngineService. "
            "Hàm _kiem_du_lieu chỉ kiểm mỗi mục có gia_tri và nguon thuộc allowlist; validator không nhận "
            "khung/version để kiểm mã ô có tồn tại trong form hay giá trị có đúng kiểu/lựa chọn. Service lưu "
            "JSON vào form_instance. Khi đọc và render, UI chỉ lặp các trường trong khung đã khai báo."
        ),
        trigger=(
            "Client có quyền sửa phiếu gửi key không thuộc khung của đúng phiên bản form, hoặc gửi giá trị "
            "không tương thích kiểu, nhưng cấu trúc vẫn có gia_tri và nguon hợp lệ."
        ),
        impact=(
            "Payload sai schema có thể được ghi vào dữ liệu phiếu mà giao diện chính không render; nhân viên "
            "có thể không biết phần dữ liệu đó tồn tại hoặc bị bỏ qua khi đọc/in. Đây là rủi ro integrity có "
            "điều kiện trên request không hợp lệ; chưa thấy UI hiện tại phát payload sai và chưa chứng minh "
            "hồ sơ production bị ảnh hưởng."
        ),
        recommendation=(
            "Trong transaction, nạp đúng form_definition và version đã ghim rồi validate toàn bộ key, kiểu, "
            "enum/range, độ dài và cấu trúc lồng nhau theo schema. Từ chối key lạ/value sai kiểu trước khi "
            "tăng revision, lưu JSON hoặc phát event; trả lỗi có thể sửa được cho client."
        ),
        acceptance=(
            "Trên DB disposable, payload có key lạ, kiểu sai, enum ngoài danh sách hoặc value sai form-version "
            "trả 422 và không thay du_lieu/du_lieu_dang_sua, revision, lịch sử hay event. Payload hợp lệ theo "
            "form version được chấp nhận; GET/in chỉ trả các giá trị đã validate và render theo cùng schema."
        ),
        note=(
            "Static cross-layer trace: API model dùng dict[str, Any]; _kiem_du_lieu kiểm cấu trúc tối thiểu "
            "trước khi service nạp khung/version; JSON được lưu nguyên trạng; UI chỉ render các field trong khung. "
            "Test hiện có kiểm source allowlist nhưng không kiểm key lạ/giá trị sai schema. Không gửi request runtime."
        ),
        refs=[
            ("src/clinicai/api/v1/routers/phieu.py", 31, 36,
             "LuuBody khai du_lieu dạng dict[str, Any], không có schema theo form."),
            ("src/clinicai/api/v1/routers/phieu.py", 83, 97,
             "Route chuyển nguyên payload du_lieu vào service lưu nháp."),
            ("src/clinicai/services/form_engine_service.py", 556, 576,
             "luu_nhap gọi validator trước khi resolve form/version cụ thể."),
            ("src/clinicai/services/form_engine_service.py", 1469, 1479,
             "_kiem_du_lieu chỉ yêu cầu gia_tri và nguon nằm trong allowlist; không nhận khung để kiểm field/value schema."),
            ("src/clinicai/services/form_engine_service.py", 628, 656,
             "Service ghi du_lieu/du_lieu_dang_sua vào form_instance sau validation nông."),
            ("src/clinicai/services/form_engine_service.py", 1417, 1437,
             "Read response giữ và trả dữ liệu JSON đã lưu."),
            ("src/dashboard/app/(dashboard)/_lam-viec/PhieuKetQua.tsx", 544, 565,
             "React render lặp các ô đã khai trong khung, bỏ qua key ngoài schema."),
            ("src/tests/services/test_form_engine_db.py", 310, 324,
             "Test từ chối nguon lạ; không kiểm unknown field hoặc sai kiểu/enum."),
        ],
        tests=[
            "src/tests/services/test_form_engine_db.py:310-324 — đã đọc, không chạy; chỉ kiểm nguồn dữ liệu lạ.",
            "src/dashboard/lib/phieu-ket-qua.test.mts — đã đọc, không chạy; không bao phủ server-side field schema validation.",
        ],
        related=[
            {"id": "CLIN-038", "relationship": "CLIN-038 kiểm form_id gắn sai service; CLIN-041 kiểm từng field/value trong payload theo schema của form đã chọn."},
            {"id": "CLIN-039", "relationship": "CLIN-039 là lost update giữa tab; CLIN-041 là payload schema acceptance và dữ liệu bị ẩn khỏi render."},
        ],
        result=(
            "Static trace nối request model, route, validation order, persistence, read response và UI rendering. "
            "Test lân cận không cover key lạ/kiểu sai; chưa chạy malformed request hoặc DB assertion."
        ),
        limitations=limits,
    )

    state = read_json("STATE.json")
    held = state.get("held_observations", [])
    held_ids = {x.get("id") for x in held}
    requiredness = {
        "id": "CLINICAL-FORM-REQUIREDNESS-001",
        "classification": "held_clinical_policy_design_gap",
        "severity_assessment": "Not classified until a clinician/product owner defines required and conditional fields by form/version.",
        "snapshot_sha": PINNED_SHA,
        "question": "Dynamic forms have no requiredness metadata. Empty fields are surfaced as reminders, while completion can still reach READY and emit the result event. Which fields must block completion for each clinical form and scenario?",
        "impact": "Without an approved required-field policy, the audit cannot distinguish an intentional warning from an incomplete clinical record. No field was labelled clinically mandatory in the inspected contract; no patient record or production workflow was examined.",
        "evidence": [
            {"path": "src/clinicai/services/form_engine_service.py", "lines": "768,868-899,1552-1570", "sha256": prior.source("src/clinicai/services/form_engine_service.py")[1]},
            {"path": "src/dashboard/lib/phieu-ket-qua.ts", "lines": "137-149", "sha256": prior.source("src/dashboard/lib/phieu-ket-qua.ts")[1]},
        ],
        "not_promoted_reason": "No clinically approved requiredness/conditionality contract was found; labeling current warning behavior a defect would assume medical policy.",
        "next": "Clinical owner defines required/conditional fields by form and version. Then validate server-side and test warning-only versus blocked completion, including conditional branches and revision/event behavior.",
    }
    if requiredness["id"] not in held_ids:
        held.append(requiredness)
    findings.append(finding)
    write_json("PHAT-HIEN.json", findings)
    write_json("blocks/round23_clinical_findings.json", [finding])

    full_reads = {
        "src/clinicai/phieu_kham/khung.py": "Full 391-line read; dynamic form frame/model behavior reviewed in round 23.",
    }
    ranges = [
        ("src/clinicai/api/v1/routers/phieu.py", 31, 36, "Request body accepts a generic dictionary."),
        ("src/clinicai/api/v1/routers/phieu.py", 83, 97, "Route passes raw form data to the service."),
        ("src/clinicai/services/form_engine_service.py", 556, 576, "Save path validation order before loading exact form version."),
        ("src/clinicai/services/form_engine_service.py", 628, 656, "Persisted JSON fields after shallow validation."),
        ("src/clinicai/services/form_engine_service.py", 768, 768, "Completion path checks remaining values."),
        ("src/clinicai/services/form_engine_service.py", 868, 899, "Completion behavior and READY/result event path."),
        ("src/clinicai/services/form_engine_service.py", 1417, 1437, "Read response returns stored form data."),
        ("src/clinicai/services/form_engine_service.py", 1469, 1479, "Shallow field/value validator."),
        ("src/clinicai/services/form_engine_service.py", 1552, 1570, "Empty fields are enumerated as reminders."),
        ("src/dashboard/app/(dashboard)/_lam-viec/PhieuKetQua.tsx", 544, 565, "Rendering iterates the declared frame fields."),
        ("src/dashboard/lib/phieu-ket-qua.ts", 137, 149, "Client labels missing values as reminders only."),
        ("src/tests/services/test_form_engine_db.py", 310, 324, "Existing negative test covers unknown source, not unknown field/value schema."),
    ]
    all_ranges: dict[str, list[tuple[int, int, str]]] = {}
    for item in finding["main_validation"]["evidence"]:
        all_ranges.setdefault(item["path"], []).append((item["line"], item["end_line"], item["detail"]))
    for item in requiredness["evidence"]:
        for part in item["lines"].split(","):
            bits = part.split("-")
            a = int(bits[0]); b = int(bits[1]) if len(bits) > 1 else a
            all_ranges.setdefault(item["path"], []).append((a, b, f"Held {requiredness['id']}; see STATE.json for full limits."))
    for path, note in full_reads.items():
        lines, _ = prior.source(path)
        all_ranges.setdefault(path, []).append((1, len(lines), note))
    for path, start, end, detail in ranges:
        all_ranges.setdefault(path, []).append((start, end, detail))

    rank = {"inventoried": 0, "scanned": 1, "traced": 2, "read": 3, "excluded": 4}
    coverage_files = []
    for path, spans in sorted(all_ranges.items()):
        if path not in by_path:
            raise SystemExit(f"Reviewed path missing from ledger: {path}")
        lines, digest = prior.source(path)
        row = by_path[path]
        if row.get("sha256") != digest or row.get("lines") != len(lines):
            raise SystemExit(f"Main ledger fingerprint mismatch: {path}")
        if any(a < 1 or b < a or b > len(lines) for a, b, _ in spans):
            raise SystemExit(f"Reviewed range is outside pinned source: {path} ({len(lines)} lines)")
        old = row["status"]
        is_full = path in full_reads
        status = "read" if is_full else ("traced" if rank[old] < rank["traced"] else old)
        row["status"] = status
        mode = "full_file_read" if is_full else "targeted_semantic_trace"
        row["method"] = f"{row.get('method', '')} | Round 23 clinical {mode}: " + "; ".join(f"{a}-{b}" for a,b,_ in spans)
        coverage_files.append({
            "path": path, "status": status, "prior_status": old,
            "read_level_this_round": mode, "full_file_read_this_round": is_full,
            "ranges": [{"start": a, "end": b, "purpose": purpose} for a,b,purpose in spans],
            "sha256": digest, "line_count": len(lines),
        })
    write_json("MAIN-PHAM-VI.json", manifest)
    write_json("blocks/round23_clinical_coverage.json", {
        "schema_version": 1,
        "audit": "round23_clinical_forms_form_engine_validation",
        "snapshot": {"path": str(SNAPSHOT), "sha": PINNED_SHA},
        "review_mode": "static_read_only_exact_main_cross_layer_trace",
        "scope": ["dynamic form request validation, form-version persistence/read, React rendering, completion reminders and nearby tests"],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "One MEDIUM static finding added for unknown fields/schema-incompatible values being persisted but omitted by schema-driven rendering. Requiredness policy remains held. Form khung.py was fully read; other modules in this slice were targeted, not full-file reads. No test or runtime request ran.",
        "held_observations": [requiredness["id"]],
        "files": coverage_files,
    })
    checks = read_json("KIEM-CHUNG.json")
    checked = {(row["id"], row["path"]) for row in checks["checks"]}
    for item in finding["main_validation"]["evidence"]:
        key = (finding["id"], item["path"])
        if key not in checked:
            checks["checks"].append({"id": finding["id"], "path": item["path"], "valid": True})
            checked.add(key)
    write_json("KIEM-CHUNG.json", checks)

    held_ids = {x.get("id") for x in held}
    state["held_observations"] = held
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    severity = Counter(row["severity"] for row in findings)
    levels = Counter(row["evidence_level"] for row in findings)
    main_status = Counter(row["main_validation"]["status"] for row in findings)
    state["updated_at"] = now
    state["phase"] = "round23_clinical_forms_and_pharmacy_lifecycle_checkpoint"
    state["report_version"] = "v0.45"
    state["report_round_summary"] = (
        "Round 22 thêm SEC-030 và mở rộng SEC-011; lát event/provider không thêm finding. Round 23 đã đọc trọn ba service dược/billing "
        "và khung phiếu khám, không promote hai observation theo ngưỡng/chính sách; thêm CLIN-041 về validate payload phiếu theo đúng schema/version. "
        "Không chạy ClinicAI test, DB, API, provider hoặc production trong các lát round 22–23; chỉ QA report sau khi dựng."
    )
    state["next_action"] = (
        "Continue exact-main semantic review of remaining patient/API callers, clinical form parsers and other scanned/inventoried sources. "
        "Add synthetic deny/no-write tests for CLIN-041 and test SEC-011/SEC-029/SEC-030 on disposable Supabase from pinned migrations. "
        "Resolve clinical requiredness, Bio mapping, payment clinic-wide read and list-cap policies with owners. Full source audit remains incomplete."
    )
    state["report_status"] = "v0.45_pending_report_QA; full source audit incomplete"
    state.setdefault("summary", {})["findings"] = len(findings)
    state["summary"]["severity"] = {key: severity.get(key, 0) for key in ("HIGH", "MEDIUM", "LOW")}
    state["summary"]["evidence_levels"] = {key: levels.get(key, 0) for key in ("reproduced_local", "design_gap", "confirmed_static", "hypothesis")}
    state["summary"]["main_status"] = {key: main_status.get(key, 0) for key in ("still_present_on_main", "partially_addressed_on_main", "addressed_on_main")}
    state["summary"]["main_coverage"] = {key: counts.get(key, 0) for key in ("inventoried", "read", "traced", "scanned", "excluded")}
    state["summary"]["main_read_files"] = counts["read"]
    state["summary"]["main_partial_traces"] = counts["traced"]
    state["summary"]["code_like_source_files"] = {
        "definition": "Pinned-tree paths with common source-code/web/sql/shell suffixes; includes app, tests, tooling and styles, not only runtime code.",
        "total": len(code_files), "coverage": {key: code_counts.get(key, 0) for key in ("inventoried", "traced", "scanned", "read")}, "traced_is_partial": True,
    }
    state["summary"]["reviewed_slice_v045"] = "Round 23 clinical form validation adds CLIN-041; form requiredness remains a policy/design observation. Pharmacy lifecycle adds two held observations and no finding."
    state["summary"]["new_findings_v045"] = ["CLIN-041"]
    state.setdefault("blocks", {})["round23_clinical_forms"] = {
        "status": "static form-engine review integrated; 1 MEDIUM finding, required-field policy held",
        "scope": "form request/schema validation, exact form version, JSON persistence, read/render, completion semantics and tests",
        "artifacts": "blocks/round23_clinical_findings.json; blocks/round23_clinical_coverage.json; integrate_round23_clinical.py",
        "findings": "CLIN-041 confirmed_static on pinned main; no malformed request or database test was run.",
        "next": "Validate keys/types against the pinned form version and add no-write rejection tests; clinical owner defines required fields.",
    }
    state["artifacts"]["integration_script"] = "integrate_round23_clinical.py and integrate_round23_pharmacy.py; round23 evidence/coverage in blocks/round23_*; earlier checkpoints retained."
    state["artifacts"]["qa"] = "Pending v0.45 structural/evidence, browser and audit-only package QA; application behavior not validated in round 22–23."
    state["artifacts"]["bundle_integrity"] = "Pending v0.45 audit-only package rebuild and verification."
    state["artifacts"]["html_sha256"] = "pending v0.45 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.45 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.45 package verification"
    state.setdefault("runtime_summary", {})["round23_clinical"] = "Static exact-main review only; no ClinicAI runtime/test/DB/provider/production access, secrets or patient records."
    write_json("STATE.json", state)
    print(json.dumps({
        "added_findings": ["CLIN-041"], "total_findings": len(findings),
        "severity": dict(severity), "main_status": dict(main_status),
        "coverage": dict(counts), "code_like_total": len(code_files),
        "code_like_coverage": dict(code_counts), "round23_reviewed_paths": len(coverage_files),
        "round23_full_reads": len(full_reads), "held_observations": list(held_ids), "updated_at": now,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
