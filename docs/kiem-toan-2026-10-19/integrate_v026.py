"""Integrate round-8 exact-main findings and coverage into the audit ledger."""

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

PROOF_SPANS = {
    "LAB-001": [
        ("src/dashboard/lib/chuyen-tiep-tai-len.ts", 27, 43),
        ("src/dashboard/app/api/cskh/ket-qua/route.ts", 75, 82),
        ("src/dashboard/app/(dashboard)/customers/TepKetQua.tsx", 194, 210),
        ("src/clinicai/api/v1/routers/cskh.py", 729, 753),
        ("src/clinicai/services/tep_ket_qua_service.py", 855, 863),
        ("src/clinicai/services/tep_ket_qua_service.py", 908, 927),
        ("src/clinicai/services/tep_ket_qua_service.py", 960, 980),
        ("supabase/migrations/20260809000008_tep_ket_qua.sql", 57, 63),
        ("src/tests/services/test_full_chi_dinh_slice_ab_db.py", 636, 658),
    ],
    "CLIN-034": [
        ("src/dashboard/app/(dashboard)/tasks/AndrologyReview.tsx", 55, 82),
        ("src/dashboard/app/(dashboard)/tasks/AndrologyReview.tsx", 84, 99),
        ("src/dashboard/app/(dashboard)/tasks/AndrologyReview.tsx", 127, 137),
        ("src/dashboard/app/(dashboard)/tasks/ServiceFormEngine.tsx", 335, 339),
        ("src/clinicai/api/v1/routers/clinical_forms.py", 96, 107),
    ],
    "FE-011": [
        ("src/dashboard/app/(dashboard)/tasks/ServiceFormEngine.tsx", 69, 77),
        ("src/dashboard/app/(dashboard)/tasks/ServiceFormEngine.tsx", 335, 339),
        ("src/dashboard/app/(dashboard)/tasks/AndrologyReview.tsx", 58, 90),
        ("src/dashboard/app/api/clinical-form/andrology-review/route.ts", 14, 27),
        ("src/clinicai/api/v1/routers/clinical_forms.py", 23, 26),
        ("src/clinicai/api/v1/routers/clinical_forms.py", 39, 53),
        ("src/clinicai/api/v1/routers/clinical_forms.py", 103, 122),
        ("src/clinicai/permissions/y_khoa.py", 27, 60),
        ("src/clinicai/services/andrology_review_service.py", 184, 203),
        ("src/clinicai/services/andrology_review_service.py", 220, 235),
    ],
    "SEC-018": [
        ("supabase/migrations/20260801000003_adopt_prod_only_tables.sql", 70, 87),
        ("supabase/migrations/20260801000003_adopt_prod_only_tables.sql", 101, 118),
        ("supabase/migrations/20260801000003_adopt_prod_only_tables.sql", 126, 150),
        ("supabase/migrations/20260730000003_multi_tenant_foundation.sql", 235, 267),
        ("docker-compose.supabase.yml", 152, 171),
        ("caddy/Caddyfile", 191, 194),
        ("src/clinicai/api/identity.py", 56, 70),
        ("supabase/tests/tenant_scoped_rls.sql", 388, 429),
        ("supabase/tests/role_scoped_clinical_read.sql", 102, 144),
    ],
}


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


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


