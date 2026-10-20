"""Integrate a read-only exact-main authorization/tenant review into the audit."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"


def load(name: str):
    return json.loads((ROOT / name).read_text())


def save(name: str, data) -> None:
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def source(path: str) -> tuple[bytes, list[str]]:
    data = subprocess.check_output(["git", "show", f"{SHA}:{path}"], cwd=REPO)
    return data, data.decode("utf-8").splitlines()


def proof(path: str, start: int, end: int, detail: str) -> dict:
    data, lines = source(path)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid pinned range {path}:{start}-{end}")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": hashlib.sha256(data).hexdigest(),
        "excerpt": "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1)),
        "detail": detail,
        "lines": len(lines),
    }


def main() -> None:
    findings = load("PHAT-HIEN.json")
    by_id = {item["id"]: item for item in findings}
    sec = by_id["SEC-010"]

    new_specs = [
        (
            "src/clinicai/api/v1/routers/consent.py",
            36,
            47,
            "Sibling links endpoint uses get_current_identity and returns linked-partner metadata.",
        ),
        (
            "src/clinicai/services/consent_service.py",
            100,
            121,
            "Consent lookup and linked-partner lookup are scoped to identity.clinic_id plus supplied patient UUID.",
        ),
        (
            "src/clinicai/services/consent_service.py",
            140,
            185,
            "Response contains relationship, other patient ID/name/code and allowed form-code metadata in both directions.",
        ),
        (
            "supabase/migrations/20260804000020_patient_link_consent.sql",
            149,
            162,
            "RLS distinguishes clinic-wide patient_link reads from clinical-role-only consent reads.",
        ),
        (
            "supabase/migrations/20260730000013_role_scoped_clinical_read.sql",
            59,
            85,
            "The clinical read set is DOCTOR, ULTRASOUND_DOCTOR, TKYK and NURSE_ULTRASOUND; management is explicitly excluded by default.",
        ),
        (
            "src/clinicai/core/database.py",
            85,
            106,
            "The backend creates its asyncpg pool from DATABASE_URL; runtime credentials were not inspected.",
        ),
        (
            ".env.prod.example",
            41,
            41,
            "The checked-in production example uses a postgres database user; this is a template, not proof of the active secret value.",
        ),
    ]
    added = []
    for path, start, end, detail in new_specs:
        item = proof(path, start, end, detail)
        evidence = {k: item[k] for k in ("path", "line", "end_line", "detail")}
        main_evidence = {k: item[k] for k in ("path", "line", "end_line", "sha256", "excerpt")}
        if not any(
            (x["path"], x["line"], x["end_line"]) == (path, start, end)
            for x in sec["evidence"]
        ):
            sec["evidence"].append(evidence)
        if not any(
            (x["path"], x["line"], x["end_line"]) == (path, start, end)
            for x in sec["main_validation"]["evidence"]
        ):
            sec["main_validation"]["evidence"].append(main_evidence)
        sec.setdefault("source_hashes", {})[path] = item["sha256"]
        added.append(item)

    sec["title"] = "Router consent thiếu guard y khoa ở cả đường đọc form chia sẻ và metadata liên kết"
    sec["summary"] = (
        "GET /patients/{patient_id}/shared-form nhận viewing_patient_id do caller truyền; may_surface() cho phép vô điều kiện "
        "khi hai ID bằng nhau, rồi service truy vấn clinical_form_response.form_data theo clinic + patient. Route và endpoint "
        "chị em GET /patients/{patient_id}/links chỉ dùng get_current_identity (chặn DISPLAY/PARTNER, không đòi quyền y khoa). "
        "Đường /links trả quan hệ, tên/mã bệnh nhân liên kết và form_codes đã chia sẻ; riêng endpoint này không trả form_data. "
        "Migration giới hạn RLS consent cho bốn vai lâm sàng, còn API dùng asyncpg/DATABASE_URL; ví dụ cấu hình prod dùng user postgres."
    )
    sec["trigger"] = (
        "Nhân viên nội bộ không có quyền đọc lâm sàng biết/nhận được UUID bệnh nhân trong cùng clinic rồi gọi "
        "shared-form với patient_id=viewing_patient_id để đọc form; hoặc gọi /patients/{patient_id}/links để xem quan hệ và "
        "phạm vi form được chia sẻ. Dashboard hiện không có caller /links tìm thấy qua các chuỗi đã dò; UUID enumeration và "
        "đường UI thực tế chưa được xác minh."
    )
    sec["impact"] = (
        "Đường shared-form có thể trả tối đa 20 bản clinical_form_response.form_data — dữ liệu sức khỏe nhạy cảm — qua đường "
        "không đặt guard y khoa. Đường /links bổ sung lộ metadata quan hệ và phạm vi đồng ý chia sẻ, nhưng không trả nội dung "
        "phiếu. Query ở cả hai đường giữ clinic_id; không có chứng cứ đọc chéo clinic, request thật hay truy cập production. "
        "Mức tác động runtime phụ thuộc cấu hình DATABASE_URL thực tế, cấu hình này không được đọc."
    )
    sec["validation"] = {
        "method": "exact_main_static_authorization_and_dataflow_trace",
        "command": None,
        "result": (
            "Trace hai GET trong cùng consent router qua get_current_identity đến ConsentService; shared-form có nhánh same-ID "
            "dẫn tới SELECT form_data, còn /links trả metadata quan hệ/form_codes. So sánh với policy RLS clinical-only và "
            "danh sách vai lâm sàng. Dashboard grep không tìm thấy caller cho /links; test service IO kiểm tra shape metadata "
            "nhưng không kiểm guard role ở route. Một reviewer bảo mật độc lập khuyến nghị mở rộng SEC-010 thay vì tạo ID trùng."
        ),
        "limitations": (
            "Static exact-main trace; không chạy HTTP/ASGI, ClinicAI test, DB, runtime hoặc production. Không đọc giá trị "
            "DATABASE_URL thật; .env.prod.example chỉ là template. Chưa xác minh UUID discovery hoặc caller UI cho /links. "
            "Kết luận cùng clinic; /links không trả form_data; không chứng minh sự cố đã xảy ra."
        ),
    }
    sec["recommendation"] = (
        "Đặt guard y khoa hoặc capability đọc metadata consent rõ ràng tại từng entrypoint trước khi gọi service; không coi "
        "UUID do caller cung cấp là bằng chứng có quyền với bệnh nhân. Giữ kiểm tra consent giữa hai bệnh nhân tách khỏi "
        "quyền nhân viên; đồng bộ source-of-truth giữa API guard và RLS, audit actor/patient/form mà không ghi nội dung bệnh án."
    )
    sec["acceptance"] = (
        "Role không có quyền lâm sàng nhận 403 khi gọi cả shared-form và /links, kể cả khi tự đặt patient_id hoặc "
        "patient_id=viewing_patient_id; role được cấp quyền chỉ xem đúng clinic và consent còn hiệu lực. Có route-level role "
        "matrix test cho bác sĩ, lễ tân, CSKH và quản lý; kiểm revoked consent, UUID khác clinic và không ghi form_data vào audit."
    )
    sec["related_tests"] = [
        "src/tests/services/test_consent_service_io.py:294-323 — xác nhận shape metadata linked_partners; không kiểm quyền route theo vai; đã đọc, không chạy.",
        "src/tests/services/test_consent.py — pure consent semantics; đã đọc ở lát trước, không chạy.",
    ]
    sec["main_validation"]["note"] = (
        "SEC-010 vẫn hiện diện trên pinned main. Cùng consent router có hai endpoint thiếu guard y khoa: shared-form trả "
        "form_data khi caller tự đặt cùng patient UUID; /links trả metadata quan hệ và consent form_codes. Metadata route là "
        "phần mở rộng cùng ranh giới, không phải finding ID riêng. RLS ghi rõ consent chỉ dành cho bốn vai lâm sàng; mức "
        "khai thác backend phụ thuộc DATABASE_URL runtime chưa được kiểm tra."
    )
    sec["production_verified"] = False

    # Record the no-finding/dedup conclusions and exact source coverage together.
    coverage_specs = [
        *new_specs,
        ("src/tests/services/test_consent_service_io.py", 294, 323, "Service IO test returns relationship and form-code metadata; it does not exercise route role authorization and was not run."),
        ("src/clinicai/api/v1/routers/xem_luot.py", 17, 20, "Normal visit journey endpoints are available to internal staff; the table does not add a capability boundary absent from this API."),
        ("src/clinicai/api/v1/routers/xem_luot.py", 44, 54, "Per-visit journey endpoint delegates to HanhTrinhKhachService under cua_noi_bo."),
        ("src/clinicai/services/xem_luot_service.py", 176, 194, "Timeline reads the projection and returns its whitelisted chi_tiet fields for the selected clinic/visit."),
        ("src/clinicai/api/v1/routers/ops.py", 189, 202, "Operations diary is a separate ops.view route, scoped to identity.clinic_id."),
        ("src/clinicai/services/nhat_ky_van_hanh.py", 89, 114, "Operations diary reads selected label/actor fields, not chi_tiet; do not conflate it with the general visit journey."),
        ("src/clinicai/events/consumers/dong_thoi_gian.py", 30, 53, "Projection uses an event-specific field whitelist."),
        ("src/clinicai/events/consumers/dong_thoi_gian.py", 80, 149, "Whitelist includes operational reasons, amounts and consultation result labels; contents are not arbitrary event payloads."),
        ("src/clinicai/events/consumers/dong_thoi_gian.py", 209, 246, "Consumer persists only the whitelist projection and deduplicates by event_id."),
        ("supabase/migrations/20260923000002_projection_dong_thoi_gian.sql", 14, 44, "Projection has clinic-only SELECT RLS/grant. No new finding because the normal visit journey API already exposes the same projection to internal staff; runtime PostgREST was not tested."),
        ("src/dashboard/app/(dashboard)/hanh-trinh/BangHanhTrinh.tsx", 63, 92, "Dashboard loads the normal API and uses table subscriptions to refresh; no direct PostgREST row-read was found in this component."),
        ("supabase/migrations/20261014156000_hoa_don_cong_ty.sql", 14, 35, "Company invoice references are separate FKs without a composite patient/company-clinic constraint."),
        ("supabase/migrations/20261014156000_hoa_don_cong_ty.sql", 60, 68, "Migration leaves same-company/patient validation to the service."),
        ("src/clinicai/services/hoa_don_cong_ty_service.py", 214, 239, "Service validates the clinic-scoped patient before creating the company invoice."),
        ("src/clinicai/services/hoa_don_cong_ty_service.py", 374, 393, "Company selection is scoped to clinic and patient context."),
        ("src/clinicai/services/hoa_don_cong_ty_service.py", 478, 488, "Invoice update path retains the clinic/patient scope."),
        ("src/clinicai/services/hoa_don_cong_ty_service.py", 558, 579, "Finalization path checks the same clinic-scoped identities."),
        ("src/tests/services/test_hoa_don_cong_ty_db.py", 317, 330, "Test rejects a company belonging to a different patient; read only, not run. Similar to DB-007, so no new finding."),
        ("supabase/migrations/20261019110000_pharmacy_inventory_p1_guards.sql", 42, 64, "Composite request-to-inventory transaction FK retains clinic and batch scope; staff FK is global."),
        ("src/clinicai/services/pharmacy_service.py", 2640, 2712, "Inventory request writer derives staff and clinic from identity; multi-clinic staff use is not shown to be a violation."),
        ("src/clinicai/api/v1/routers/thai_ky.py", 1, 85, "Full router read: medical read guard and service-owned write permission; no new issue in this slice."),
        ("src/clinicai/services/thai_ky_service.py", 310, 318, "Service checks pregnancy write capability rather than trusting the broad identity dependency."),
        ("src/clinicai/services/thai_ky_service.py", 370, 390, "Pregnancy reads require medical access and the patient is checked within identity clinic."),
        ("src/clinicai/services/thai_ky_service.py", 392, 467, "Create path checks writer permission, clinic-scoped patient and matching clinic-scoped visit."),
        ("src/clinicai/services/thai_ky_service.py", 469, 545, "Update path checks writer permission and scopes the pregnancy row by clinic."),
        ("src/clinicai/api/v1/routers/clinical_forms.py", 1, 122, "Full router read: normal form read/write routes declare clinical capability guards; service-level coverage remains partial."),
    ]
    by_path: dict[str, dict] = {}
    for path, start, end, detail in coverage_specs:
        item = proof(path, start, end, detail)
        entry = by_path.setdefault(
            path,
            {"path": path, "sha256": item["sha256"], "lines": item["lines"], "read_ranges": [], "notes": []},
        )
        entry["read_ranges"].append({"start": start, "end": end})
        entry["notes"].append(detail)
        if entry["sha256"] != item["sha256"] or entry["lines"] != item["lines"]:
            raise AssertionError(f"Inconsistent source snapshot: {path}")

    reviewer_note = (
        "Round 42 security-reviewer: merge /links metadata into SEC-010; same router guard boundary, no SEC-036."
    )
    manifest = load("MAIN-PHAM-VI.json")
    for path, item in by_path.items():
        record = next((x for x in manifest["files"] if x["path"] == path), None)
        if record is None:
            continue
        if path == "src/tests/services/test_consent_service_io.py" and record["status"] == "scanned":
            record["status"] = "traced"
        elif path == ".env.prod.example" and record["status"] == "inventoried":
            record["status"] = "traced"
        elif path in {"src/clinicai/api/v1/routers/thai_ky.py", "src/clinicai/api/v1/routers/clinical_forms.py"} and record["status"] == "traced":
            record["status"] = "read"
            record["full_file_read"] = True
        ranges = ", ".join(f"{x['start']}–{x['end']}" for x in item["read_ranges"])
        note = f"Round 42 exact-main trace {ranges}; see blocks/round42.coverage.json."
        if note not in record.get("method", ""):
            record["method"] = (record.get("method", "") + " | " + note).strip(" |")
        if path in {".env.prod.example", "src/tests/services/test_consent_service_io.py"}:
            record["round42_note"] = reviewer_note if path == "src/tests/services/test_consent_service_io.py" else "Production sample only; active DATABASE_URL not read."
    manifest["last_updated_round"] = 42
    save("MAIN-PHAM-VI.json", manifest)

    tree_grep = {}
    for query in ("ConsentService", "/links", "linked_partners", "luot_dong_thoi_gian"):
        proc = subprocess.run(
            ["git", "grep", "-n", query, SHA, "--", "src/dashboard"],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        tree_grep[query] = {
            "exit_code": proc.returncode,
            "matches": proc.stdout.splitlines(),
            "interpretation": "No string match is not proof of no dynamically constructed caller." if proc.returncode == 1 else "Exact-main string matches recorded.",
        }

    role_proof = proof(
        "src/clinicai/api/identity.py", 638, 659,
        "Identity guard rejects DISPLAY/PARTNER only; other resolved internal roles pass.",
    )
    role_migration = proof(
        "supabase/migrations/20260730000013_role_scoped_clinical_read.sql", 59, 85,
        "Clinical RLS allow-set is limited to four medical roles; MANAGEMENT is explicitly excluded by default.",
    )
    route_guard = proof(
        "src/clinicai/api/v1/routers/consent.py", 36, 47,
        "Links endpoint depends on get_current_identity and has no clinical capability dependency.",
    )
    held_or_deduped = [
        {
            "id": "ROUND42-TIMELINE-ACCESS-001",
            "disposition": "reviewed_no_distinct_finding_after_api_scope_dedupe",
            "rationale": "The direct table grant is clinic-only, but the normal visit-journey API uses cua_noi_bo and returns the same event-specific whitelist to internal staff. Dashboard usage here is API fetch plus refresh subscription. No PostgREST request was run; ops.view diary is a separate route and not conflated with visit history.",
            "evidence": [{"path": x["path"], "lines": f"{x['read_ranges'][0]['start']}-{x['read_ranges'][0]['end']}", "sha256": x["sha256"]} for x in (by_path["supabase/migrations/20260923000002_projection_dong_thoi_gian.sql"], by_path["src/clinicai/api/v1/routers/xem_luot.py"], by_path["src/clinicai/services/xem_luot_service.py"], by_path["src/clinicai/events/consumers/dong_thoi_gian.py"])],
        },
        {
            "id": "ROUND42-COMPANY-INVOICE-FK-001",
            "disposition": "no_new_finding_duplicate_of_DB-007",
            "rationale": "Schema FKs are not composite-scoped to clinic/patient, but the service validates clinic and patient before write and the existing test rejects a different patient's company. This is a defense-in-depth gap, not a demonstrated current service path failure; retain under DB-007's broader relationship invariant.",
            "evidence": [{"path": x, "sha256": by_path[x]["sha256"]} for x in ("supabase/migrations/20261014156000_hoa_don_cong_ty.sql", "src/clinicai/services/hoa_don_cong_ty_service.py", "src/tests/services/test_hoa_don_cong_ty_db.py")],
        },
        {
            "id": "ROUND42-PHARMACY-STAFF-FK-001",
            "disposition": "held_not_a_finding_without_tenant_violation_evidence",
            "rationale": "The migration has a global staff FK, but the reviewed writer takes actor identity from the current staff and that staff may be active in multiple clinics. No cross-clinic write or identity mismatch was shown.",
            "evidence": [{"path": x, "sha256": by_path[x]["sha256"]} for x in ("supabase/migrations/20261019110000_pharmacy_inventory_p1_guards.sql", "src/clinicai/services/pharmacy_service.py")],
        },
    ]
    coverage = {
        "round": 42,
        "snapshot_sha": SHA,
        "mode": "read_only_exact_main_targeted_semantic_trace_with_independent_security_review",
        "scope": ["consent API authorization", "PostgREST/timeline access dedupe", "tenant foreign-key lifecycle", "pregnancy and clinical-form route guard controls"],
        "method": "Read source only from immutable Git blobs using git show; exact-main git grep for dashboard callers; read-only independent security review; tests read but not run. No ClinicAI API/database/runtime/provider/VPS/production/secret/PHI access.",
        "result": "Extended SEC-010 with sibling /links metadata exposure under the same consent-router identity-only boundary; no new finding ID. Tenant invoice FK candidate deduplicates with DB-007; timeline direct-select candidate did not add a distinct permission scope versus the normal internal journey API; pregnancy and normal clinical form route checks did not yield a new candidate.",
        "files": list(by_path.values()),
        "additional_security_evidence": [route_guard, role_proof, role_migration],
        "dashboard_string_search": tree_grep,
        "reviewer": {
            "agent": "round42_sec_review",
            "conclusion": "Merge /links metadata into SEC-010 rather than create SEC-036; same router guard boundary. Candidate remains static and conditional on actual DB credentials/UUID knowledge.",
            "runtime_role_verified": False,
        },
        "reviewed_candidates": held_or_deduped,
        "validation": {
            "application_tests": "not run; relevant source tests read only",
            "API_or_HTTP": "not run",
            "database_or_PostgREST": "not accessed",
            "production_or_secrets_or_PHI": "not accessed",
            "report_qa": "pending",
            "bundle_qa": "pending",
        },
        "limitations": [
            "The /links exposure assumes the backend database role can read the rows under the application's DATABASE_URL; the checked-in production example uses postgres, but the active secret/runtime role was not inspected.",
            "No dashboard string match was found for /links/ConsentService; dynamically constructed callers and API UUID discovery were not verified.",
            "The timeline projection stores only event-specific whitelisted fields; the normal internal visit-journey route already returns that projection. No direct PostgREST request was run.",
            "Company invoice schema lacks a composite patient/clinic FK, but reviewed service/test evidence does not show a current cross-tenant write; retained as a DB-007 defense-in-depth relationship pattern.",
            "Test results were not executed. All conclusions are static and exact-main; no incident or real patient exposure is claimed.",
            "Full source audit remains incomplete; path counts are not semantic/behavioral coverage.",
        ],
    }
    (ROOT / "blocks/round42.md").write_text(
        "# Round 42 — consent authorization, tenant relations và timeline projection\n\n"
        f"Nguồn code là Git main ghim `{SHA}` qua `git show`; checkout chính có WIP và không phải bằng chứng. Chỉ audit artifacts được sửa. Không chạy ClinicAI tests/API/DB/runtime/provider/production, không đọc secrets hoặc PHI.\n\n"
        "## SEC-010 — mở rộng cùng ranh giới guard, không tạo ID mới\n\n"
        "Router consent có hai đường đọc dùng `get_current_identity`: `/patients/{patient_id}/shared-form` và `/patients/{patient_id}/links`. SEC-010 đã bao phủ đường shared-form: caller tự truyền hai patient ID, nhánh cùng ID qua `may_surface`, sau đó service có thể trả tối đa 20 `form_data`. Lát này bổ sung `/links`: service lọc `clinic_id` cùng UUID được truyền nhưng trả quan hệ, ID/tên/mã người kia và form-code consent hai chiều. Nó không trả `form_data`.\n\n"
        "Policy DB của `clinical_data_consent` giới hạn RLS cho DOCTOR, ULTRASOUND_DOCTOR, TKYK và NURSE_ULTRASOUND; migration nói MANAGEMENT không có quyền đọc lâm sàng mặc định. `get_current_identity` chỉ từ chối DISPLAY/PARTNER. Backend lấy kết nối qua `DATABASE_URL`, còn `.env.prod.example` dùng user `postgres`; không đọc cấu hình runtime/secret. Vì vậy đây là khoảng trống tĩnh với điều kiện DB role chuẩn, UUID cùng clinic đã biết và không phải chứng cứ có người khai thác. Exact evidence và SHA ở `round42.coverage.json`. Reviewer bảo mật độc lập khuyến nghị gộp vào SEC-010 vì cùng router/guard boundary; không tạo SEC-036.\n\n"
        "Test service IO kiểm tra metadata được trả nhưng không kiểm quyền vai ở route; test chỉ được đọc. Không tìm thấy chuỗi caller `/links`, `ConsentService` hoặc `linked_partners` trong dashboard; grep không loại trừ caller dựng động.\n\n"
        "## Candidate được rà nhưng không mở finding\n\n"
        "- **Timeline projection/PostgREST:** migration cấp SELECT theo clinic và `chi_tiet` chứa whitelist theo loại sự kiện. Tuy vậy API hành trình lượt thường dùng `cua_noi_bo` và trả projection cho nội bộ; dashboard dùng API để nạp và bảng chỉ để refresh. Vì không chứng minh phạm vi quyền tăng thêm so với luồng thường, không mở finding riêng. Nhật ký `/ops/nhat-ky` là route khác có `ops.view`; không gộp nhầm hai bề mặt. Chưa chạy PostgREST/JWT.\n"
        "- **Hóa đơn công ty:** FK không ghép clinic/patient ở schema, nhưng service kiểm tra patient và company theo clinic; test đọc có ca company của bệnh nhân khác bị loại. Đây là defense-in-depth gần DB-007, không có đường ghi hiện tại sai đã chứng minh.\n"
        "- **Kho thuốc:** FK staff toàn cục nhưng FK request–transaction giữ clinic + batch; writer lấy actor từ identity. Staff có thể làm nhiều clinic; chưa có chứng cứ mismatch nên giữ ngoài register.\n"
        "- **Thai kỳ/clinical forms:** full read hai router cho thấy clinical forms khai guard y khoa; ThaiKyService kiểm quyền ghi, patient/visit clinic. Không thêm finding trong lát này.\n\n"
        "Coverage path/ranges/hashes và giới hạn được lưu trong `round42.coverage.json`. Đây là lát rà mục tiêu, không phải đọc hết repository; full source audit vẫn đang mở.\n"
    )
    (ROOT / "blocks/round42.coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n")

    path_counts = Counter(item["status"] for item in manifest["files"])
    code_suffixes = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html"}
    code = [x for x in manifest["files"] if Path(x["path"]).suffix.lower() in code_suffixes]
    code_counts = Counter(x["status"] for x in code)
    severity = Counter(item["severity"] for item in findings)
    levels = Counter(item["evidence_level"] for item in findings)
    main_status = Counter(item["main_validation"]["status"] for item in findings)

    state = load("STATE.json")
    state["updated_at"] = "2026-10-20"
    state["status"] = "in_progress"
    state["phase"] = "round42_v065_consent_scope_extended_tenant_timeline_dedup_audit_open"
    state["next_action"] = "Continue exact-main review of unread dashboard and service paths, prioritizing patient/object authorization, clinical lifecycle, finance reconciliation and event recovery. SEC-010 now includes the consent /links metadata surface; full source audit remains incomplete."
    state["report_status"] = "v0.65 report build and report-only QA pending; full source audit remains incomplete."
    state["report_version"] = "v0.65"
    state["report_round_summary"] = "Round 42 extends SEC-010 to the sibling /links endpoint: identity-only route returns relationship and consent-form metadata while the DB policy is clinical-role scoped; runtime DB credentials, UUID discovery and dashboard caller are unverified. Company invoice FK candidate deduplicates with DB-007; timeline PostgREST grant adds no distinct scope over the ordinary internal journey API; ThaiKy/clinical form route checks found no new candidate. No application or runtime checks ran. Full source audit remains incomplete."
    state["full_source_audit_complete"] = False
    state["report_html_sha256"] = "pending report-only QA"
    state["portable_bundle_status"] = "pending v0.65 package verification"
    summary = state["summary"]
    summary["findings"] = len(findings)
    summary["severity"] = {k: severity[k] for k in ("HIGH", "MEDIUM", "LOW")}
    summary["evidence_levels"] = {k: levels[k] for k in ("reproduced_local", "design_gap", "confirmed_static")}
    summary["main_status"] = {k: main_status[k] for k in ("still_present_on_main", "partially_addressed_on_main", "addressed_on_main")}
    summary["main_files"] = len(manifest["files"])
    summary["main_partial_traces"] = path_counts["traced"]
    summary["main_coverage"] = {k: path_counts[k] for k in ("read", "traced", "scanned", "inventoried", "excluded")}
    summary["main_read_files"] = path_counts["read"]
    summary["code_like_source_files"] = {
        "definition": "Pinned-tree paths with common code/web/sql/shell suffixes; includes app, tests, tooling and styles.",
        "total": len(code),
        "coverage": {k: code_counts[k] for k in ("read", "traced", "scanned", "inventoried", "excluded")},
        "traced_is_partial": True,
    }
    summary["reviewed_slice_v065"] = "Round 42: SEC-010 extended to consent /links metadata; independent security reviewer advised dedup rather than SEC-036. Company-invoice FK remains under DB-007; timeline projection no distinct scope over internal journey API; ThaiKy and clinical-form route controls checked. No app/DB/API/runtime/provider/production access."
    summary["new_findings_v065"] = []
    summary["extended_findings_v065"] = ["SEC-010"]
    state["blocks"]["round42"] = {
        "status": "round42_integrated_report_qa_pending_audit_open",
        "notes": "blocks/round42.md",
        "findings": "SEC-010 extended; no new ID; DB-007 dedupe and timeline/ThaiKy no-finding checks recorded",
        "coverage": "blocks/round42.coverage.json",
        "next": "Continue unread dashboard/service source audit and exact-main API/object authorization. Validate the consent role matrix only on a disposable fixture after scope is explicitly expanded; do not inspect production credentials or PHI.",
    }
    state["limits"][:2] = [
        f"Full source audit incomplete: ledger has {path_counts['inventoried']} inventoried, {path_counts['traced']} partially traced, {path_counts['scanned']} scanned and {path_counts['excluded']} excluded paths out of {len(manifest['files']):,}. Path status is not behavioral coverage.",
        f"Code-like suffix group includes runtime, tests, tooling and styles; current counts are {code_counts['read']} read, {code_counts['traced']} partially traced, {code_counts['scanned']} scanned, {code_counts['inventoried']} inventoried and {code_counts['excluded']} excluded out of {len(code):,}. This is not a percent-complete or correctness score.",
    ]
    state["artifacts"].update({
        "qa": "pending v0.65 report-only validator and desktop/mobile browser QA; not ClinicAI behavior validation.",
        "integration_script": "Round42: integrate_round42.py; blocks/round42.md and blocks/round42.coverage.json; report/package QA pending.",
        "bundle_integrity": "pending v0.65 ZIP regeneration and verification.",
        "html_sha256": "pending v0.65 report build.",
        "html_checked_at": "pending",
        "qa_html_version": "v0.65 pending",
    })
    save("STATE.json", state)

    (ROOT / "NHAN-DINH.md").write_text(
        "# Nhận định theo các lát cắt đã kiểm — Round 42: API consent, tenant scope và timeline\n\n"
        f"Nguồn code là Git main ghim `{SHA}`. Risk register giữ 195 hồ sơ (26 HIGH, 141 MEDIUM, 28 LOW); SEC-010 được mở rộng, không tạo ID mới. Path ledger {len(manifest['files']):,} path: {path_counts['read']} read, {path_counts['traced']} traced một phần, {path_counts['scanned']} scanned, {path_counts['inventoried']} inventoried, {path_counts['excluded']} excluded. Đây là các giai đoạn kiểm theo path, không phải coverage hành vi; **full source audit chưa hoàn tất**.\n\n"
        "SEC-010 hiện bao gồm `/patients/{patient_id}/links`: endpoint cùng router chỉ dùng get_current_identity, trả quan hệ, tên/mã và consent form_codes; policy RLS của bảng consent giới hạn cho bốn vai lâm sàng. Đây là mở rộng cùng ranh giới với shared-form, không phải lộ form_data từ /links. Khả năng khai thác phụ thuộc cấu hình DATABASE_URL thật chưa được kiểm; cần UUID cùng clinic. Reviewer bảo mật độc lập đồng ý gộp vào SEC-010.\n\n"
        "Không mở finding riêng cho timeline projection sau khi so sánh với API hành trình nội bộ; không tách candidate FK công ty khỏi DB-007 vì service/test hiện có chốt clinic/patient; không thấy vi phạm tenant từ FK staff kho thuốc. Đọc full hai router ThaiKy và clinical forms, không tạo candidate mới ở lát đó. Test chỉ đọc, không chạy; không gọi API/DB/runtime/production, không đọc secret hay PHI. Report v0.65 và ZIP audit-only đang chờ QA; full source audit vẫn mở.\n"
    )
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(
        "# Bắt đầu từ đây — checkpoint v0.65, Round 42\n\n"
        "Round 42 mở rộng SEC-010 sang metadata của GET `/patients/{patient_id}/links`; cùng identity-only guard, nhưng không trả clinical form_data. Independent security review khuyến nghị gộp vào SEC-010, không tạo ID trùng. Candidate timeline và FK hóa đơn công ty được dedupe; xem `blocks/round42.md` và `blocks/round42.coverage.json`.\n\n"
        f"Risk register: 195 findings (26 HIGH, 141 MEDIUM, 28 LOW). Path ledger {len(manifest['files']):,}: {path_counts['read']} read, {path_counts['traced']} traced một phần, {path_counts['scanned']} scanned, {path_counts['inventoried']} inventoried, {path_counts['excluded']} excluded. Full source audit **chưa hoàn tất**; đây không phải phần trăm hoàn thành.\n\n"
        f"Nguồn duy nhất: Git SHA `{SHA}` qua `git show` trong worktree audit. Main checkout có WIP và không phải bằng chứng. Chỉ sửa audit artifacts tại thư mục này; không sửa app/migration hoặc chạy ClinicAI app/tests/API/DB/provider/VPS/production; không đọc secrets/PHI.\n\n"
        "QA report/ZIP v0.65 đang chờ. Sau đó cập nhật hash HTML, QA metadata, đóng gói ZIP, chạy verify_bundle.py và cập nhật TIEP-TUC/NHAT-KY.\n\n"
        "## Trình tự tiếp quản\n\n"
        "1. Đọc `TIEP-TUC.md`, `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `blocks/round42.md` và coverage.\n"
        "2. Tiếp tục unread dashboard/service/API paths; ưu tiên object authorization, clinical lifecycle, financial reconciliation và event recovery.\n"
        "3. Giữ điều kiện runtime DB credentials, UUID discovery và product-policy holds rõ ràng.\n"
        "4. Chỉ kết luận full audit khi semantic review, cross-layer tracing và dedup các vùng còn lại đã xong.\n"
    )
    (ROOT / "TIEP-TUC.md").write_text(
        "# CURRENT HANDOFF — v0.65, Round 42\n\n"
        f"Evidence source: immutable Git SHA `{SHA}` in the managed audit worktree. The primary checkout has user WIP and is not evidence. Read source with `git show <SHA>:<path>`. Modify only audit artifacts under this directory; do not edit app/migrations or run ClinicAI tests/runtime/API/DB/provider/VPS/production/secrets/PHI.\n\n"
        "Round 42 extends SEC-010 to the sibling consent `/links` endpoint: identity-only API guard, clinical-role-scoped DB policy, and relationship/form-code metadata exposure under same clinic. Independent security review recommends consolidating rather than SEC-036. Company-invoice FK candidate deduplicates with DB-007; timeline direct table grant does not establish distinct scope beyond the normal internal journey API. Full source audit remains incomplete. Evidence: `blocks/round42.md`, `blocks/round42.coverage.json`.\n\n"
        f"Risk register: {len(findings)} findings ({severity['HIGH']} HIGH, {severity['MEDIUM']} MEDIUM, {severity['LOW']} LOW). Ledger {len(manifest['files']):,} paths ({path_counts['read']} read, {path_counts['traced']} partially traced, {path_counts['scanned']} scanned, {path_counts['inventoried']} inventoried, {path_counts['excluded']} excluded). These are inspection stages, not semantic coverage.\n\n"
        "## Current checkpoint\n\n"
        "Report v0.65 is pending build and report-only QA. No ClinicAI tests/runtime/DB/provider/production were run this round. The prior v0.64 QA and bundle do not validate the new SEC-010 evidence.\n\n"
        "## Next work\n\n"
        "1. Build v0.65 from canonical PHAT-HIEN/STATE; run validator and desktop/mobile report QA.\n"
        "2. Rebuild the audit-only ZIP, verify its member set/CRC/bytes/SHA and record outer digest.\n"
        "3. Continue exact-main review of unread source, prioritizing dashboard flows, API object authorization, clinical lifecycle and event/finance recovery.\n"
        "4. Keep DB runtime role, caller/UUID discovery, product-policy holds and untested behaviors explicit.\n"
        "5. Do not claim all code was read: 2,890 paths remain a mixture of full reads, partial traces, scans and inventory.\n"
    )
    journal = ROOT / "NHAT-KY.md"
    existing = journal.read_text()
    if "## Round 42 — 20/10/2026" not in existing:
        journal.write_text(
            "## Round 42 — 20/10/2026, v0.65\n\n"
            "SEC-010 được mở rộng sau independent security review: `/links` cùng consent router trả relation/name/code/form_codes nhưng route chỉ dùng identity guard, trong khi migration đặt RLS consent theo vai lâm sàng. Không tạo SEC-036 vì trùng cùng permission boundary; điều kiện DB credentials/UUID/caller chưa xác minh. Company invoice FK dedupe với DB-007; timeline projection không thêm distinct scope so với internal journey API; ThaiKy/clinical forms control slice không có candidate mới. Full router reads: thai_ky và clinical_forms; tests chỉ đọc. Không chạy app/API/DB/runtime/provider/production; không đọc secrets/PHI. Risk register 195; full source audit còn mở. Xem `blocks/round42.coverage.json`.\n\n" + existing
        )

    print(
        f"Integrated Round 42: {len(findings)} findings; SEC-010 extended; "
        f"path status={dict(path_counts)}; code status={dict(code_counts)}"
    )


if __name__ == "__main__":
    main()
