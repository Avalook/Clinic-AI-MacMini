"""Integrate round-22 RLS and service-order evidence on immutable exact main.

This script writes only audit artifacts. It does not alter application source,
migrations, test code, databases, or deployment state.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import integrate_round21 as r21

ROOT = Path(__file__).resolve().parent
SNAPSHOT = r21.SNAPSHOT
PINNED_SHA = r21.PINNED_SHA
prior = r21.prior
CODE_SUFFIXES = prior.CODE_SUFFIXES


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def ev(path: str, start: int, end: int, detail: str) -> dict:
    return prior.evidence((path, start, end, detail))


def main() -> None:
    actual = subprocess.check_output(
        ["git", "-C", str(SNAPSHOT), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != PINNED_SHA:
        raise SystemExit(f"Pinned source mismatch: expected {PINNED_SHA}, got {actual}")

    manifest = read_json("MAIN-PHAM-VI.json")
    if manifest["sha"] != PINNED_SHA:
        raise SystemExit("MAIN-PHAM-VI.json does not reference pinned main")
    by_path = {row["path"]: row for row in manifest["files"]}
    findings = read_json("PHAT-HIEN.json")
    by_id = {row["id"]: row for row in findings}
    if "SEC-030" in by_id:
        raise SystemExit("SEC-030 already exists; refusing duplicate integration")

    limits = (
        "Static exact-main migration and API trace only. No PostgREST request/JWT, ClinicAI app test, "
        "DB runtime, production, secret or patient record was used in this round. The migrations "
        "document a clinic-wide operational read need for some front-desk/cashier/reconciliation "
        "flows; role and roster policy therefore needs an explicit product decision before tightening."
    )
    payment = prior.finding(
        id="SEC-030",
        title="PostgREST đọc dữ liệu thu tiền vượt phạm vi ca trực của API",
        severity="MEDIUM",
        level="confirmed_static",
        category="financial_postgrest_scope",
        summary=(
            "Các bảng payment, payment_cycle, payment_bill_line, payment_refund và các bảng phân bổ/"
            "chứng từ liên quan cho phép authenticated SELECT với RLS chủ yếu lọc clinic_id; không có "
            "predicate capability, roster, ca hoặc actor như các route nghiệp vụ. Dữ liệu có số tiền, "
            "phương thức, trạng thái, người thu/xác nhận, lý do hoàn, dòng hóa đơn và metadata chứng từ "
            "chuyển khoản. Đây là đường đọc trực tiếp qua PostgREST khác với scope của endpoint thu ngân."
        ),
        trigger=(
            "Một tài khoản authenticated trong clinic gọi trực tiếp /rest/v1/ trên các bảng thanh toán "
            "ngoài ngày, ca, loại nghiệp vụ hoặc phạm vi actor mà route thu ngân cho tài khoản đó."
        ),
        impact=(
            "Cấu hình tĩnh cho phép đọc hàng tài chính cùng clinic rộng hơn guard của một số endpoint: "
            "lịch sử API giới hạn theo ngày/loại/roster/ca/actor, còn RLS bảng gốc chỉ giới hạn clinic. "
            "Một migration cũ chủ ý đọc payment clinic-wide cho quầy và đối soát; chưa có chính sách "
            "được xác nhận rằng mọi vai và mọi ca đều cần phạm vi đó. Không có bằng chứng cross-clinic, "
            "request thực tế, tải file chứng từ hoặc dữ liệu đã bị đọc."
        ),
        recommendation=(
            "Chốt ma trận role × capability × loại thanh toán × ca/roster × ngày. Thu hồi SELECT bảng "
            "gốc khỏi client nếu không cần; nếu cần, cung cấp projection/API giới hạn theo nghiệp vụ và "
            "metadata tối thiểu. Tách quyền xem chứng từ khỏi metadata bảng; giữ ngoại lệ clinic-wide "
            "chỉ cho vai đối soát đã được duyệt và có audit."
        ),
        acceptance=(
            "Trên Supabase disposable chạy đúng migrations, dùng JWT tổng hợp cho các vai Reception, "
            "Cashier, Management và một vai không thu ngân. So sánh direct PostgREST với endpoint lịch "
            "sử dụng cùng clinic, ngày, ca, roster, actor và loại; vai không được cấp không đọc hàng "
            "hoặc metadata ngoài phạm vi. Đối soát clinic-wide chỉ hoạt động cho vai/purpose đã duyệt; "
            "cross-clinic luôn bị chặn."
        ),
        note=(
            "Exact-main static chain: RLS/grant authenticated trên bảng thanh toán theo clinic; "
            "CashierScopeService giới hạn route lịch sử theo kind/date/approved roster/location/shift/actor. "
            "Migration role-scoped cũ ghi rõ một số quầy/đối soát cần payment clinic-wide, nên đây là "
            "chênh lệch scope cần policy owner chốt, không khẳng định mọi SELECT clinic-wide đều trái nghiệp vụ. "
            "Không kiểm PostgREST/JWT runtime."
        ),
        refs=[
            ("supabase/migrations/20260730000004_tenant_scoped_rls.sql", 152, 168,
             "Bảng payment nhận policy authenticated chỉ lọc clinic_id qua current_clinic_ids."),
            ("supabase/migrations/20260730000003_multi_tenant_foundation.sql", 235, 246,
             "current_clinic_ids lọc membership active, không lọc role/capability."),
            ("supabase/migrations/20260730000008_table_grants.sql", 47, 59,
             "Dynamic grant SELECT authenticated trên public tables có read policy."),
            ("supabase/migrations/20260714000001_baseline_schema.sql", 744, 758,
             "Payment lưu visit/patient/kind/status/amount/paid_by/paid_at."),
            ("supabase/migrations/20260919000002_tien_thuoc_cp2_payment_cycle.sql", 21, 46,
             "Payment cycle chứa số tiền, visit, kind, phương thức/trạng thái, creator/confirmer và thời điểm."),
            ("supabase/migrations/20260919000002_tien_thuoc_cp2_payment_cycle.sql", 246, 252,
             "Payment cycle bật RLS và grant SELECT cho authenticated theo clinic."),
            ("supabase/migrations/20260919000001_tien_thuoc_cp1_hoa_don.sql", 85, 110,
             "Bill-line snapshot lưu dịch vụ/thuốc, số lượng, đơn giá và tổng tiền."),
            ("supabase/migrations/20260919000001_tien_thuoc_cp1_hoa_don.sql", 127, 136,
             "Bill line bật RLS và grant SELECT authenticated theo clinic."),
            ("supabase/migrations/20260919000004_tien_thuoc_cp5_hoan_tra.sql", 41, 69,
             "Refund/return lưu tiền, trạng thái, lý do, người tạo/xác nhận và thời điểm."),
            ("supabase/migrations/20260919000004_tien_thuoc_cp5_hoan_tra.sql", 542, 557,
             "Các bảng refund/return có RLS và grant đọc cùng clinic."),
            ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 43, 50,
             "Phần thanh toán lưu số tiền và khách đưa theo hình thức."),
            ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 224, 258,
             "Metadata ảnh chuyển khoản gồm key, MIME, hash/size, actor và lifecycle; không chứng minh tải được file."),
            ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 267, 272,
             "Bảng metadata ảnh chuyển khoản grant SELECT authenticated theo clinic."),
            ("src/clinicai/api/v1/routers/cashier.py", 129, 159,
             "Route lịch sử thu gọi CashierScopeService và truyền giới hạn ngày/actor."),
            ("src/clinicai/services/cashier_scope_service.py", 349, 422,
             "Guard áp kind, ngày, approved roster, location/shift, active shift và actor."),
            ("src/clinicai/permissions/catalogue.py", 373, 378,
             "Capability thu dịch vụ riêng biệt."),
            ("src/clinicai/permissions/catalogue.py", 519, 524,
             "Capability thu thuốc riêng biệt."),
            ("supabase/migrations/20260923000003_capability.sql", 151, 169,
             "Preset vai có capability thu khác nhau."),
            ("supabase/migrations/20260730000013_role_scoped_clinical_read.sql", 19, 26,
             "Comment migration nói front desk/cashier/đối soát cần đọc payment clinic-wide."),
            ("caddy/Caddyfile", 191, 194,
             "Caddy route /rest/v1/* vào Supabase gateway."),
            ("src/tests/services/test_cashier_scope_db.py", 18, 63,
             "Test được đọc, không chạy: cashier scope phụ thuộc ngày/ca/roster và bị thu hồi khi roster rejected."),
            ("supabase/tests/role_scoped_clinical_read.sql", 174, 201,
             "Test được đọc, không chạy: operational payment rows được giữ clinic-wide; chưa assert boundary theo role/ca."),
        ],
        tests=[
            "src/tests/services/test_cashier_scope_db.py:18-63 — đã đọc, không chạy; kiểm scope route theo roster/ca.",
            "supabase/tests/role_scoped_clinical_read.sql:174-201 — đã đọc, không chạy; chưa kiểm direct PostgREST role/roster scope.",
        ],
        related=[
            {"id": "SEC-029", "relationship": "Cùng kênh PostgREST authenticated nhưng SEC-029 là PII bệnh nhân; SEC-030 là dữ liệu tài chính và scope ca/actor."},
            {"id": "SEC-018", "relationship": "SEC-018 là dữ liệu liên hệ/thân nhân; không bao gồm payment rows hoặc scope cashier."},
        ],
        result=(
            "Đã đối chiếu grants/policies trên payment, payment cycle, bill lines, refund/return và metadata "
            "chuyển khoản với cashier route scope; chưa gọi PostgREST hoặc xác nhận role thực tế qua JWT."
        ),
        limitations=limits,
    )

    # Appointment/draft/allocation are the same missing assigned-doctor invariant
    # already tracked by SEC-011, so extend that record instead of adding a duplicate.
    assigned = by_id["SEC-011"]
    extension = [
        ev("supabase/migrations/20260915000021_thu_ky_rls_theo_bac_si.sql", 84, 115,
           "Restrictive assignment policy covers 11 clinical tables but omits appointment, service_order_draft and prescription_allocation."),
        ev("supabase/migrations/20260730000004_tenant_scoped_rls.sql", 152, 168,
           "appointment remains in the generic tenant-only read policy set."),
        ev("supabase/migrations/20260915000008_service_order_draft.sql", 16, 43,
           "Draft rows expose visit, selected service codes, recorder/approver/version/state."),
        ev("supabase/migrations/20260915000008_service_order_draft.sql", 84, 102,
           "Draft SELECT is restricted to clinical roles and same clinic, not assigned doctor."),
        ev("src/clinicai/services/service_order_service.py", 263, 290,
           "Backend get_draft adds a TKYK doctor-assignment check that the raw table policy does not express."),
        ev("supabase/migrations/20260919000003_tien_thuoc_cp3_phan_lo_ban.sql", 47, 83,
           "Prescription allocation contains prescription/visit/drug/batch and dispensed quantities."),
        ev("supabase/migrations/20260919000003_tien_thuoc_cp3_phan_lo_ban.sql", 437, 445,
           "Prescription allocation receives authenticated same-clinic SELECT but no TKYK assignment predicate."),
        ev("src/clinicai/services/thu_ky_bac_si.py", 31, 61,
           "Unassigned TKYK semantics deliberately yield no doctor filter; assigned secretary maps to a doctor."),
        ev("src/clinicai/services/thu_ky_bac_si.py", 76, 100,
           "Assignment helper derives customer/doctor association from appointments, visits and ultrasound records."),
        ev("supabase/tests/thu_ky_rls_theo_bac_si.sql", 59, 104,
           "Existing SQL test covers visit/clinical_record assignment but omits appointment, draft and allocation."),
    ]
    assigned["summary"] += (
        " Round 22 bổ sung đường PostgREST: restrictive TKYK assignment policy hiện áp trên 11 bảng "
        "lâm sàng nhưng không áp lên appointment, service_order_draft và prescription_allocation. "
        "Trong khi API get_draft kiểm bác sĩ được phân, raw SELECT của draft chỉ kiểm role clinical + clinic."
    )
    assigned["trigger"] += (
        " Thêm trường hợp TKYK đã gắn bác sĩ gọi trực tiếp PostgREST trên appointment/nháp/dữ liệu phân lô "
        "cùng clinic của bác sĩ khác; các bảng này không có restrictive assignment predicate tương ứng."
    )
    assigned["impact"] += (
        " Raw table path có thể để lộ lịch hẹn hoặc nháp chỉ định/dữ liệu phân lô ngoài bác sĩ được phân; "
        "đây là cùng invariant thiếu assignment đã được ghi ở SEC-011, không tạo finding riêng. Chưa kiểm JWT/runtime."
    )
    assigned["recommendation"] += (
        " Áp cùng invariant doctor-assignment vào mọi đường PostgREST có clinical/appointment data; hoặc bỏ raw "
        "SELECT và buộc đọc qua API có guard. Bổ sung test cho appointment, service_order_draft và prescription_allocation."
    )
    assigned["acceptance"] += (
        " Với JWT TKYK được phân cho bác sĩ A, PostgREST không trả appointment, draft hoặc allocation của bác sĩ B "
        "trong cùng clinic; A đọc được hàng thuộc scope đã phân; role chưa gán giữ đúng no-filter/product policy đã duyệt."
    )
    assigned["validation"]["result"] += (
        " Round 22 đối chiếu restrictive policy 11 bảng với grant/policy appointment, draft, allocation và API draft; "
        "test RLS hiện có chỉ exercise visit/clinical_record, chưa chạy test mới."
    )
    assigned["validation"]["limitations"] += (
        " Round 22 chưa chạy PostgREST/JWT hoặc fixture hai bác sĩ; kết luận tĩnh trong cùng clinic."
    )
    assigned["main_validation"]["note"] += (
        " Round 22 mở rộng cùng lỗ hổng assignment sang direct PostgREST appointment/draft/allocation; đây là extension SEC-011."
    )
    assigned["related_tests"] = list(dict.fromkeys(assigned.get("related_tests", []) + [
        "supabase/tests/thu_ky_rls_theo_bac_si.sql:59-104 — đã đọc, không chạy; chỉ kiểm visit và clinical_record, chưa bao phủ appointment/draft/allocation.",
    ]))
    known_ranges = {(x["path"], x["line"], x["end_line"]) for x in assigned["main_validation"]["evidence"]}
    for item in extension:
        key = (item["path"], item["line"], item["end_line"])
        if key not in known_ranges:
            assigned["main_validation"]["evidence"].append(item)
            assigned["evidence"].append({k: item[k] for k in ("path", "line", "end_line", "detail")})
            assigned["source_hashes"][item["path"]] = item["sha256"]
            known_ranges.add(key)

    state = read_json("STATE.json")
    held = state.get("held_observations", [])
    held_by_id = {item.get("id"): item for item in held}
    service_order = {
        "id": "SERVICE-ORDER-LEGACY-READ-API-001",
        "classification": "held_legacy_api_contract_mismatch_no_current_dashboard_caller",
        "severity_assessment": "LOW/P3; the old FastAPI read contracts are statically inconsistent with current canonical writes, but no current TSX caller was found and the dashboard BFF route is disabled.",
        "snapshot_sha": PINNED_SHA,
        "trigger": "An internal client calls a legacy service-order GET endpoint for an order/draft written through the canonical service_order lifecycle.",
        "impact": "The legacy read path may return missing/stale rows because it queries work_item.payload or service_order_draft. Current dashboard BFF paths are marked disabled/410, Caddy does not expose the API publicly, and no direct TSX caller was found; present customer impact is therefore unproven.",
        "evidence": [
            {"path": "src/clinicai/services/service_order_service.py", "lines": "85-120,263-321,553-574", "sha256": prior.source("src/clinicai/services/service_order_service.py")[1]},
            {"path": "src/clinicai/api/v1/routers/work_items.py", "lines": "482-493,553-566,642-660", "sha256": prior.source("src/clinicai/api/v1/routers/work_items.py")[1]},
            {"path": "src/clinicai/services/chi_dinh_service.py", "lines": "135-301", "sha256": prior.source("src/clinicai/services/chi_dinh_service.py")[1]},
            {"path": "src/clinicai/services/luot_kham_service.py", "lines": "2178-2244", "sha256": prior.source("src/clinicai/services/luot_kham_service.py")[1]},
            {"path": "src/dashboard/lib/route-da-tat.ts", "lines": "1-24", "sha256": prior.source("src/dashboard/lib/route-da-tat.ts")[1]},
            {"path": "caddy/Caddyfile", "lines": "198-201", "sha256": prior.source("caddy/Caddyfile")[1]},
        ],
        "not_promoted_reason": "No current dashboard caller found; BFF routes are intentionally disabled and no public Caddy API route exists. The code contract mismatch alone does not prove active user impact.",
        "next": "Either retire these internal legacy GET endpoints with an explicit 410/deprecation contract, or read from canonical service_order and add an API contract test covering orders created by both current writers.",
    }
    if service_order["id"] not in held_by_id:
        held.append(service_order)

    full_reads = {
        "src/clinicai/services/service_selection_service.py": "Full 659-line read in round 22; confirmation, revision, exact decision-set and financial locks traced; no stale write promoted.",
        "src/clinicai/events/worker.py": "Full 328-line read in round 22; lease/retry/consumer dispatch, no new candidate beyond existing INF findings.",
        "src/clinicai/services/notification_relay.py": "Full 269-line read in round 22; retry/channel semantics checked against existing findings.",
        "src/clinicai/services/providers/zalo.py": "Full 222-line read in round 22; timeout/unknown outcome checked against existing INF-024.",
        "src/clinicai/services/providers/telegram.py": "Full 82-line read in round 22; dynamic HTML issue already tracked in INF-025.",
        "src/clinicai/services/pos_outbox.py": "Full 87-line read in round 22; dead-letter recovery remains INF-011.",
        "src/clinicai/services/pos_relay.py": "Full 262-line read in round 22; advisory locks, retry and null adapter checked; no new issue.",
        "src/clinicai/events/hen_gio.py": "Full 266-line read in round 22; lease/retry/alert paths compared with INF-005/018/022.",
        "src/clinicai/worker.py": "Full 483-line read in round 22; queue and worker failure paths compared with INF-004/config observations.",
        "src/clinicai/services/event_service.py": "Full 146-line read in round 22; generic publisher caller/wiring checked; no new finding.",
        "src/clinicai/events/phat_lai.py": "Full 141-line read in round 22; replay/projection transaction checked; no new finding.",
        "src/clinicai/api/v1/routers/events.py": "Full 76-line read in round 22; SSE/event API inspected; no additional finding.",
        "src/clinicai/events/consumers/dong_thoi_gian.py": "Full 247-line read in round 22; event-id projection upsert/replay reviewed.",
        "src/clinicai/services/service_order_service.py": "Full 868-line read by a read-only specialist in round 22; legacy read/source-of-truth mismatch held, not promoted.",
    }
    ranges = [
        ("src/dashboard/app/(dashboard)/thu-ngan/ChonDichVu.tsx", 1, 300, "Selection drawer sends order-id set and revision."),
        ("src/clinicai/services/chi_dinh_service.py", 135, 301, "Current order writer uses canonical service_order."),
        ("src/clinicai/services/chi_dinh_service.py", 372, 503, "Carry-over locks visit and updates order lifecycle."),
        ("src/clinicai/services/luot_kham_service.py", 2178, 2244, "Visit workflow writes canonical service_order."),
        ("src/clinicai/api/v1/routers/work_items.py", 482, 493, "Legacy GET order endpoint reads the old service path."),
        ("src/clinicai/api/v1/routers/work_items.py", 553, 566, "Legacy GET draft endpoint remains in FastAPI."),
        ("src/clinicai/api/v1/routers/work_items.py", 642, 660, "Legacy GET order list remains in FastAPI."),
        ("supabase/migrations/20260801000002_order_services.sql", 177, 205, "Historical duplicate query reads work_item payload."),
        ("src/dashboard/lib/route-da-tat.ts", 1, 24, "Service-order BFF routes are explicitly disabled."),
        ("caddy/Caddyfile", 191, 201, "PostgREST routes to gateway; remaining paths route to dashboard, not public API."),
        ("supabase/migrations/20260730000004_tenant_scoped_rls.sql", 149, 168, "Generic tenant-only policy for selected operational tables."),
        ("supabase/migrations/20260730000008_table_grants.sql", 47, 59, "Authenticated SELECT grant loop for tables with read policy."),
        ("supabase/migrations/20260714000001_baseline_schema.sql", 313, 343, "Appointment rows contain patient/doctor/slot/status context."),
        ("supabase/migrations/20260915000021_thu_ky_rls_theo_bac_si.sql", 84, 115, "Restrictive TKYK doctor assignment policy covers a finite table list."),
        ("src/clinicai/api/v1/routers/cashier.py", 129, 159, "Cashier history route applies scope before fetching data."),
        ("src/clinicai/services/cashier_scope_service.py", 349, 422, "Cashier history scope includes date/kind/roster/shift/actor."),
        ("src/tests/services/test_cashier_scope_db.py", 18, 63, "Read-only inspection of existing cashier scope tests; not run."),
        ("supabase/tests/role_scoped_clinical_read.sql", 174, 201, "Read-only inspection of operational payment SELECT assertions; not run."),
        ("supabase/tests/thu_ky_rls_theo_bac_si.sql", 59, 104, "Read-only inspection of assigned secretary RLS tests; not run."),
        ("supabase/migrations/20260730000013_role_scoped_clinical_read.sql", 19, 26, "Historical comment records clinic-wide operational payment read intent."),
    ]

    all_ranges: dict[str, list[tuple[int, int, str]]] = {}
    for item in payment["main_validation"]["evidence"] + extension:
        all_ranges.setdefault(item["path"], []).append((item["line"], item["end_line"], item["detail"]))
    for path, note in full_reads.items():
        lines, digest = prior.source(path)
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
        row["method"] = f"{row.get('method', '')} | Round 22 {mode}: " + "; ".join(
            f"{start}-{end}" for start, end, _ in spans
        )
        coverage_files.append({
            "path": path,
            "status": status,
            "prior_status": old,
            "read_level_this_round": mode,
            "full_file_read_this_round": is_full,
            "ranges": [{"start": start, "end": end, "purpose": purpose} for start, end, purpose in spans],
            "sha256": digest,
            "line_count": len(lines),
        })

    findings.append(payment)
    write_json("PHAT-HIEN.json", findings)
    write_json("blocks/round22_findings.json", [payment])
    write_json("blocks/round22_finding_extensions.json", [assigned])
    write_json("blocks/round22_coverage.json", {
        "schema_version": 1,
        "audit": "round22_payment_postgrest_tkyk_assignment_service_order_and_event_recovery",
        "snapshot": {"path": str(SNAPSHOT), "sha": PINNED_SHA},
        "review_mode": "static_read_only_exact_main_cross_layer_trace",
        "scope": [
            "payment and refund PostgREST grants versus cashier API role/roster/shift scope",
            "TKYK assigned-doctor RLS across appointment, service-order drafts and prescription allocations",
            "service-order read/write source-of-truth and disabled dashboard BFF callers",
            "selection revision/order-set concurrency and carry-over locks",
            "event worker, notification providers, POS relay/outbox and replay/recovery paths",
        ],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "One MEDIUM finding was added for financial PostgREST scope; SEC-011 was extended with the same missing TKYK assignment invariant rather than duplicated. Legacy service-order API mismatch remains held because no current dashboard caller was found and BFF routes are disabled. Related tests were read but not run. No application/runtime/database/PostgREST/provider/production test or patient data was used.",
        "held_observations": [service_order["id"]],
        "files": coverage_files,
    })
    write_json("MAIN-PHAM-VI.json", manifest)

    checks = read_json("KIEM-CHUNG.json")
    checked = {(row["id"], row["path"]) for row in checks["checks"]}
    for finding in (payment, assigned):
        for item in finding["main_validation"]["evidence"]:
            key = (finding["id"], item["path"])
            if key not in checked:
                checks["checks"].append({"id": finding["id"], "path": item["path"], "valid": True})
                checked.add(key)
    write_json("KIEM-CHUNG.json", checks)

    state["held_observations"] = held
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    severity = Counter(row["severity"] for row in findings)
    levels = Counter(row["evidence_level"] for row in findings)
    main_status = Counter(row["main_validation"]["status"] for row in findings)
    state["updated_at"] = now
    state["phase"] = "round22_postgrest_finance_tkyk_assignment_events_and_service_order_checkpoint"
    state["report_version"] = "v0.43"
    state["report_round_summary"] = (
        "Round 22 thêm SEC-030 về phạm vi đọc bảng thanh toán PostgREST; mở rộng SEC-011 sang appointment, "
        "service_order_draft và prescription_allocation. Đã đọc trọn 14 service/worker/provider files trong lát này; "
        "một API đọc service-order cũ được giữ ở observation do chưa thấy caller dashboard và BFF đã tắt. "
        "Không chạy ClinicAI app test, DB, PostgREST, provider hoặc production; chỉ QA report sau khi dựng."
    )
    state["next_action"] = (
        "Continue exact-main semantic review of remaining clinical-form/patient API callers, pharmacy lifecycle and unread scanned/inventoried source. "
        "On disposable Supabase from pinned migrations, test SEC-029/SEC-030 direct PostgREST role scope and SEC-011 assigned-secretary boundaries; "
        "decide clinic-wide cashier read policy with product/accounting owners. Then add synthetic event/provider failure tests. Full source audit remains incomplete."
    )
    state["report_status"] = "v0.43_pending_report_QA; full source audit incomplete"
    state.setdefault("summary", {})["findings"] = len(findings)
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
    state["summary"]["reviewed_slice_v043"] = (
        "Round 22 adds SEC-030 and extends SEC-011 with direct PostgREST assignment evidence. "
        "The event/provider slice reproduced no new finding beyond existing INF records. "
        "Legacy service-order read APIs remain a held contract observation because active dashboard use was not found."
    )
    state["summary"]["new_findings_v043"] = ["SEC-030"]
    state.setdefault("blocks", {})["round22_postgrest_finance_tkyk_assignment_events_and_service_order"] = {
        "status": "round22 static review integrated; 1 MEDIUM added, SEC-011 extended, 1 legacy API contract observation held",
        "scope": "PostgREST payments and TKYK assignment; service-order read/write contracts; event/provider/worker recovery paths",
        "artifacts": "blocks/round22-summary.md; blocks/round22_findings.json; blocks/round22_finding_extensions.json; blocks/round22_coverage.json; integrate_round22.py",
        "findings": "SEC-030 MEDIUM still present on pinned main; SEC-011 extended with appointment, draft and allocation PostgREST paths.",
        "next": "Continue clinical forms and pharmacy lifecycle; test direct PostgREST boundaries on a disposable stack and settle clinic-wide payment read policy.",
    }
    state["artifacts"]["integration_script"] = "integrate_round22.py; round22 evidence/coverage in blocks/round22_*; earlier checkpoints retained."
    state["artifacts"]["qa"] = "Pending v0.43 structural/evidence, browser and portable-package QA; application behavior not validated in round 22."
    state["artifacts"]["bundle_integrity"] = "Pending v0.43 audit-only package rebuild and verification."
    state["artifacts"]["html_sha256"] = "pending v0.43 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.43 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.43 package verification"
    state.setdefault("runtime_summary", {})["round22"] = (
        "Static exact-main review only; no ClinicAI application/DB/PostgREST/provider/production test, secrets or patient records."
    )
    write_json("STATE.json", state)

    print(json.dumps({
        "added_findings": ["SEC-030"],
        "extended_findings": ["SEC-011"],
        "held_observations": [service_order["id"]],
        "total_findings": len(findings),
        "severity": dict(severity),
        "main_status": dict(main_status),
        "coverage": dict(counts),
        "code_like_total": len(code_files),
        "code_like_coverage": dict(code_counts),
        "round22_reviewed_paths": len(coverage_files),
        "round22_full_reads": len(full_reads),
        "updated_at": now,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