def integrate_findings() -> list[dict]:
    canonical = read_json("PHAT-HIEN.json")
    by_id = {item["id"]: item for item in canonical}
    candidates = []
    for name in (
        "blocks/round8_lab.findings.json",
        "blocks/round8_frontend.findings.json",
        "blocks/round8_api.findings.json",
        "blocks/round8_tenant.findings.json",
    ):
        candidates.extend(read_json(name))

    candidate_ids = [item["id"] for item in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("duplicate candidate ID across round-8 files")

    inserted = []
    for candidate in candidates:
        existing = by_id.get(candidate["id"])
        if existing is not None:
            if (
                existing.get("title") == candidate.get("title")
                and existing.get("source_hashes") == candidate.get("source_hashes")
                and existing.get("reference_version") == "pinned_main"
            ):
                continue
            raise ValueError(f"conflicting finding ID already in ledger: {candidate['id']}")
        item = copy.deepcopy(candidate)
        item["evidence_level"] = "confirmed_static"
        item["reference_version"] = "pinned_main"
        item["status"] = "open"
        item["source_hashes"] = dict(item.get("source_hashes", {}))
        for path, expected in item["source_hashes"].items():
            actual = hashlib.sha256((SNAPSHOT / path).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"source hash mismatch: {item['id']} {path}")

        item["main_validation"] = {
            "sha": SNAPSHOT_SHA,
            "status": "still_present_on_main",
            "note": (
                "Root đã đối chiếu các đoạn nguồn exact-main được trích bên dưới. "
                "Đây là trace tĩnh; chưa xác nhận hành vi production hoặc tái hiện runtime."
            ),
            "evidence": [source_evidence(*span) for span in PROOF_SPANS[item["id"]]],
            "production_verified": False,
        }
        item["main_validation"]["evidence"].sort(
            key=lambda proof: (proof["path"], proof["line"])
        )
        for proof in item["main_validation"]["evidence"]:
            expected = item["source_hashes"].get(proof["path"])
            if expected != proof["sha256"]:
                raise ValueError(f"proof hash absent or mismatched: {item['id']} {proof['path']}")
        canonical.append(item)
        by_id[item["id"]] = item
        inserted.append(item)
    write_json("PHAT-HIEN.json", canonical)
    return inserted


def merge_coverage() -> dict[str, str]:
    manifest = read_json("MAIN-PHAM-VI.json")
    by_path = {item["path"]: item for item in manifest["files"]}
    read_paths: set[str] = set()
    traced_paths: set[str] = set()
    coverage_inputs = (
        "blocks/round8_lab.coverage.json",
        "blocks/round8_frontend.coverage.json",
        "blocks/round8_api.coverage.json",
        "blocks/round8_tenant.coverage.json",
    )

    for name in coverage_inputs:
        coverage = read_json(name)
        sha = coverage.get("snapshot_sha", coverage.get("sha"))
        if sha != SNAPSHOT_SHA:
            raise ValueError(f"coverage uses wrong snapshot: {name}")
        for row in coverage["files"]:
            path = row["path"]
            if path not in by_path:
                continue
            ledger = by_path[path]
            if ledger.get("sha256") != row["sha256"]:
                raise ValueError(f"coverage hash mismatch: {name} {path}")
            status = row["status"]
            is_full = status in {"full_semantic_read", "traced_full", "read"} or row.get(
                "full_file_read", False
            )
            target = "read" if is_full else "traced"
            if ledger["status"] != "excluded":
                rank = {"inventoried": 0, "scanned": 1, "traced": 2, "read": 3}
                if rank.get(target, 0) > rank.get(ledger["status"], 0):
                    ledger["status"] = target
            if target == "read":
                read_paths.add(path)
            else:
                traced_paths.add(path)
            method = f"Round 8: {status}; slice-only, see {name}."
            if method not in ledger.get("method", ""):
                ledger["method"] = (ledger.get("method", "").rstrip(" |") + " | " + method).strip(" |")

    write_json("MAIN-PHAM-VI.json", manifest)
    return {"read": str(len(read_paths)), "traced": str(len(traced_paths))}


def update_checks(inserted: list[dict]) -> None:
    checks = read_json("KIEM-CHUNG.json")
    existing = {(row.get("id"), row.get("path")) for row in checks["checks"]}
    for item in inserted:
        for path in item["source_hashes"]:
            key = (item["id"], path)
            if key not in existing:
                checks["checks"].append({"id": item["id"], "path": path, "valid": True})
                existing.add(key)
    write_json("KIEM-CHUNG.json", checks)


def update_state(inserted: list[dict]) -> None:
    state = read_json("STATE.json")
    manifest = read_json("MAIN-PHAM-VI.json")
    findings = read_json("PHAT-HIEN.json")
    files = manifest["files"]
    coverage = Counter(item["status"] for item in files)
    suffixes = {
        ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql",
        ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html",
    }
    code_files = [item for item in files if Path(item["path"]).suffix.lower() in suffixes]
    code_coverage = Counter(item["status"] for item in code_files)
    severity = Counter(item["severity"] for item in findings)
    levels = Counter(item["evidence_level"] for item in findings)
    main_status = Counter(item["main_validation"]["status"] for item in findings)
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")

    state["updated_at"] = now
    state["status"] = "in_progress"
    state["phase"] = "round8_result_upload_andrology_and_permissions_checkpoint"
    state["next_action"] = (
        "Round 8 is integrated. Continue exact-main source audit with an unreviewed subsystem; "
        "SEC-018 still needs role-boundary validation on an already available isolated disposable DB, "
        "if one can be proven safe to use. Do not create a DB or use shared CI DB. Full source audit remains incomplete."
    )
    state["report_status"] = f"v0.26_{len(findings)}_findings_pending_html_and_bundle_QA; full source audit incomplete"
    state["limits"][0] = (
        f"Full source audit incomplete: {coverage['inventoried']} inventoried, "
        f"{coverage['traced']} partial traces, {coverage['scanned']} scanned, "
        f"{coverage['excluded']} excluded; traced is not full-file semantic review."
    )
    round8_limit = (
        "Round 8 adds exact-main static traces for result-file upload retry and two Andrology UI/access contracts; "
        "SEC-018 adds an intra-clinic patient-contact least-privilege candidate. The permission-admin slice "
        "corroborates SEC-012 without a new finding. No DB/runtime/production test was run."
    )
    if round8_limit not in state["limits"]:
        state["limits"].append(round8_limit)
    coverage_limit = (
        "Round 8 file-level coverage is merged into the path ledger; counts describe read/trace/scanned status, "
        "not percentage of behavior reviewed."
    )
    if coverage_limit not in state["limits"]:
        state["limits"].append(coverage_limit)
    prev = state["summary"]
    prev["findings"] = len(findings)
    prev["severity"] = dict(severity)
    prev["evidence_levels"] = dict(levels)
    prev["main_status"] = dict(main_status)
    prev["main_files"] = len(files)
    prev["main_partial_traces"] = coverage["traced"]
    prev["main_coverage"] = dict(coverage)
    prev["code_like_source_files"] = {
        "definition": prev["code_like_source_files"]["definition"],
        "total": len(code_files),
        "coverage": dict(code_coverage),
        "traced_is_partial": True,
    }
    prev["new_findings_v026"] = ["LAB-001", "CLIN-034", "FE-011", "SEC-018"]
    prev["main_read_files"] = coverage["read"]

    state["blocks"]["clinical"].update(
        status="round8_andrology_static_trace_not_complete",
        findings="PHAT-HIEN.json (CLIN-001..CLIN-034)",
        next="CLIN-034: Andrology review keeps a prior snapshot visible during debounce/loading. Static-only; add component tests and continue unreviewed clinical forms/workflows.",
    )
    state["blocks"]["frontend"].update(
        status="round8_andrology_access_contract_static_not_complete",
        findings="PHAT-HIEN.json includes FE-011; blocks/frontend.findings.json remains prior-slice evidence",
        next="FE-011: read-only form mounts review endpoint guarded by write permissions; settle read/write contract and test the permission matrix. Continue remaining dashboard flows.",
    )
    state["blocks"]["results_upload"] = {
        "status": "round8_static_trace_not_complete",
        "notes": "blocks/round8_lab.md",
        "findings": "PHAT-HIEN.json (LAB-001)",
        "coverage": "blocks/round8_lab.coverage.json",
        "next": "LAB-001: upload response loss after commit can be reported as not saved and a retry can create another file row/event. No runtime fault injection; add stable upload intent and reconciliation after policy review.",
    }
    state["blocks"]["security"]["status"] = "round8_sec018_static_candidate_sec012_corroboration_not_complete"
    state["blocks"]["security"]["round8_notes"] = "blocks/round8_tenant.md; blocks/round8_api.md"
    state["blocks"]["security"]["round8_next"] = "SEC-018 is a static intra-clinic patient-contact role-scope candidate; verify role boundary on a disposable DB and retain invoice projection. SEC-012 is corroborated; persisted skill-toggle retry/fault test remains missing."
    state["artifacts"]["integration_script"] = "integrate_v026.py"
    state["artifacts"]["qa"] = "HTML-QA.json; report validation/browser checks are still pending for v0.26"
    for key in ("html_sha256", "html_checked_at", "bundle_verified_at", "bundle_entries", "bundle_outer_sha256"):
        state["artifacts"].pop(key, None)
    write_json("STATE.json", state)


def upsert_section(path: str, heading: str, body: str) -> None:
    file = ROOT / path
    contents = file.read_text()
    if heading not in contents:
        file.write_text(contents.rstrip() + "\n\n" + heading + "\n\n" + body.strip() + "\n")
        return
    start = contents.index(heading)
    next_heading = contents.find("\n## ", start + len(heading))
    end = next_heading if next_heading >= 0 else len(contents)
    file.write_text(contents[:start] + heading + "\n\n" + body.strip() + "\n" + contents[end:])


def update_handoffs(inserted: list[dict]) -> None:
    ids = "LAB-001, CLIN-034, FE-011, SEC-018"
    note = (
        f"Round 8 exact-main checkpoint ({ids}). Four findings were added after independent "
        "source-hash and excerpt verification. The permission-admin slice found no new item and "
        "corroborates SEC-012. All four additions are confirmed_static, still present in the pinned "
        "snapshot, and not runtime/production-confirmed. SEC-018 describes same-clinic role scope, "
        "not cross-tenant access. Main source "
        "review remains incomplete; continue from STATE.json and blocks/round8_*. The dirty working "
        "tree is not evidence; source remains /tmp/clinicai-audit-main-956ba4f2 at "
        f"{SNAPSHOT_SHA}."
    )
    upsert_section("NHAT-KY.md", "## Round 8 — upload kết quả, Nam khoa, phân quyền và tenant", note)
    upsert_section("TIEP-TUC.md", "## Checkpoint mới nhất — round 8", note + " Đọc cả bốn block round8 (lab, frontend, API và tenant) cùng coverage JSON. Tiếp theo tiếp tục audit phần source chưa kiểm; không gọi trạng thái này là đã đọc hết repo.")
    upsert_section("BAT-DAU-TU-DAY.md", "## Điểm tiếp quản round 8", note + " Đọc `round8_lab.md`, `round8_frontend.md`, `round8_api.md`, `round8_tenant.md` và coverage JSON tương ứng. Trang HTML đã được dựng/kiểm tra riêng; tạo lại gói ZIP sau mọi thay đổi audit.")


def main() -> None:
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"pinned source snapshot is missing: {SNAPSHOT}")
    inserted = integrate_findings()
    merge_coverage()
    update_checks(inserted)
    update_state(inserted)
    update_handoffs(inserted)
    print(f"Integrated {len(inserted)} findings: {', '.join(item['id'] for item in inserted)}")


if __name__ == "__main__":
    main()
