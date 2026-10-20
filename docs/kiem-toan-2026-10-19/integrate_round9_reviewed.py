"""Integrate reviewed round-9/round-10 candidates into the pinned-main audit ledger.

Only candidates in the explicit promotion map are promoted. Every other
candidate remains in its block file with a written triage disposition.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SNAPSHOT = Path("/tmp/clinicai-audit-main-956ba4f2")
SNAPSHOT_SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"

# canonical ID: (candidate file, candidate ID, severity override, evidence level)
PROMOTE = {
    "API-001": ("round9_api_clinical", "API-001", "MEDIUM", "confirmed_static"),
    "API-002": ("round9_api_clinical", "API-002", "MEDIUM", "confirmed_static"),
    "API-003": ("round9_api_clinical", "API-003", "MEDIUM", "confirmed_static"),
    "FE-012": (
        "round9_dashboard_schedule_patient",
        "CAND-R9-DASH-SCHED-01",
        "MEDIUM",
        "confirmed_static",
    ),
    "FE-013": (
        "round9_dashboard_schedule_patient",
        "CAND-R9-DASH-SCHED-02",
        "LOW",
        "confirmed_static",
    ),
    "FE-014": (
        "round9_dashboard_schedule_patient",
        "CAND-R9-DASH-SCHED-03",
        "MEDIUM",
        "confirmed_static",
    ),
    "FE-015": (
        "round9_dashboard_schedule_patient",
        "CAND-R9-DASH-SCHED-04",
        "MEDIUM",
        "confirmed_static",
    ),
    "DB-006": (
        "round9_migrations_202610",
        "DB-006",
        "MEDIUM",
        "confirmed_static",
    ),
    "DB-007": (
        "round9_migrations_202610",
        "DB-007",
        "LOW",
        "design_gap",
    ),
    "FIN-010": ("round9_migrations_202609", "FIN-010", "MEDIUM", "confirmed_static"),
    "SEC-019": (
        "round9_migrations_202610",
        "SEC-019",
        "HIGH",
        "confirmed_static",
    ),
    "INF-018": (
        "round9_worker_event",
        "CAND-WRK-001",
        "MEDIUM",
        "confirmed_static",
    ),
    "INF-019": ("round10_ops_recovery", "CAND-OPS-001", "HIGH", "confirmed_static"),
    "CI-001": ("round10_ci_quality", "CAND-CI-001", "MEDIUM", "confirmed_static"),
    "FE-016": ("round11_dashboard_forms", "CAND-R11-DASH-FORM-01", "MEDIUM", "confirmed_static"),
    "FE-017": ("round11_dashboard_forms", "CAND-R11-DASH-FORM-02", "MEDIUM", "confirmed_static"),
    "FIN-011": ("round11_finance_close", "CAND-R11-FIN-01", "MEDIUM", "confirmed_static"),
    "FIN-012": ("round11_finance_close", "CAND-R11-FIN-02", "LOW", "confirmed_static"),
    "SEC-020": ("round11_clinical_records", "CAND-CLIN-REC-001", "HIGH", "confirmed_static"),
    "PHAR-002": ("round12_pharmacy_controls", "CAND-PHAR-STOCK-001", "LOW", "confirmed_static"),
    "CLIN-035": (
        "round13_booking_lifecycle",
        "CAND-BOOK-LIFE-001",
        "MEDIUM",
        "confirmed_static",
    ),
    "SEC-021": (
        "round13_api_logging",
        "CAND-LOG-PII-001",
        "LOW",
        "confirmed_static",
    ),
    "SEC-022": (
        "round13_patient_lookup",
        "CAND-PAT-LOOKUP-001",
        "MEDIUM",
        "confirmed_static",
    ),
    "SEC-023": (
        "round13_patient_lookup",
        "CAND-PAT-LOOKUP-002",
        "MEDIUM",
        "confirmed_static",
    ),
    "FIN-013": (
        "round13_receivables",
        "CAND-R13-AR-01",
        "MEDIUM",
        "confirmed_static",
    ),
    "FIN-014": (
        "round13_receivables",
        "CAND-R13-AR-02",
        "MEDIUM",
        "design_gap",
    ),
    "FIN-015": (
        "round14_payment_settlement",
        "CAND-R14-PAY-IDEM-001",
        "LOW",
        "confirmed_static",
    ),
    "SEC-024": (
        "round14_observability",
        "CAND-OBS-RAW-ERROR-001",
        "LOW",
        "confirmed_static",
    ),
    "API-004": (
        "round14_work_items",
        "CAND-R14-WI-SCOPE-001",
        "MEDIUM",
        "confirmed_static",
    ),
}

FINDING_OVERRIDES = {
    "INF-019": {
        "title": "Tín hiệu backup có thể xanh dù bản sao ngoài VPS chưa được xác nhận",
        "summary": (
            "Backup cục bộ được xác minh và gửi heartbeat thành công trước khi systemd chạy uploader Viettel CFS. "
            "Lỗi uploader bị bỏ qua ở cấp unit; cờ offsite hiện có chỉ phản ánh R2, còn trạng thái Ops tổng thể "
            "không dùng kết quả CFS. Vì vậy monitor có thể tiếp tục xanh khi lần sao lưu ngoài VPS thất bại. "
            "Đây là lỗi đường điều khiển tĩnh, không chứng minh CFS đang lỗi hay đã mất dữ liệu."
        ),
        "category": "backup_offsite_monitoring",
        "related_findings": ["INF-001", "INF-006"],
        "validation": {
            "method": "Static control-flow trace across backup, systemd, CFS uploader, monitoring and Ops projection.",
            "result": "The success heartbeat precedes the CFS uploader and the unit ignores uploader failure; no live failure was tested.",
            "limitations": "No systemd/runtime state, real CFS mount, monitoring configuration, backup payload or production data was accessed.",
        },
    },
    "CI-001": {
        "title": "Thu hồi khóa CI cũ không nguyên tử, có thể cho phép hai lượt CI chạy đồng thời",
        "summary": (
            "Khi tạo thư mục khóa thất bại và PID ghi trong đó đã chết, script chỉ thông báo khóa cũ rồi tiếp tục. "
            "Nó ghi PID mới vào cùng thư mục mà không giành quyền sở hữu khóa nguyên tử. Hai tiến trình cùng đi "
            "qua nhánh này có thể cùng chạy và dùng chung log, mã kết quả, cổng/container kiểm thử; kết quả CI "
            "và khả năng chẩn đoán có thể bị nhiễu. Chưa mô phỏng race lúc chạy."
        ),
        "category": "ci_lock_lifecycle",
        "impact": (
            "Concurrent runs can interleave shared CI logs and result files and contend for test ports or containers. "
            "This can make the release-gate result or diagnosis unreliable; no false-green outcome was demonstrated."
        ),
    },
    "CLIN-035": {
        "validation": {
            "method": "static_service_route_ui_and_test_trace_pinned_main",
            "result": "Service transition chỉ gate theo trạng thái; UI cho phép bấm no-show với lịch tương lai trong ngày và API chuyển action xuống service. Không chạy runtime.",
            "limitations": "Chưa gọi API/DB hoặc UI runtime. Chính sách grace period chưa được xác định trong code nên không giả định ngưỡng cụ thể.",
        }
    },
    "SEC-021": {
        "validation": {
            "method": "static_exception_to_structured_logger_trace",
            "result": "Lookup miss đưa UUID vào exception message, handler chép message vào field reason, sanitizer không xóa UUID khỏi free text. Không xác nhận production logging/retention.",
            "limitations": "Không đọc production logs, cấu hình sink hoặc retention; chỉ truy vết mã nguồn tĩnh và không thấy bệnh án đi cùng đường này.",
        }
    },
    "SEC-022": {
        "summary": "Hai endpoint danh sách bệnh nhân và khách CSKH chọn CCCD/email nguyên văn rồi serialize vào response; patient-list đưa nguyên hồ sơ sang client dù màn hình đã rà không hiển thị hai trường này. Các truy vấn được kiểm tra có lọc clinic_id.",
        "category": "patient_list_pii_overfetch",
        "validation": {
            "method": "static_service_route_response_and_ui_trace_pinned_main",
            "result": "Theo dấu projection service, guard và response API, props client cùng trường được render. Hai field CCCD/email có trong payload nhưng không được dùng ở patient-list UI đã rà.",
            "limitations": "Không gọi API/runtime hoặc xem network payload production. Chỉ rà hai luồng danh sách được nêu; không kết luận cross-clinic, xuất toàn bộ phòng khám hoặc truy cập thực tế.",
        }
    },
    "API-004": {
        "related_findings": [
            {"id": "API-001", "relationship": "Cùng chủ đề thiếu scope location ở API mutation; API-001 là sắp hàng đợi, API-004 là trạng thái work item."},
            {"id": "API-002", "relationship": "API-002 là đường đọc workflow của lượt ở cơ sở khác; API-004 là command ghi trạng thái work item."},
            {"id": "CLIN-004", "relationship": "CLIN-004 bàn ownership/hand-off; API-004 là ranh giới cơ sở ở các command start/complete/skip/cancel."},
        ]
    },
    "SEC-023": {
        "summary": "Preset CASHIER, CASHIER_DV và CASHIER_THUOC được cấp crm.manage, capability mà API CSKH dùng để ghi tương tác/follow-up/feedback; UI mô tả thu ngân chỉ đọc nhưng dùng cùng capability để mount vùng ghi.",
        "category": "cashier_cskh_write_capability",
        "validation": {
            "method": "static_permission_preset_guard_and_ui_trace_pinned_main",
            "result": "Migration cấp capability cho preset, backend guard các endpoint ghi bằng crm.manage, và UI dùng capability đó để bật khu vực thao tác. Không xác minh grant/tài khoản hiện tại.",
            "limitations": "Không kiểm tra production grants hay account cụ thể, không gọi API/runtime. Kết luận về preset mặc định; quyền thành viên có thể đã được thay đổi.",
        },
        "related_findings": [
            {
                "id": "SEC-020",
                "relationship": (
                    "Cùng capability crm.manage; SEC-020 là đường đọc chart lâm sàng, "
                    "SEC-023 là quyền ghi tương tác CSKH từ preset CASHIER*."
                ),
            }
        ]
    },
}

# Current debt writers select the patient from the clinic-scoped visit. Keep
# that limiting fact in the evidence record when documenting the DB invariant.
EXTRA_PROOFS = {
    "DB-007": [
        ("src/clinicai/services/cong_no_service.py", 401, 418),
        ("src/clinicai/services/cong_no_service.py", 452, 469),
        ("src/clinicai/services/so_no_service.py", 94, 100),
        ("src/clinicai/services/so_no_service.py", 217, 227),
        ("src/clinicai/services/so_no_service.py", 270, 280),
    ]
}


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proof(path: str, start: int, end: int) -> dict:
    source = SNAPSHOT / path
    raw = source.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    if start < 1 or end < start or end > len(lines):
        raise ValueError(f"invalid evidence range: {path}:{start}-{end}")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "excerpt": "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1)),
    }


def find_candidate(block: str, candidate_id: str) -> dict:
    candidates = read_json(f"blocks/{block}.findings.json")
    if isinstance(candidates, dict):
        candidates = candidates.get("findings", [])
    if not isinstance(candidates, list):
        raise ValueError(f"candidate file must contain a list: {block}")
    hits = [item for item in candidates if item.get("id") == candidate_id]
    if len(hits) != 1:
        raise ValueError(
            f"expected one candidate {block}:{candidate_id}; found {len(hits)}"
        )
    return hits[0]


def normalize_candidate(
    canonical_id: str,
    block: str,
    candidate_id: str,
    severity: str,
    evidence_level: str,
) -> dict:
    import re

    item = copy.deepcopy(find_candidate(block, candidate_id))
    item["id"] = canonical_id
    item.pop("canonical_id", None)
    item.pop("confidence", None)
    item.pop("status", None)
    item["severity"] = severity
    item["evidence_level"] = evidence_level
    item["status"] = "open"
    item["reference_version"] = "pinned_main"
    item.setdefault("source_hashes", {})
    item.update(copy.deepcopy(FINDING_OVERRIDES.get(canonical_id, {})))
    if "related_existing_findings" in item:
        item.setdefault("related_findings", item.pop("related_existing_findings"))

    for path, expected in item["source_hashes"].items():
        source = SNAPSHOT / path
        if not source.is_file() or sha256(source) != expected:
            raise ValueError(f"source hash mismatch: {canonical_id} {path}")

    spans: list[tuple[str, int, int]] = []
    normalized_evidence: list[dict] = []
    for row in item.get("evidence", []):
        path = row["path"]
        if row.get("line") is not None:
            start = int(row["line"])
            end = int(row.get("end_line", start))
            ranges = [(start, end)]
        else:
            raw_ranges = str(row.get("lines", ""))
            ranges = []
            for part in raw_ranges.split(","):
                match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", part)
                if not match:
                    raise ValueError(
                        f"invalid evidence range: {canonical_id} {path}:{raw_ranges}"
                    )
                start = int(match.group(1))
                end = int(match.group(2) or match.group(1))
                ranges.append((start, end))
        actual_hash = sha256(SNAPSHOT / path)
        expected_hash = row.get("sha256")
        if expected_hash is not None and expected_hash != actual_hash:
            raise ValueError(f"evidence hash mismatch: {canonical_id} {path}")
        for start, end in ranges:
            spans.append((path, start, end))
            normalized_evidence.append(
                {
                    "path": path,
                    "line": start,
                    "end_line": end,
                    "sha256": actual_hash,
                    **({"detail": row["detail"]} if row.get("detail") else {}),
                }
            )

    for path, start, end in EXTRA_PROOFS.get(canonical_id, []):
        expected = sha256(SNAPSHOT / path)
        prior = item["source_hashes"].get(path)
        if prior is not None and prior != expected:
            raise ValueError(f"extra proof hash mismatch: {canonical_id} {path}")
        item["source_hashes"][path] = expected
        spans.append((path, start, end))

    proofs = [proof(*span) for span in spans]
    if not proofs:
        raise ValueError(f"candidate has no source evidence: {canonical_id}")
    for row in proofs:
        prior = item["source_hashes"].get(row["path"])
        if prior is not None and prior != row["sha256"]:
            raise ValueError(
                f"proof not covered by candidate hashes: {canonical_id} {row['path']}"
            )
        item["source_hashes"][row["path"]] = row["sha256"]

    item["evidence"] = normalized_evidence
    item["main_validation"] = {
        "sha": SNAPSHOT_SHA,
        "status": "still_present_on_main",
        "note": "Static source review on the pinned main snapshot; no production or patient data was accessed.",
        "evidence": sorted(proofs, key=lambda row: (row["path"], row["line"])),
        "production_verified": False,
    }
    return item


def integrate_findings() -> list[dict]:
    canonical = read_json("PHAT-HIEN.json")
    by_id = {item["id"]: item for item in canonical}
    inserted: list[dict] = []
    for canonical_id, spec in PROMOTE.items():
        item = normalize_candidate(canonical_id, *spec)
        existing = by_id.get(canonical_id)
        if existing:
            same = (
                existing.get("title") == item.get("title")
                and existing.get("source_hashes") == item.get("source_hashes")
                and existing.get("reference_version") == "pinned_main"
            )
            if same:
                for field in (
                    "summary", "category", "impact", "validation",
                    "related_findings", "evidence",
                ):
                    if field in item:
                        existing[field] = item[field]
                continue
            raise ValueError(f"canonical ID collision: {canonical_id}")
        canonical.append(item)
        by_id[canonical_id] = item
        inserted.append(item)
    write_json("PHAT-HIEN.json", canonical)
    return inserted


def merge_coverage() -> None:
    manifest = read_json("MAIN-PHAM-VI.json")
    by_path = {item["path"]: item for item in manifest["files"]}
    rank = {"excluded": -1, "inventoried": 0, "scanned": 1, "traced": 2, "read": 3}
    read_levels = {"full_semantic_read", "full_file_static_read", "read", "traced_full", "full"}
    traced_levels = {
        "partial",
        "partial_deep_review",
        "partial_semantic_read",
        "targeted",
        "targeted_semantic_read",
        "targeted_test_review",
        "read_only_source_review",
        "targeted_static_trace",
        "targeted_static_read",
        "traced",
        "guard_and_scope_scan",
    }
    scanned_levels = {"scanned", "static_scan"}
    inventoried_levels = {"inventoried", "caller_inventory", "inventory"}
    excluded_levels = {"excluded"}

    paths = sorted((ROOT / "blocks").glob("round9_*.coverage.json"))
    paths += sorted((ROOT / "blocks").glob("round10_*.coverage.json"))
    paths += sorted((ROOT / "blocks").glob("round11_*.coverage.json"))
    paths += sorted((ROOT / "blocks").glob("round12_*.coverage.json"))
    paths += sorted((ROOT / "blocks").glob("round13_*.coverage.json"))
    paths += sorted((ROOT / "blocks").glob("round14_*.coverage.json"))
    for path in paths:
        coverage = json.loads(path.read_text())
        source = coverage.get("source", {})
        snapshot_meta = coverage.get("snapshot", {})
        source_ref = source.get("repository_sha") if isinstance(source, dict) else None
        snapshot_ref = (
            snapshot_meta.get("repository_sha") or snapshot_meta.get("sha")
            if isinstance(snapshot_meta, dict)
            else None
        )
        reference = (
            coverage.get("snapshot_sha")
            or coverage.get("pinned_reference_sha")
            or coverage.get("sha")
            or source_ref
            or snapshot_ref
        )
        if reference != SNAPSHOT_SHA:
            raise ValueError(f"wrong snapshot in {path.name}")

        round_label = path.name.split("_", 1)[0].replace("round", "Round ")
        rows = list(coverage.get("files", []))
        nested_coverage = coverage.get("coverage")
        if not rows and isinstance(nested_coverage, dict):
            rows = [
                {**row, "status": row.get("coverage_status", "targeted")}
                for row in (
                    nested_coverage.get("reviewed_migration_files", [])
                    + nested_coverage.get("reviewed_sql_test_files", [])
                )
            ]
        normalized_rows = []
        for row in rows:
            row = dict(row)
            raw_status = (
                row.get("status")
                or row.get("read_level")
                or row.get("review_status")
                or row.get("coverage_status")
                or row.get("coverage")
                or row.get("depth")
                or "unclassified"
            )
            notes = str(
                row.get("reviewed_ranges_or_notes")
                or row.get("notes")
                or ""
            ).lower()
            if "function names inventoried" in notes or "content not reviewed" in notes:
                raw_status = "inventoried"
            row["_normalized_status"] = raw_status
            normalized_rows.append(row)
        for row in normalized_rows:
            target = by_path.get(row["path"])
            if target is None:
                continue
            if target.get("sha256") != row.get("sha256"):
                raise ValueError(f"coverage hash mismatch: {row['path']}")

            raw_status = row.get("_normalized_status", "unclassified")
            if raw_status in read_levels:
                status = "read"
            elif raw_status in traced_levels:
                status = "traced"
            elif raw_status in scanned_levels:
                status = "scanned"
            elif raw_status in inventoried_levels:
                status = "inventoried"
            elif raw_status in excluded_levels:
                status = "excluded"
            elif raw_status == "excluded_previously_reviewed":
                status = target.get("status", "inventoried")
            else:
                status = "inventoried"

            if target.get("status") != "excluded" and rank[status] > rank.get(target.get("status"), 0):
                target["status"] = status
            method = f"{round_label}: {raw_status}; see {path.name}."
            if method not in target.get("method", ""):
                target["method"] = (
                    target.get("method", "").rstrip(" |") + " | " + method
                ).strip(" |")
    write_json("MAIN-PHAM-VI.json", manifest)


def update_checks(inserted: list[dict]) -> None:
    checks = read_json("KIEM-CHUNG.json")
    present = {(row.get("id"), row.get("path")) for row in checks["checks"]}
    for item in inserted:
        for path in item["source_hashes"]:
            key = (item["id"], path)
            if key not in present:
                checks["checks"].append({"id": item["id"], "path": path, "valid": True})
                present.add(key)
    write_json("KIEM-CHUNG.json", checks)


def update_handoffs(count: int, inserted_ids: list[str]) -> None:
    state = read_json("STATE.json")
    manifest = read_json("MAIN-PHAM-VI.json")
    findings = read_json("PHAT-HIEN.json")
    coverage = Counter(item["status"] for item in manifest["files"])
    suffixes = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html"}
    code = [item for item in manifest["files"] if Path(item["path"]).suffix.lower() in suffixes]
    code_coverage = Counter(item["status"] for item in code)
    severity = Counter(item["severity"] for item in findings)
    evidence_levels = Counter(item["evidence_level"] for item in findings)
    main_status = Counter(item["main_validation"]["status"] for item in findings)
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    state.update(
        updated_at=now,
        status="in_progress",
        phase="round9_candidate_triage_and_cross_layer_review",
        next_action="Rà source slices chưa phủ, mở rộng exact-main review theo authorization, mutation và lifecycle; full source audit remains incomplete.",
        report_status=f"v0.29_{len(findings)}_findings_report_QA_pending; full source audit incomplete",
    )
    state["summary"].update(
        findings=len(findings),
        severity=dict(severity),
        evidence_levels=dict(evidence_levels),
        main_status=dict(main_status),
        main_files=len(manifest["files"]),
        main_partial_traces=coverage["traced"],
        main_coverage=dict(coverage),
        main_read_files=coverage["read"],
        new_findings_v029=list(PROMOTE),
        code_like_source_files={
            "definition": state["summary"]["code_like_source_files"]["definition"],
            "total": len(code),
            "coverage": dict(code_coverage),
            "traced_is_partial": True,
        },
    )
    state["limits"][0] = (
        f"Full source audit incomplete: {coverage['inventoried']} inventoried, {coverage['traced']} partial traces, "
        f"{coverage['scanned']} scanned, {coverage['excluded']} excluded; traced is not full-file semantic review."
    )
    state["artifacts"]["integration_script"] = "integrate_round9_reviewed.py"
    state["artifacts"]["qa"] = "HTML-QA.json; pending v0.29 structural/evidence/browser QA and ZIP regeneration"
    state["artifacts"]["bundle_integrity"] = "Pending regeneration after round-9 triage is integrated."
    for key in ("html_sha256", "html_checked_at", "bundle_verified_at", "bundle_entries", "bundle_outer_sha256"):
        state["artifacts"].pop(key, None)
    state["blocks"]["api_round9"] = {
        "status": "round9_clinical_api_slice_complete; broader API audit open",
        "findings": "API-001..API-003",
        "coverage": "blocks/round9_api_clinical.coverage.json",
        "next": "Expand permission/location matrices and test identified route boundaries on disposable data; continue unreviewed API modules.",
    }
    state["blocks"]["dashboard_round9"] = {
        "status": "round9_schedule_patient_slice_complete; broader dashboard audit open",
        "findings": "FE-012..FE-015",
        "coverage": "blocks/round9_dashboard_schedule_patient.coverage.json",
        "next": "Add focused component/route tests for stale async state and destructive roster preview; continue other dashboard flows.",
    }
    state["blocks"]["migrations_round9"] = {
        "status": "round9_migrations_july_october_triaged; remaining migration/source audit open",
        "findings": "DB-006..DB-007, FIN-010, SEC-019; resolved and held candidates are in blocks/round9-triage.md",
        "coverage": "blocks/round9_migrations_20260708.coverage.json; blocks/round9_migrations_202609.coverage.json; blocks/round9_migrations_202610.coverage.json",
        "next": "Test SECURITY DEFINER ACL and note/history role policies on a fresh exact-main DB; inspect remaining migration dates and data invariants.",
    }
    state["blocks"]["worker_round9"] = {
        "status": "round9_worker_event_static_slice_complete; runtime crash-loop verification open",
        "findings": "INF-018",
        "coverage": "blocks/round9_worker_event.coverage.json",
        "next": "Add disposable DB tests for repeated crash/lease reclaim beyond the retry cap; continue the wider source audit.",
    }
    note = (
        f"Checkpoint v0.31 trên main ghim {SNAPSHOT_SHA}: đã triage worker/event, API lâm sàng, dashboard lịch/bệnh nhân và migration tháng 7–10. "
        "Đã tích hợp API-001..003, FE-012..015, DB-006..007, FIN-010, SEC-019 và INF-018; tổng 115 hồ sơ. "
        "INF-018 ghi nhận nhánh thu hồi lease không áp retry cap khi worker chết sau claim; đây là static control-flow finding, chưa mô phỏng crash. "
        "SEC-019 là finding HIGH ở ranh giới đọc lịch sử biểu mẫu/ghi chú lâm sàng; hai candidate ACL về phiếu kho và RPC điều phối đã được đối chiếu migration 19/10 và không còn mở. "
        "Audit toàn source vẫn chưa xong; xem blocks/round9-triage.md, blocks/round9_worker_event.md và STATE.json."
    )
    for key in ("TIEP-TUC.md", "BAT-DAU-TU-DAY.md"):
        path = ROOT / key
        text = path.read_text()
        if key == "TIEP-TUC.md":
            text = text.replace("# CURRENT HANDOFF — v0.28 (19/10/2026)", "# CURRENT HANDOFF — v0.29 (19/10/2026)", 1)
            text = text.replace("## v0.28 mới tích hợp", "## v0.29 mới tích hợp", 1)
            import re
            text = re.sub(r"(?m)^Trạng thái canonical ở `STATE.json`:.*?\n\n(?=## )", note + "\n\n", text, count=1, flags=re.S)
            text = re.sub(r"(?m)^## v0\.29 mới tích hợp\n.*?(?=^## |\Z)", "## v0.29 mới tích hợp\n\n" + note + " Đọc `blocks/round9-triage.md`, `STATE.json` và `blocks/round9_worker_event.md`; tiếp tục các phần source chưa được đọc trọn. Không tuyên bố audit toàn code hoàn tất.\n\n", text, count=1, flags=re.S)
        else:
            text = text.replace("checkpoint v0.28", "checkpoint v0.29", 1)
            text = text.replace("## Checkpoint v0.28 — tiếp quản audit", "## Checkpoint v0.29 — tiếp quản audit", 1)
            import re
            text = re.sub(r"(?m)^Audit toàn code chưa xong\..*?(?=^## )", note + "\n\n", text, count=1, flags=re.S)
            text = re.sub(r"(?m)^## Checkpoint v0\.29 — tiếp quản audit\n.*?(?=^## |\Z)", "## Checkpoint v0.29 — tiếp quản audit\n\n" + note + " Đọc `blocks/round9-triage.md`, `STATE.json` và `blocks/round9_worker_event.md`; tiếp tục các phần source chưa được đọc trọn. Không tuyên bố audit toàn code hoàn tất.\n\n", text, count=1, flags=re.S)
        path.write_text(text)
    write_json("STATE.json", state)


def update_template() -> None:
    path = ROOT / "report.template.html"
    text = path.read_text()
    text = text.replace("Bản 0.28", "Bản 0.29").replace("v0.28", "v0.29")
    import re
    text = re.sub(
        r"(?m)^<p>Checkpoint v0\.29.*?</p>",
        "<p>Checkpoint v0.29 tích hợp lát worker/event cùng các lát API lâm sàng, dashboard lịch/bệnh nhân và migration tháng 7–10 trên main ghim. Có thêm INF-018: nhánh thu hồi lease không áp retry cap khi worker chết sau claim; tổng sổ là 115 hồ sơ. Các phát hiện mới là static review, chưa kiểm production. Toàn bộ cây đã được kiểm kê, nhưng chỉ một phần code được đọc trọn hoặc truy vết sâu. Full source audit chưa xong.</p>",
        text,
        count=1,
        flags=re.S,
    )
    text = text.replace("BẢN 0.28 — CHƯA PHẢI", "BẢN 0.29 — CHƯA PHẢI")
    path.write_text(text)


def finalize_round14_handoff() -> None:
    import html
    import re

    state = read_json("STATE.json")
    manifest = read_json("MAIN-PHAM-VI.json")
    findings = read_json("PHAT-HIEN.json")
    coverage = Counter(item["status"] for item in manifest["files"])
    suffixes = {
        ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html",
    }
    code = [
        item for item in manifest["files"]
        if Path(item["path"]).suffix.lower() in suffixes
    ]
    code_coverage = Counter(item["status"] for item in code)
    severity = Counter(item["severity"] for item in findings)
    evidence_levels = Counter(item["evidence_level"] for item in findings)
    main_status = Counter(item["main_validation"]["status"] for item in findings)
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    round13_ids = [
        "CLIN-035", "SEC-021", "SEC-022", "SEC-023", "FIN-013", "FIN-014"
    ]
    round14_ids = ["API-004", "FIN-015", "SEC-024"]

    note = (
        f"Checkpoint v0.35 trên main ghim {SNAPSHOT_SHA}: {len(findings)} hồ sơ "
        f"({severity['HIGH']} HIGH, {severity['MEDIUM']} MEDIUM, {severity['LOW']} LOW); "
        f"{main_status['still_present_on_main']} còn hiện diện, "
        f"{main_status['partially_addressed_on_main']} xử lý một phần, "
        f"{main_status['addressed_on_main']} đã có bản sửa trong phạm vi đối chiếu. "
        f"Coverage {len(manifest['files']):,} path: {coverage['read']} read, "
        f"{coverage['traced']} traced một phần, {coverage['scanned']} scanned, "
        f"{coverage['inventoried']} inventoried, {coverage['excluded']} excluded. "
        "Round 13 thêm CLIN-035, SEC-021..SEC-023 và FIN-013..FIN-014. Round 14 thêm "
        "API-004 (command work item thiếu location gate), FIN-015 (receipt idempotency "
        "bỏ lựa chọn công ty nhưng replay vẫn gắn snapshot) và SEC-024 (error detail "
        "có thể đi qua telemetry vận hành chưa scrub). Lát tiện ích lõi đã đọc thêm "
        "13 file và không có finding mới. Các kết quả là audit tĩnh; "
        "không xác minh lỗi production. Full source audit chưa xong."
    )
    state.update(
        updated_at=now,
        status="in_progress",
        phase="round14_core_primitives_checkpoint",
        next_action=(
            "Tiếp tục đọc các vùng source chưa được semantic-read, ưu tiên API/business "
            "rules, clinical lifecycle, data access, finance, events/recovery và UI "
            "caller. Xác minh các candidate bằng test trên dữ liệu giả khi môi trường "
            "phù hợp; full source audit remains incomplete."
        ),
        report_status=(
            f"v0.35_{len(findings)}_findings_HTML_and_ZIP_QA_pending; "
            "full source audit incomplete"
        ),
    )
    state["summary"].update(
        findings=len(findings),
        severity=dict(severity),
        evidence_levels=dict(evidence_levels),
        main_status=dict(main_status),
        main_files=len(manifest["files"]),
        main_partial_traces=coverage["traced"],
        main_coverage=dict(coverage),
        main_read_files=coverage["read"],
        new_findings_v033=round13_ids,
        new_findings_v034=round14_ids,
        reviewed_slice_v035="round14_core_primitives; 13 files read/targeted, no new finding",
        new_findings_v029=[
            "API-001", "API-002", "API-003",
            "FE-012", "FE-013", "FE-014", "FE-015",
            "DB-006", "DB-007", "FIN-010", "SEC-019",
            "INF-018", "INF-019", "CI-001", "FE-016", "FE-017",
            "FIN-011", "FIN-012", "SEC-020", "PHAR-002",
        ],
        new_findings_v032=["PHAR-002"],
        code_like_source_files={
            "definition": state["summary"]["code_like_source_files"]["definition"],
            "total": len(code),
            "coverage": dict(code_coverage),
            "traced_is_partial": True,
        },
    )
    state["limits"][0] = (
        f"Full source audit incomplete: {coverage['inventoried']} inventoried, "
        f"{coverage['traced']} partial traces, {coverage['scanned']} scanned, "
        f"{coverage['excluded']} excluded; traced is not full-file semantic review."
    )

    state["blocks"]["round14_work_items"] = {
        "status": "round14 work-item location authorization slice triaged; API-004 added",
        "scope": "Command, worklist, blocker/read endpoints, BFF and direct tests",
        "artifacts": "blocks/round14_work_items.md; blocks/round14_work_items.findings.json; blocks/round14_work_items.coverage.json",
        "findings": "API-004 MEDIUM confirmed static; same-clinic cross-location command scope not runtime-tested",
        "next": "Add synthetic same-clinic/two-location command tests; preserve explicit policy for locationless OPS work.",
    }
    state["blocks"]["round14_payment_settlement"] = {
        "status": "round14 payment/idempotency slice triaged; FIN-015 added",
        "scope": "Service/medicine collection, receipt hash, company snapshot, refund and export callers",
        "artifacts": "blocks/round14_payment_settlement.md; blocks/round14_payment_settlement.findings.json; blocks/round14_payment_settlement.coverage.json",
        "findings": "FIN-015 LOW confirmed static boundary mismatch; effect inferred, no duplicate collection shown",
        "next": "Test same-key company mismatch before any snapshot side effect; include company choice in fingerprint or split command.",
    }
    state["blocks"]["round14_rls_grants"] = {
        "status": "round14 tenant/RLS/ACL slice complete; no distinct candidate",
        "scope": "Selected tenant policies, function ACLs, permission views and final stock grants",
        "artifacts": "blocks/round14_rls_grants.md; blocks/round14_rls_grants.findings.json; blocks/round14_rls_grants.coverage.json",
        "findings": "No new finding; duplicate view issue maps to SEC-017; stock grant issue absent after final migration in pinned source.",
        "next": "Verify actual grants/owners and two-clinic behavior on disposable exact-main DB; do not infer production ACL from source.",
    }
    state["blocks"]["round14_observability"] = {
        "status": "round14 in-process telemetry error-detail slice triaged; SEC-024 added",
        "scope": "Telemetry buffer, exception capture, ops endpoint, scrubber contrast and direct tests",
        "artifacts": "blocks/round14_observability.md; blocks/round14_observability.findings.json; blocks/round14_observability.coverage.json",
        "findings": "SEC-024 LOW confirmed static data-flow; no exception containing PII/PHI or production occurrence demonstrated.",
        "next": "Add synthetic sentinel tests for telemetry detail storage and /ops/telemetry response; keep raw exception text out of feed.",
    }
    state["blocks"]["round14_core_primitives"] = {
        "status": "round14 selected core-primitive slice complete; no new candidate",
        "scope": "Clock/date, clinic context, phone, location code, GS1, observability helpers and Sentry privacy bootstrap",
        "artifacts": "blocks/round14_core_primitives.md; blocks/round14_core_primitives.findings.json; blocks/round14_core_primitives.coverage.json",
        "findings": "No distinct issue observed in the selected pure helpers; Sentry remains wired behind SENTRY_DSN despite dead-service policy, classified as policy drift only",
        "next": "Read remaining core modules and phone/date callers; tests were inspected but not run. Verify Sentry is disabled or remove dead integration in a separate product change.",
    }

    state["artifacts"]["integration_script"] = "integrate_round9_reviewed.py"
    state["artifacts"]["qa"] = (
        "HTML-QA.json; pending v0.35 structural/evidence/browser QA and ZIP regeneration"
    )
    state["artifacts"]["bundle_integrity"] = (
        "Pending regeneration after v0.35 report QA and handoff updates."
    )
    for key in (
        "html_sha256", "html_checked_at", "bundle_verified_at",
        "bundle_entries", "bundle_outer_sha256",
    ):
        state["artifacts"].pop(key, None)

    path = ROOT / "TIEP-TUC.md"
    text = path.read_text()
    history_start = text.find("\n## v0.25 mới tích hợp")
    if history_start < 0:
        raise ValueError("cannot locate TIEP-TUC history")
    current = (
        f"# CURRENT HANDOFF — v0.35 (20/10/2026)\n\n{note} "
        "Đọc BAT-DAU-TU-DAY.md, STATE.json, MAIN-PHAM-VI.json, PHAT-HIEN.json, "
        "KIEM-CHUNG.json, TEST-RUNS.json, blocks/round13-triage.md, "
        "blocks/round14-triage.md và blocks/round14_core_primitives.md. "
        "Bằng chứng gắn với exact-main SHA đã ghim; nếu "
        "/tmp bị dọn, chạy python3 docs/kiem-toan-2026-10-19/recreate_snapshot.py "
        "từ repository có Git object đó. Không dùng working tree bẩn làm bằng chứng. "
        "HTML cần QA sau khi cập nhật; full source audit còn dang dở."
    )
    text = current + "\n\n## v0.35 mới tích hợp\n\n" + note + (
        " Các lát work-item, payment/idempotency và telemetry được triage riêng; "
        "RLS/grants và tiện ích lõi không có finding mới sau dedupe. Tiếp tục đọc source còn lại, "
        "không tuyên bố audit toàn code hoàn tất."
    ) + text[history_start:]
    path.write_text(text)

    path = ROOT / "BAT-DAU-TU-DAY.md"
    text = path.read_text()
    replacement = (
        f"# Trạng thái hiện hành — 20/10/2026, checkpoint v0.35\n\n{note}\n\n"
        "## Checkpoint v0.35 — tiếp quản audit\n\n"
        f"{note} Đọc STATE.json, MAIN-PHAM-VI.json, PHAT-HIEN.json, TIEP-TUC.md, "
        "KIEM-CHUNG.json, TEST-RUNS.json, blocks/round13-triage.md, "
        "blocks/round14-triage.md và blocks/round14_core_primitives.md. "
        "Bám exact-main SHA "
        f"{SNAPSHOT_SHA}; nếu snapshot tạm không còn, chạy "
        "python3 docs/kiem-toan-2026-10-19/recreate_snapshot.py từ repository "
        "có Git object này. Không dùng working tree hiện tại làm bằng chứng. "
        "HTML tự chứa là đầu ra cuối dự kiến; full source audit còn dang dở."
    )
    text, count = re.subn(
        r"(?s)\A# Trạng thái hiện hành.*?(?=^## Checkpoint v0\.25)",
        replacement + "\n\n",
        text,
        count=1,
        flags=re.M,
    )
    if count != 1:
        raise ValueError("cannot locate current BAT-DAU-TU-DAY checkpoint")
    path.write_text(text)

    path = ROOT / "report.template.html"
    text = path.read_text()
    text = text.replace("v0.34", "v0.35")
    text = text.replace("Bản 0.29", "Bản 0.35")
    text = text.replace("BẢN 0.33 —", "BẢN 0.35 —")
    checkpoint = (
        f"<p>{html.escape(note)} Round 14 artifacts preserve source hashes and "
        "limitations; findings remain static and production-unverified. "
        "Full source audit chưa xong.</p>"
    )
    text, count = re.subn(
        r"(?m)^<p>Checkpoint v0\.\d+.*?</p>",
        checkpoint,
        text,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("cannot locate current report template checkpoint")
    text = re.sub(
        r"trong \d+ hồ sơ ở mục Phát hiện",
        f"trong {len(findings)} hồ sơ ở mục Phát hiện",
        text,
        count=1,
    )
    path.write_text(text)
    write_json("STATE.json", state)

def main() -> None:
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"pinned snapshot missing: {SNAPSHOT}")
    inserted = integrate_findings()
    merge_coverage()
    update_checks(inserted)
    inserted_ids = [item["id"] for item in inserted]
    update_handoffs(len(inserted), inserted_ids)
    update_template()
    finalize_round14_handoff()
    coverage_inputs = len(
        list((ROOT / "blocks").glob("round[0-9]*_*.coverage.json"))
    )
    print(
        f"Integrated {len(inserted)} findings: "
        f"{', '.join(inserted_ids) or '(already integrated)'}"
    )
    print(f"Coverage inputs: {coverage_inputs} round-9/10/11/12/13/14 blocks")


if __name__ == "__main__":
    main()
