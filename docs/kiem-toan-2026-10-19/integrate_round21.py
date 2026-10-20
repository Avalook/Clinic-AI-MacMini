"""Integrate round-21 patient PostgREST, dashboard contract and finance slices.

Writes audit artifacts only. Every promoted source excerpt is fingerprinted
against the immutable exact-main checkout before it is accepted.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import integrate_round20 as r20

ROOT = Path(__file__).resolve().parent
SNAPSHOT = r20.SNAPSHOT
PINNED_SHA = r20.PINNED_SHA
prior = r20.prior
CODE_SUFFIXES = prior.CODE_SUFFIXES


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def ev(path: str, start: int, end: int, detail: str) -> dict:
    return prior.evidence((path, start, end, detail))


def main() -> None:
    actual_sha = subprocess.check_output(
        ["git", "-C", str(SNAPSHOT), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != PINNED_SHA:
        raise SystemExit(f"Pinned source mismatch: expected {PINNED_SHA}, got {actual_sha}")

    manifest = read_json("MAIN-PHAM-VI.json")
    if manifest["sha"] != PINNED_SHA:
        raise SystemExit("MAIN-PHAM-VI.json does not reference pinned main")
    by_path = {row["path"]: row for row in manifest["files"]}
    findings = read_json("PHAT-HIEN.json")
    by_id = {row["id"]: row for row in findings}
    if "SEC-029" in by_id:
        raise SystemExit("SEC-029 already exists; refusing duplicate integration")

    limits = (
        "Round 21 is static exact-main review. No PostgREST HTTP/JWT request, ClinicAI "
        "application test, DB runtime, production, secret or patient data was used. "
        "A valid Supabase authenticated session and gateway behavior still need a "
        "synthetic integration check."
    )
    new = prior.finding(
        id="SEC-029",
        title="PostgREST cho tài khoản cùng clinic đọc trực tiếp toàn bộ hồ sơ bệnh nhân",
        severity="MEDIUM",
        level="confirmed_static",
        category="patient_data_postgrest_role_scope",
        summary=(
            "Migration cấp SELECT trên bảng patient cho role authenticated và policy chỉ "
            "lọc clinic_id qua current_clinic_ids(); helper kiểm membership active nhưng "
            "không kiểm capability/role. Bảng có CCCD, điện thoại, ngày sinh và địa chỉ. "
            "Caddy công khai /rest/v1/* tới gateway Supabase, còn đăng nhập dashboard tạo "
            "phiên Supabase gắn với nhân viên. Đây là đường đọc trực tiếp, không đi qua "
            "patient.list.view hoặc DTO/projection của FastAPI."
        ),
        trigger=(
            "Một nhân viên có JWT Supabase role authenticated của clinic gọi trực tiếp "
            "PostgREST GET /rest/v1/patient?select=*; có ý nghĩa nhất khi role đó không "
            "được cấp patient.list.view."
        ),
        impact=(
            "Nhân viên trong cùng clinic có thể đọc hàng loạt các trường định danh trên "
            "toàn bộ bệnh nhân mà RLS cho phép theo tenant, vượt ranh capability và "
            "projection của API. Code tĩnh chưa xác nhận request qua gateway/JWT thực tế, "
            "không cho thấy đọc chéo clinic, dữ liệu đã bị lấy hay có sự cố production."
        ),
        recommendation=(
            "Đưa patient reads qua API có guard capability, object/location scope và DTO "
            "tối thiểu; hoặc thiết kế projection/RPC trực tiếp với RLS theo capability và "
            "cột được phép. Không tự cấp SELECT bảng gốc cho mọi authenticated chỉ vì "
            "bảng có một read policy tenant. Nếu Realtime cần tín hiệu bệnh nhân, phát "
            "projection tối thiểu riêng và giữ dữ liệu định danh ngoài kênh đó."
        ),
        acceptance=(
            "Trong stack Supabase disposable từ migrations ghim, lấy JWT cho các vai "
            "RECEPTION, CASHIER, PHARMACIST và DOCTOR. Gọi trực tiếp PostgREST patient "
            "với select=* và các cột national_id_number/phone/address; chỉ vai/đường có "
            "quyền rõ ràng mới đọc được, cross-clinic luôn bị chặn. Kiểm đồng thời API "
            "FastAPI, Realtime subscription và quyền cột để bảo đảm quy trình quầy còn đủ "
            "dữ liệu mà không mở bảng gốc."
        ),
        note=(
            "Static chain: patient nằm trong danh sách tenant_read; policy chỉ so "
            "clinic_id/current_clinic_ids; current_clinic_ids không lọc capability; "
            "migration grants SELECT authenticated trên mọi bảng có SELECT policy; "
            "Caddy chuyển /rest/v1/* tới Supabase. Test role-scoped hiện chủ ý cho RECEPTION "
            "đọc row patient nhưng không kiểm vai thiếu patient.list.view hoặc cột PII. "
            "Chưa thực hiện request PostgREST."
        ),
        refs=[
            (
                "supabase/migrations/20260730000004_tenant_scoped_rls.sql",
                149, 168,
                "patient được tạo policy SELECT authenticated chỉ theo current_clinic_ids.",
            ),
            (
                "supabase/migrations/20260730000003_multi_tenant_foundation.sql",
                235, 246,
                "current_clinic_ids kiểm membership active; không áp role/capability.",
            ),
            (
                "supabase/migrations/20260730000008_table_grants.sql",
                47, 58,
                "Cấp SELECT cho authenticated trên mọi bảng có SELECT policy.",
            ),
            (
                "supabase/migrations/20260714000001_baseline_schema.sql",
                617, 640,
                "Bảng patient chứa national_id_number, điện thoại, ngày sinh và địa chỉ.",
            ),
            (
                "caddy/Caddyfile",
                191, 194,
                "Đường công khai /rest/v1/* được reverse proxy tới Supabase gateway.",
            ),
            (
                "src/dashboard/app/(auth)/login/actions.ts",
                33, 48,
                "Đăng nhập Supabase và liên kết user với staff.",
            ),
            (
                "src/dashboard/lib/supabase-browser.ts",
                7, 12,
                "Browser client dùng phiên Supabase authenticated và anon key.",
            ),
            (
                "supabase/tests/role_scoped_clinical_read.sql",
                121, 143,
                "Test hiện tại chủ ý cho Reception đọc patient, nhưng không kiểm role thiếu capability hoặc cột PII.",
            ),
        ],
        tests=[
            "supabase/tests/tenant_scoped_rls.sql — kiểm ranh tenant; đã đọc, không chạy round 21.",
            "supabase/tests/role_scoped_clinical_read.sql — kiểm Reception đọc clinical_record = 0 và patient = 1; không kiểm vai thiếu patient.list.view hoặc quyền cột; đã đọc, không chạy.",
        ],
        related=[
            {
                "id": "SEC-027",
                "relationship": "SEC-027 là API FastAPI tra bệnh nhân thiếu patient.list.view; SEC-029 là đường PostgREST trực tiếp vượt các guard/projection đó.",
            },
            {
                "id": "SEC-022",
                "relationship": "SEC-022 ghi nhận PII trong API payload; SEC-029 là SELECT trực tiếp bảng nguồn qua gateway.",
            },
        ],
        result=(
            "Đã xác minh migration policy/grant, helper tenant, cột patient, đăng nhập Supabase "
            "và public gateway route trên exact-main. Chưa gửi HTTP request hoặc xác nhận "
            "khả năng khai thác trong môi trường chạy."
        ),
        limitations=limits,
    )

    # Consolidate a second stale-data screen into FE-002: same user-visible failure
    # contract (keep old data but fail to label it stale), not a separate finding.
    stale = by_id["FE-002"]
    stale["title"] = "Dashboard giữ dữ liệu cũ nhưng không báo lần làm mới thất bại"
    stale["summary"] += (
        " Round 21 trace thêm PhanHoiThuocKhach: sau khi tải thành công, event "
        "tuong_tac_cskh kích hoạt tải lại; nếu request lỗi, component giữ data và loiDoc "
        "nhưng chỉ hiển thị lỗi khi chưa có data. Dòng tóm tắt đầu khung cũng không được "
        "cập nhật. Đây là cùng lỗi stale-state/thiếu dấu hiệu freshness, không tạo finding mới."
    )
    stale["trigger"] += (
        " Với phản hồi thuốc: người khác thêm/gỡ tương tác CSKH rồi lần tải do event lỗi."
    )
    stale["impact"] += (
        " Ở khung khách, CSKH có thể đọc phản hồi thuốc cũ như hiện trạng mà không thấy "
        "lỗi tải lại; chưa chứng minh quyết định lâm sàng bị ảnh hưởng."
    )
    stale["recommendation"] = (
        "Giữ dữ liệu cũ nhưng gắn nhãn stale, lần tải thành công cuối, lý do và nút thử lại "
        "ở cả bảng hành trình và phản hồi thuốc. Phân biệt trạng thái kết nối SSE với độ mới "
        "của từng dữ liệu; chỉ bỏ nhãn stale sau response thành công."
    )
    stale["acceptance"] = (
        "Browser tests cho hai màn: sau lần tải thành công, tạo SSE/poll/event refresh rồi "
        "trả lỗi; nội dung cũ vẫn đọc được nhưng có cảnh báo stale, thời điểm tải cuối và "
        "nút thử lại. 200 với data mới gỡ cảnh báo; 200 empty phải được phân biệt với lỗi."
    )
    stale["validation"]["result"] += (
        " Round 21 bổ sung static trace PhanHoiThuocKhach → BFF → FastAPI → caller; chưa chạy browser test."
    )
    stale["validation"]["limitations"] += (
        " Round 21 không tái hiện lỗi refresh trên dashboard."
    )
    stale["main_validation"]["note"] += (
        " Round 21 xác nhận cùng stale/error-hidden pattern ở khung phản hồi thuốc của hồ sơ khách; "
        "hợp nhất làm bằng chứng cho FE-002, không tăng số finding."
    )
    stale["related_tests"] = list(dict.fromkeys(stale.get("related_tests", []) + [
        "src/dashboard/tests/phan-hoi-thuoc-cot-boundary.test.mts:81-92 — kiểm callback/tóm tắt, không kiểm lỗi tải lại sau khi đã có data.",
        "src/tests/services/test_phan_hoi_thuoc_db.py:75-139 — kiểm đường đọc/ghi thành công; không kiểm stale-state của UI.",
    ]))
    new_stale_refs = [
        ev(
            "src/dashboard/app/(dashboard)/_lam-viec/PhanHoiThuocKhach.tsx",
            103, 132,
            "Refresh lỗi giữ data cũ; lỗi chỉ render khi chưa có data.",
        ),
        ev(
            "src/dashboard/app/(dashboard)/_lam-viec/PhanHoiThuocKhach.tsx",
            158, 165,
            "Summary callback chỉ chạy khi data đổi, nên lỗi refresh không làm mới tóm tắt.",
        ),
        ev(
            "src/dashboard/app/api/cskh/khach/[id]/route.ts",
            38, 40,
            "BFF chuyển request đọc phản hồi thuốc tới backend.",
        ),
        ev(
            "src/clinicai/api/v1/routers/cskh.py",
            161, 170,
            "FastAPI trả danh sách phản hồi thuốc cho patient id.",
        ),
        ev(
            "src/dashboard/app/(dashboard)/_lam-viec/KhungKhach.tsx",
            343, 350,
            "Component phản hồi thuốc được mount trong khung khách.",
        ),
    ]
    for item in new_stale_refs:
        key = (item["path"], item["line"], item["end_line"])
        if not any((old["path"], old["line"], old["end_line"]) == key for old in stale["main_validation"]["evidence"]):
            stale["main_validation"]["evidence"].append(item)
        if not any((old["path"], old["line"], old["end_line"]) == key for old in stale["evidence"]):
            stale["evidence"].append({k: item[k] for k in ("path", "line", "end_line", "detail")})
        stale["source_hashes"][item["path"]] = item["sha256"]

    # Low-priority and policy-dependent candidates stay visible without inflating
    # the canonical risk count or presenting unresolved policy as a confirmed bug.
    state = read_json("STATE.json")
    held = state.get("held_observations", [])
    held_by_id = {item.get("id"): item for item in held}
    held_candidates = [
        {
            "id": "PHARMACY-RESPONSE-VISIT-CAP-001",
            "classification": "held_low_priority_unpaged_picker_limit",
            "severity_assessment": "LOW; verified API/UI contract, threshold impact depends on a patient having over 20 eligible visits.",
            "snapshot_sha": PINNED_SHA,
            "trigger": "A patient has more than 20 visits containing prescriptions and staff needs to attach feedback to a visit outside the returned page.",
            "impact": "The picker returns at most 20 visits and the UI renders them as complete; an older eligible visit cannot be selected from that component. No evidence that a real patient exceeded the threshold.",
            "evidence": [
                {
                    "path": "src/clinicai/services/phan_hoi_thuoc_service.py",
                    "lines": "34-38,103-146",
                    "sha256": prior.source("src/clinicai/services/phan_hoi_thuoc_service.py")[1],
                },
                {
                    "path": "src/clinicai/api/v1/routers/cskh.py",
                    "lines": "161-170",
                    "sha256": prior.source("src/clinicai/api/v1/routers/cskh.py")[1],
                },
                {
                    "path": "src/dashboard/app/(dashboard)/_lam-viec/PhanHoiThuocKhach.tsx",
                    "lines": "167-185",
                    "sha256": prior.source("src/dashboard/app/(dashboard)/_lam-viec/PhanHoiThuocKhach.tsx")[1],
                },
            ],
            "not_promoted_reason": "LOW, volume-dependent missing page indicator; list-cap failures already recur across FE-003, FE-020, FE-022 and FIN-002. Retain for product triage and avoid a duplicate cross-cutting count until caps are consolidated.",
            "next": "Either add cursor/has_more and a visible older-visit search, or state the 20-visit window; add a fixture with 21+ eligible visits and test selecting the oldest.",
        },
        {
            "id": "FIN-REFUND-ACCOUNTING-DATE-001",
            "classification": "held_accounting_policy_question",
            "severity_assessment": "Unclassified pending clinic/accounting policy; code semantics are statically clear but correct business date is not.",
            "snapshot_sha": PINNED_SHA,
            "trigger": "A bank refund is requested on day/shift N, remains pending through close, then is confirmed paid on day/shift N+1.",
            "impact": "Current report groups the completed refund by created_at while the debt ledger records occurred_at at confirmation; depending on accounting basis, daily report and ledger can assign the cash event to different periods. No runtime reproduction or approved accounting rule was available.",
            "evidence": [
                {"path": "src/clinicai/services/hoan_tien_service.py", "lines": "218-238", "sha256": prior.source("src/clinicai/services/hoan_tien_service.py")[1]},
                {"path": "src/clinicai/services/bao_cao_cuoi_ngay_service.py", "lines": "236-256,989-1009", "sha256": prior.source("src/clinicai/services/bao_cao_cuoi_ngay_service.py")[1]},
                {"path": "src/clinicai/events/consumers/so_no.py", "lines": "93-110", "sha256": prior.source("src/clinicai/events/consumers/so_no.py")[1]},
                {"path": "src/clinicai/api/v1/routers/reports.py", "lines": "150-229", "sha256": prior.source("src/clinicai/api/v1/routers/reports.py")[1]},
                {"path": "src/clinicai/services/chot_so_ca_service.py", "lines": "7-13", "sha256": prior.source("src/clinicai/services/chot_so_ca_service.py")[1]},
                {"path": "src/clinicai/services/quay_thu_service.py", "lines": "1207-1250,628-650", "sha256": prior.source("src/clinicai/services/quay_thu_service.py")[1]},
                {"path": "src/dashboard/app/(dashboard)/thu-ngan/LichSuThu.tsx", "lines": "241-244", "sha256": prior.source("src/dashboard/app/(dashboard)/thu-ngan/LichSuThu.tsx")[1]},
            ],
            "not_promoted_reason": "A completed cash refund could be reported by either request date or payment-confirmation date depending on the approved accounting policy; do not label either choice incorrect before that policy is specified.",
            "next": "Owner decides whether daily reports use request date, completion date, or separate pending/completed columns. Then align report, refund history, debt ledger, close-shift totals and two-day boundary tests.",
        },
    ]
    for item in held_candidates:
        if item["id"] not in held_by_id:
            held.append(item)
            held_by_id[item["id"]] = item

    # Add full-file reads and exact targeted ranges to the path ledger.
    full_reads = {
        "src/clinicai/services/clinic_policy.py": "Full 199-line read in round 21; broad fallback behavior held because writes remain DB-guarded and the active dashboard call has no doctor/date parameters.",
        "src/clinicai/services/dinh_chinh_don.py": "Full 1005-line read in round 21; no independent defect promoted from this file-only slice.",
    }
    extra_ranges = [
        ("src/clinicai/services/clinic_policy.py", 1, 199, "Full-file read; inspect validation and broad exception fallbacks."),
        ("src/clinicai/services/dinh_chinh_don.py", 1, 1005, "Full-file read; prescription correction, snapshots, locking, provenance, catalog and permission gates."),
        ("src/clinicai/api/v1/routers/booking.py", 634, 720, "Policy endpoint can resolve doctor/date; targeted trace."),
        ("src/clinicai/services/booking_service.py", 576, 676, "Booking transaction and effective policy use; targeted trace."),
        ("src/tests/unit/test_clinic_policy.py", 70, 143, "Policy validation tests inspected; resolver/query-exception path absent in this range."),
        ("src/dashboard/lib/booking-policy.ts", 85, 130, "Client policy loader and no-local-default contract; targeted trace."),
        ("supabase/tests/tenant_scoped_rls.sql", 1, 220, "Tenant test suite was inspected by agent; no role/capability assertion on patient was found in referenced test."),
        ("src/dashboard/tests/phan-hoi-thuoc-cot-boundary.test.mts", 81, 92, "UI boundary test inspected, no refresh-failure assertion."),
        ("src/tests/services/test_phan_hoi_thuoc_db.py", 75, 139, "DB service test inspected; successful read/write paths only."),
        ("src/clinicai/services/phan_hoi_thuoc_service.py", 34, 38, "Picker cap constant."),
        ("src/clinicai/services/phan_hoi_thuoc_service.py", 103, 146, "Eligible visit query has LIMIT 20 and response lacks pagination."),
        ("src/dashboard/app/(dashboard)/_lam-viec/PhanHoiThuocKhach.tsx", 167, 185, "Picker renders received visits without an overflow marker."),
        ("src/tests/services/test_bao_cao_cuoi_ngay_db.py", 1, 220, "Refund-by-date tests inspected; did not cover request/completion on separate days."),
        ("src/tests/unit/test_bao_cao_cuoi_ngay.py", 1, 200, "Unit report cases use timestamps but do not exercise a cross-day refund confirmation."),
    ]
    for item in new_stale_refs:
        extra_ranges.append((item["path"], item["line"], item["end_line"], item["detail"]))
    for ref in new["main_validation"]["evidence"]:
        extra_ranges.append((ref["path"], ref["line"], ref["end_line"], ref["detail"]))
    for item in held_candidates:
        for source_item in item["evidence"]:
            range_text = source_item["lines"].split(",")
            # Coverage is descriptive; record single-line ranges as targeted where exact
            # ranges are known, and keep multi-ranges in held evidence itself.
            first = range_text[0].split("-")
            start = int(first[0])
            end = int(first[1]) if len(first) > 1 else start
            extra_ranges.append((source_item["path"], start, end, f"Held observation {item['id']}; see STATE.json for all ranges and limits."))

    all_ranges: dict[str, list[tuple[int, int, str]]] = {}
    for item in [new, stale]:
        for source_item in item["main_validation"]["evidence"]:
            all_ranges.setdefault(source_item["path"], []).append(
                (source_item["line"], source_item["end_line"], source_item.get("detail", "Previously recorded pinned-main evidence."))
            )
    for path, start, end, detail in extra_ranges:
        all_ranges.setdefault(path, []).append((start, end, detail))

    rank = {"inventoried": 0, "scanned": 1, "traced": 2, "read": 3, "excluded": 4}
    coverage_files = []
    for path, spans in sorted(all_ranges.items()):
        if path not in by_path:
            raise SystemExit(f"Reviewed path missing from ledger: {path}")
        lines, digest = prior.source(path)
        row = by_path[path]
        if row["sha256"] != digest or row["lines"] != len(lines):
            raise SystemExit(f"Main ledger fingerprint mismatch: {path}")
        old = row["status"]
        status = "read" if path in full_reads else (
            "traced" if rank[old] < rank["traced"] else old
        )
        row["status"] = status
        mode = "full_file_read" if path in full_reads else "targeted_semantic_trace"
        row["method"] = f"{row.get('method', '')} | Round 21 {mode}: " + "; ".join(
            f"{start}-{end}" for start, end, _ in spans
        )
        coverage_files.append({
            "path": path,
            "status": status,
            "prior_status": old,
            "read_level_this_round": mode,
            "full_file_read_this_round": path in full_reads,
            "ranges": [{"start": start, "end": end, "purpose": purpose} for start, end, purpose in spans],
            "sha256": digest,
            "line_count": len(lines),
        })

    # Add security finding after exact source evidence exists.
    findings.append(new)
    write_json("PHAT-HIEN.json", findings)
    write_json("blocks/round21_findings.json", [new])
    write_json("blocks/round21_coverage.json", {
        "schema_version": 1,
        "audit": "round21_patient_postgrest_dashboard_contracts_finance_policy_and_clinical_read",
        "snapshot": {"path": str(SNAPSHOT), "sha": PINNED_SHA},
        "review_mode": "static_read_only_exact_main_cross_layer_trace",
        "scope": [
            "patient-table grants, tenant RLS, Supabase login and public PostgREST gateway",
            "patient feedback refresh error state and eligible-visit picker contract",
            "refund request/completion date semantics across daily report, debt ledger and UI",
            "clinic booking-policy exception fallback",
            "full prescription-amendment service semantics",
        ],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "Two root full-file reads and exact targeted traces by three read-only specialist slices. Related tests were inspected, not run. No PostgREST request, disposable DB, production, secret or patient record was accessed. The refund date basis and list-cap candidates remain policy/threshold-dependent observations.",
        "held_observations": [item["id"] for item in held_candidates] + ["CLINIC-POLICY-001"],
        "files": coverage_files,
    })
    write_json("MAIN-PHAM-VI.json", manifest)

    checks = read_json("KIEM-CHUNG.json")
    known = {(row["id"], row["path"]) for row in checks["checks"]}
    for finding in [new, stale]:
        for item in finding["main_validation"]["evidence"]:
            key = (finding["id"], item["path"])
            if key not in known:
                checks["checks"].append({"id": finding["id"], "path": item["path"], "valid": True})
                known.add(key)
    write_json("KIEM-CHUNG.json", checks)

    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    severity = Counter(row["severity"] for row in findings)
    levels = Counter(row["evidence_level"] for row in findings)
    main_status = Counter(row["main_validation"]["status"] for row in findings)
    state["held_observations"] = held
    state["updated_at"] = now
    state["phase"] = "round21_patient_postgrest_dashboard_finance_and_prescription_checkpoint"
    state["next_action"] = (
        "Continue exact-main semantic review: fresh-migration RLS/grant matrices, remaining patient and clinical API callers, "
        "provider/event retry and recovery paths, and other scanned/inventoried source. Then run bounded synthetic tests for "
        "SEC-029 and highest-risk conditional findings on disposable services only. Full source audit remains incomplete."
    )
    state["report_status"] = "v0.42_pending_report_QA; full source audit incomplete"
    state["summary"]["findings"] = len(findings)
    state["summary"]["severity"] = {key: severity.get(key, 0) for key in ("HIGH", "MEDIUM", "LOW")}
    state["summary"]["evidence_levels"] = {key: levels.get(key, 0) for key in ("reproduced_local", "design_gap", "confirmed_static", "hypothesis")}
    state["summary"]["main_status"] = {key: main_status.get(key, 0) for key in ("still_present_on_main", "partially_addressed_on_main", "addressed_on_main")}
    state["summary"]["main_coverage"] = {key: counts.get(key, 0) for key in ("inventoried", "read", "traced", "scanned", "excluded")}
    state["summary"]["main_read_files"] = counts["read"]
    state["summary"]["main_partial_traces"] = counts["traced"]
    state["summary"]["code_like_source_files"] = {
        "definition": "Pinned-tree paths with common source-code/web/sql/shell suffixes; includes app, tests, tooling and styles, not only runtime code.",
        "total": len(code_files),
        "coverage": {key: code_counts.get(key, 0) for key in ("inventoried", "traced", "scanned", "read")},
        "traced_is_partial": True,
    }
    state["summary"]["reviewed_slice_v042"] = (
        "Round 21 adds SEC-029 (patient direct PostgREST row/column boundary, MEDIUM) and consolidates the patient-feedback stale-refresh case into FE-002. "
        "A 20-visit medicine-feedback picker cap and refund accounting-date semantics remain held. Root fully read clinic_policy.py and dinh_chinh_don.py; "
        "three specialist slices reviewed dashboard contracts, patient/RLS and finance. No ClinicAI test or runtime request ran."
    )
    state["summary"]["new_findings_v042"] = ["SEC-029"]
    state.setdefault("blocks", {})["round21_patient_postgrest_dashboard_finance_and_prescription"] = {
        "status": "round21 static review integrated; 1 MEDIUM finding, FE-002 evidence expanded, 2 policy/threshold candidates held",
        "scope": "Patient table PostgREST/RLS, dashboard medicine-feedback UI contracts, refund accounting-date semantics, clinic policy fallback, prescription amendment service",
        "artifacts": "blocks/round21-summary.md; blocks/round21_findings.json; blocks/round21_coverage.json; integrate_round21.py",
        "findings": "SEC-029 MEDIUM still present on exact-main; FE-002 expanded with a second stale refresh screen.",
        "next": "Test direct PostgREST permissions using disposable Supabase auth and decide accounting-date policy before promoting the refund report observation.",
    }
    state["artifacts"]["integration_script"] = "integrate_round21.py; round21 evidence/coverage in blocks/round21_*; earlier checkpoints retained."
    state["artifacts"]["qa"] = "Pending v0.42 report structural/evidence, browser and portable-package QA; application behavior not validated."
    state["artifacts"]["bundle_integrity"] = "Pending v0.42 audit-only package rebuild and verification."
    state["artifacts"]["html_sha256"] = "pending v0.42 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.42 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.42 package verification"
    state.setdefault("runtime_summary", {})["round21"] = (
        "Static exact-main review only; no ClinicAI application/DB/PostgREST/provider/production test, secrets or patient records."
    )
    write_json("STATE.json", state)

    print(json.dumps({
        "new_findings": ["SEC-029"],
        "total_findings": len(findings),
        "severity": dict(severity),
        "main_status": dict(main_status),
        "coverage": dict(counts),
        "code_like_total": len(code_files),
        "code_like_coverage": dict(code_counts),
        "round21_reviewed_paths": len(coverage_files),
        "round21_full_reads": len(full_reads),
        "updated_at": now,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
