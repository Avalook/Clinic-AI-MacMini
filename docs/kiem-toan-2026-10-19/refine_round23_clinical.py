"""Clarify generic Form Engine vs versioned phiếu-khám v5 coverage."""
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
    finding = next((row for row in findings if row["id"] == "CLIN-041"), None)
    if not finding:
        raise SystemExit("CLIN-041 is missing; run the initial round-23 integration first")

    finding["title"] = "Form Engine generic lưu field ngoài schema nhưng giao diện không hiển thị"
    finding["summary"] = (
        "Đường generic FormEngineService nhận du_lieu dạng dict[str, Any] và gọi _kiem_du_lieu trước khi nạp form/version. "
        "Validator chỉ kiểm mỗi mục có gia_tri và nguon thuộc allowlist; không xác minh mã field thuộc khung hay giá trị "
        "đúng kiểu/lựa chọn của form đã chọn. Service lưu JSON; UI generic render theo các field trong khung, nên field lạ "
        "có thể được lưu nhưng không xuất hiện. Đây không phải đường phiếu khám v5: v5 dùng PhieuKhamService.kiem_luu "
        "và kiểm key theo khung đã ghim."
    )
    finding["impact"] = (
        "Nếu client có quyền sửa generic form gửi payload ngoài schema, dữ liệu không hợp lệ có thể được lưu mà không "
        "hiện trong màn đọc/in generic. Không có bằng chứng UI hiện tại gửi key sai, người dùng gặp trường hợp này, "
        "hay hồ sơ v5 bị ảnh hưởng."
    )
    finding["trigger"] = (
        "Client có quyền sửa một generic Form Engine form gửi key ngoài khung hoặc giá trị sai kiểu nhưng vẫn có "
        "gia_tri và nguon hợp lệ."
    )
    finding["recommendation"] = (
        "Validate payload generic against the exact form definition and pinned version before any write or revision change. "
        "Reject unknown keys and invalid value types/enums/ranges. Keep the separate phiếu-khám v5 validator and contract tests intact."
    )
    finding["main_validation"]["note"] += (
        " Boundary clarification from round 23: CLIN-041 applies to generic FormEngineService only. The separately reviewed v5 path "
        "uses PhieuKhamService.kiem_luu with the pinned form frame and an existing test for unknown keys; no v5 finding was added."
    )
    finding["validation"]["result"] += (
        " Scope boundary checked against the separate v5 PhieuKhamService path: v5 validates against the pinned khung and its test rejects unknown keys."
    )
    finding["validation"]["limitations"] += (
        " The generic Form Engine finding does not establish a defect in the distinct versioned phiếu-khám v5 path."
    )
    write_json("PHAT-HIEN.json", findings)
    write_json("blocks/round23_clinical_findings.json", [finding])

    v5_ranges = [
        ("src/clinicai/phieu_kham/doc_chu.py", 34, 55, "Text field reader for pinned phiếu-khám v5."),
        ("src/clinicai/phieu_kham/doc_chu.py", 58, 77, "Structured form content reader."),
        ("src/clinicai/phieu_kham/doc_chu.py", 80, 109, "Version-5 typed form reader."),
        ("src/clinicai/phieu_kham/hanh_trinh.py", 623, 678, "Read lifecycle/visit history behavior."),
        ("src/clinicai/phieu_kham/ket_qua_chi_dinh.py", 79, 281, "Read result-by-order projection."),
        ("src/clinicai/phieu_kham/kiem_khung_mau.py", 69, 218, "Validate configured frame/model."),
        ("src/clinicai/phieu_kham/mang_sang.py", 81, 99, "Build clinical record projection."),
        ("src/clinicai/phieu_kham/mang_sang.py", 150, 167, "Build vital measurement projection."),
        ("src/clinicai/phieu_kham/nap.py", 25, 50, "Load initial pinned frame."),
        ("src/clinicai/services/phieu_kham_service.py", 244, 264, "Versioned v5 schema-validation entry point."),
        ("src/clinicai/services/phieu_kham_service.py", 374, 419, "Save path calls schema validation before write."),
        ("src/clinicai/api/v1/routers/phieu_kham.py", 161, 193, "Versioned phiếu-khám API contract."),
        ("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx", 92, 109, "Versioned v5 form writer."),
        ("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx", 188, 220, "Versioned v5 form reader/caller."),
        ("src/dashboard/app/api/phieu-kham/route.ts", 1, 125, "BFF path for versioned phiếu-khám API."),
        ("src/tests/services/test_phieu_kham_db.py", 245, 275, "Test rejects keys outside the pinned v5 schema; inspected, not run."),
        ("src/tests/services/test_phieu_kham_v2_db.py", 66, 90, "Tests version pinning; inspected, not run."),
        ("src/tests/unit/test_phieu_kham_khung.py", 281, 356, "Unit test for frame/schema validation; inspected, not run."),
    ]
    coverage = read_json("blocks/round23_clinical_coverage.json")
    coverage_by_path = {row["path"]: row for row in coverage["files"]}
    rank = {"inventoried": 0, "scanned": 1, "traced": 2, "read": 3, "excluded": 4}
    for path, start, end, purpose in v5_ranges:
        if path not in by_path:
            raise SystemExit(f"v5 reviewed path missing from ledger: {path}")
        lines, digest = prior.source(path)
        if start < 1 or end < start or end > len(lines):
            raise SystemExit(f"v5 range outside pinned source: {path}:{start}-{end} ({len(lines)} lines)")
        manifest_row = by_path[path]
        if manifest_row.get("sha256") != digest or manifest_row.get("lines") != len(lines):
            raise SystemExit(f"Main ledger fingerprint mismatch: {path}")
        old = manifest_row["status"]
        status = "read" if path.endswith("/khung.py") else ("traced" if rank[old] < rank["traced"] else old)
        manifest_row["status"] = status
        manifest_row["method"] = f"{manifest_row.get('method', '')} | Round 23 clinical-v5 targeted trace: {start}-{end}"
        row = coverage_by_path.get(path)
        if row is None:
            row = {
                "path": path, "status": status, "prior_status": old,
                "read_level_this_round": "full_file_read" if path.endswith("/khung.py") else "targeted_semantic_trace",
                "full_file_read_this_round": path.endswith("/khung.py"),
                "ranges": [], "sha256": digest, "line_count": len(lines),
            }
            coverage["files"].append(row)
            coverage_by_path[path] = row
        row["status"] = status
        row["ranges"].append({"start": start, "end": end, "purpose": purpose})

    coverage["scope"].append("separate versioned phiếu-khám v5 validator and its API/UI/test path; no new finding")
    coverage["coverage_note"] += (
        " Independent v5 trace found schema-key validation and a test that rejects unknown keys; CLIN-041 is scoped to the generic Form Engine, "
        "not v5. These tests were inspected but not run."
    )
    write_json("MAIN-PHAM-VI.json", manifest)
    write_json("blocks/round23_clinical_coverage.json", coverage)
    write_json("blocks/round23_clinical_v5_boundary.json", {
        "snapshot_sha": PINNED_SHA,
        "result": "No new finding in the versioned phiếu-khám v5 path: PhieuKhamService validates data against the pinned frame before save; existing test rejects unknown keys.",
        "tests": "test_phieu_kham_db.py and test_phieu_kham_v2_db.py inspected; not run.",
        "limitations": "Static source trace only; not an exhaustive review of all form callers or tests.",
        "ranges": [{"path": path, "start": start, "end": end, "purpose": purpose, "sha256": prior.source(path)[1]} for path, start, end, purpose in v5_ranges],
    })

    state = read_json("STATE.json")
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    state["updated_at"] = now
    state["phase"] = "round23_clinical_generic_engine_vs_v5_boundary_checkpoint"
    state["report_version"] = "v0.46"
    state["report_round_summary"] = (
        "Round 22 thêm SEC-030 và mở rộng SEC-011; event/provider không thêm finding. Round 23 đọc ba service dược/billing, khung phiếu khám và trace Form Engine: "
        "CLIN-041 chỉ áp cho generic Form Engine; riêng phiếu khám v5 kiểm key theo khung đã ghim và test khóa lạ hiện có, không thêm lỗi v5. "
        "Hai observation dược và required-field policy vẫn phụ thuộc ngưỡng/chính sách. Không chạy ClinicAI app/DB/API/provider/production test; chỉ QA report."
    )
    state["next_action"] = (
        "Continue exact-main semantic review of remaining patient/API callers, generic form callers and other scanned/inventoried source. "
        "Add synthetic no-write tests for CLIN-041 and disposable Supabase role tests for SEC-011/SEC-029/SEC-030. "
        "Resolve clinical requiredness, Bio mapping, payment clinic-wide read and list-cap policies with owners. Full source audit remains incomplete."
    )
    state["report_status"] = "v0.46_pending_report_QA; full source audit incomplete"
    state["summary"]["main_coverage"] = {key: counts.get(key, 0) for key in ("inventoried", "read", "traced", "scanned", "excluded")}
    state["summary"]["main_read_files"] = counts["read"]
    state["summary"]["main_partial_traces"] = counts["traced"]
    state["summary"]["code_like_source_files"]["coverage"] = {key: code_counts.get(key, 0) for key in ("inventoried", "traced", "scanned", "read")}
    state["summary"]["reviewed_slice_v046"] = "Round 23 boundary refinement: generic FormEngine candidate CLIN-041 retained; versioned phiếu-khám v5 path separately traced and no finding promoted."
    state.setdefault("blocks", {})["round23_clinical_v5_boundary"] = {
        "status": "separate v5 validation path traced; existing unknown-key test found; no new v5 finding",
        "scope": "Phiếu khám v5 typed frame, save API, BFF/UI writer, schema validator and related tests",
        "artifacts": "blocks/round23_clinical_v5_boundary.json; ranges merged into blocks/round23_clinical_coverage.json",
        "findings": "No new finding in v5. CLIN-041 is limited to generic FormEngineService.",
        "next": "Keep generic and v5 form contracts separate; run the existing negative-key test and add generic-engine tests only on isolated fixtures.",
    }
    state["artifacts"]["qa"] = "Pending v0.46 structural/evidence, browser and audit-only package QA; application behavior not validated in rounds 22–23."
    state["artifacts"]["bundle_integrity"] = "Pending v0.46 audit-only package rebuild and verification."
    state["artifacts"]["html_sha256"] = "pending v0.46 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.46 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.46 package verification"
    write_json("STATE.json", state)
    print(json.dumps({"report_version": "v0.46", "added_findings": [], "clarified_scope": "CLIN-041 generic only; v5 no new finding", "v5_paths": len(v5_ranges), "coverage": dict(counts), "code_like_coverage": dict(code_counts), "updated_at": now}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
