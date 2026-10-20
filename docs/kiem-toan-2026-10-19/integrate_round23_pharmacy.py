"""Checkpoint round-23 pharmacy lifecycle review on the pinned main snapshot."""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import integrate_round22 as r22

ROOT = Path(__file__).resolve().parent
SNAPSHOT = r22.SNAPSHOT
PINNED_SHA = r22.PINNED_SHA
prior = r22.prior
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
    state = read_json("STATE.json")
    held = state.get("held_observations", [])
    held_ids = {x.get("id") for x in held}

    observations = [
        {
            "id": "PHARMACY-BIO-SERVICE-MAP-001",
            "classification": "held_business_contract_question_suggestion_vs_allowlist",
            "severity_assessment": "Unclassified; schema/comment calls the mapping a suggestion, so rejecting unmapped service_price_id is not yet a proven contract.",
            "snapshot_sha": PINNED_SHA,
            "trigger": "A caller submits a service_price_id belonging to a same-clinic sellable VATU_GOI_Y group but not listed under the selected service_code mapping.",
            "impact": "The write path checks clinic, group, sellable and approval state, but does not enforce the UI suggestion mapping. If the mapping is an allowlist, the service can accept an item the UI would not present; if it is guidance only, current behavior may be intended. No invalid production row was inspected.",
            "evidence": [
                {"path": "src/clinicai/services/bio_chi_dinh_service.py", "lines": "67-78,270-290", "sha256": prior.source("src/clinicai/services/bio_chi_dinh_service.py")[1]},
                {"path": "src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/DauDoChiDinh.tsx", "lines": "6-13,106-122", "sha256": prior.source("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/DauDoChiDinh.tsx")[1]},
            ],
            "not_promoted_reason": "Migration/comment names the map as a suggestion and product contract is not confirmed; no demonstrated financial or operational harm.",
            "next": "Owner decides suggestion versus hard allowlist. If hard, validate the service_code/service_price_id pair server-side and add a same-clinic unmapped-ID denial test; otherwise label the UI mapping as guidance.",
        },
        {
            "id": "PHARMACY-ORDER-HISTORY-CAP-001",
            "classification": "held_low_priority_unpaged_history_cap",
            "severity_assessment": "LOW; behavior is static and only affects records beyond 200; no threshold occurrence is known.",
            "snapshot_sha": PINNED_SHA,
            "trigger": "A patient has more than 200 eligible order-history rows and staff needs a row older than the service limit.",
            "impact": "Service returns at most 200 rows and logs a warning; the UI only signals more when co_them is true, so reaching the cap may look like the full history. No real patient count or lost action was checked.",
            "evidence": [
                {"path": "src/clinicai/services/ban_theo_don_service.py", "lines": "258-279,314-369", "sha256": prior.source("src/clinicai/services/ban_theo_don_service.py")[1]},
                {"path": "src/dashboard/app/(dashboard)/pharmacy/LichSuDonThuoc.tsx", "lines": "1-260", "sha256": prior.source("src/dashboard/app/(dashboard)/pharmacy/LichSuDonThuoc.tsx")[1]},
            ],
            "not_promoted_reason": "Threshold-dependent UI completeness issue; recurring page-cap patterns are already captured elsewhere and no >200-row case is evidenced.",
            "next": "Either add cursor/has_more with a visible older-history control or document the 200-row window; add a synthetic 201-row fixture and select the oldest record.",
        },
    ]
    for item in observations:
        if item["id"] not in held_ids:
            held.append(item)
            held_ids.add(item["id"])

    full_reads = {
        "src/clinicai/services/ban_theo_don_service.py": "Full 485-line read; order-history cap, sale/re-sale idempotency and bill interactions reviewed.",
        "src/clinicai/services/bio_chi_dinh_service.py": "Full 390-line read; Bio selection validation, approval and bill coupling reviewed.",
        "src/clinicai/services/theo_hang_hoa_service.py": "Full 209-line read; inventory reporting delegates to invoice source and uses accounting access path.",
    }
    ranges = [
        ("src/clinicai/api/v1/routers/pharmacy.py", 196, 292, "Pharmacy endpoints and service boundaries."),
        ("src/clinicai/api/v1/routers/luot_kham.py", 548, 581, "Visit endpoint for Bio/visit prescription flow."),
        ("src/clinicai/api/v1/routers/hoa_don.py", 123, 158, "Invoice-facing route and permission boundary."),
        ("src/clinicai/services/ban_le_service.py", 125, 180, "Retail sales and billing interaction."),
        ("src/dashboard/app/(dashboard)/pharmacy/LichSuDonThuoc.tsx", 1, 260, "History table shows pagination/cap presentation."),
        ("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/DauDoChiDinh.tsx", 1, 130, "UI mapping and Bio selection payload."),
        ("supabase/migrations/20261014190000_bio_theo_chi_dinh.sql", 26, 64, "Bio mapping schema/comment semantics."),
        ("src/tests/services/test_ban_theo_don_db.py", 1, 442, "DB test suite reviewed; not executed."),
        ("src/tests/services/test_bio_chi_dinh_db.py", 100, 210, "Fixtures reviewed; not executed."),
        ("src/tests/services/test_bio_chi_dinh_db.py", 330, 720, "Bio DB behavior and invariant tests reviewed; not executed."),
        ("src/tests/services/test_theo_hang_hoa_db.py", 1, 106, "Inventory reporting access/source test reviewed; not executed."),
        ("src/tests/unit/test_ban_theo_don.py", 1, 154, "Pure helper tests reviewed; not executed."),
        ("src/tests/unit/test_theo_hang_hoa.py", 1, 115, "Pure output/formula safety tests reviewed; not executed."),
    ]
    all_ranges: dict[str, list[tuple[int, int, str]]] = {}
    for item in observations:
        for ev in item["evidence"]:
            start_s, *more = ev["lines"].split(",")
            start_bits = start_s.split("-")
            start = int(start_bits[0])
            end = int(start_bits[1]) if len(start_bits) > 1 else start
            all_ranges.setdefault(ev["path"], []).append((start, end, f"Held {item['id']}; see STATE.json for remaining evidence."))
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
        if any(start < 1 or end < start or end > len(lines) for start, end, _ in spans):
            raise SystemExit(f"Reviewed range is outside pinned source: {path} ({len(lines)} lines)")
        old = row["status"]
        is_full = path in full_reads
        status = "read" if is_full else ("traced" if rank[old] < rank["traced"] else old)
        row["status"] = status
        mode = "full_file_read" if is_full else "targeted_semantic_trace"
        row["method"] = f"{row.get('method', '')} | Round 23 pharmacy {mode}: " + "; ".join(f"{a}-{b}" for a,b,_ in spans)
        coverage_files.append({
            "path": path, "status": status, "prior_status": old,
            "read_level_this_round": mode, "full_file_read_this_round": is_full,
            "ranges": [{"start": a, "end": b, "purpose": purpose} for a,b,purpose in spans],
            "sha256": digest, "line_count": len(lines),
        })
    write_json("MAIN-PHAM-VI.json", manifest)
    write_json("blocks/round23_pharmacy_coverage.json", {
        "schema_version": 1,
        "audit": "round23_pharmacy_billing_lifecycle",
        "snapshot": {"path": str(SNAPSHOT), "sha": PINNED_SHA},
        "review_mode": "static_read_only_exact_main_cross_layer_trace",
        "scope": ["prescription sale/re-sale, order-history contract, Bio selection, billing and inventory reporting"],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "Three full service reads, API/UI/migration/test traces. No finding was promoted. Bio mapping semantics and the 200-row order history cap remain held; tests were read, not run.",
        "held_observations": [x["id"] for x in observations],
        "files": coverage_files,
    })
    state["held_observations"] = held
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    state["updated_at"] = now
    state["phase"] = "round23_pharmacy_lifecycle_checkpoint"
    state["report_version"] = "v0.44"
    state["report_round_summary"] = (
        "Round 22 thêm SEC-030 về scope tài chính PostgREST và mở rộng SEC-011 cho TKYK; event/provider không thêm lỗi mới. "
        "Round 23 đọc trọn ba service dược/billing, không promote finding; hai observation về mapping Bio và ngưỡng 200 đơn được giữ riêng. "
        "Không chạy ClinicAI app/DB/API/provider/production test; chỉ QA report sau khi dựng."
    )
    state["next_action"] = (
        "Continue exact-main semantic review of clinical-form definitions/parsers and remaining patient/API callers. "
        "Then test payment and TKYK PostgREST boundaries on a disposable stack, and continue unread scanned/inventoried source. "
        "Resolve Bio mapping semantics and 200-row history behavior with product owners. Full source audit remains incomplete."
    )
    state["report_status"] = "v0.44_pending_report_QA; full source audit incomplete"
    state["summary"]["main_coverage"] = {key: counts.get(key, 0) for key in ("inventoried", "read", "traced", "scanned", "excluded")}
    state["summary"]["main_read_files"] = counts["read"]
    state["summary"]["main_partial_traces"] = counts["traced"]
    state["summary"]["code_like_source_files"]["coverage"] = {key: code_counts.get(key, 0) for key in ("inventoried", "traced", "scanned", "read")}
    state["summary"]["reviewed_slice_v044"] = "Round 23 pharmacy/billing lifecycle static review: no new finding; two policy/threshold observations held."
    state.setdefault("blocks", {})["round23_pharmacy_lifecycle"] = {
        "status": "static review complete; 3 services fully read; no new finding; 2 policy/threshold observations held",
        "scope": "prescription sales, Bio service selection, billing and inventory reporting",
        "artifacts": "blocks/round23_pharmacy_coverage.json; integrate_round23_pharmacy.py",
        "findings": "No new canonical finding; service-map semantics and 200-row history cap remain held.",
        "next": "Continue clinical-form pipeline and test conditional cases only on synthetic disposable fixtures.",
    }
    state["artifacts"]["integration_script"] = "integrate_round23_pharmacy.py; round23 pharmacy coverage in blocks/round23_pharmacy_coverage.json; prior checkpoints retained."
    state["artifacts"]["qa"] = "Pending v0.44 structural/evidence, browser and audit-only package QA; application behavior not validated in round 23."
    state["artifacts"]["bundle_integrity"] = "Pending v0.44 audit-only package rebuild and verification."
    state["artifacts"]["html_sha256"] = "pending v0.44 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.44 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.44 package verification"
    state.setdefault("runtime_summary", {})["round23_pharmacy"] = "Static exact-main review only; related tests were read, not run; no DB/runtime/production/PHI/secrets accessed."
    write_json("STATE.json", state)
    print(json.dumps({"held_observations": [x["id"] for x in observations], "reviewed_paths": len(coverage_files), "full_reads": len(full_reads), "coverage": dict(counts), "updated_at": now}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
