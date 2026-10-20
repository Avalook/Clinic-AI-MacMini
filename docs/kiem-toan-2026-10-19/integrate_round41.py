"""Integrate a read-only exact-main audit slice into the durable report."""
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


def proof(path: str, start: int, end: int, detail: str) -> tuple[dict, dict]:
    data, lines = source(path)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid pinned range {path}:{start}-{end}")
    digest = hashlib.sha256(data).hexdigest()
    excerpt = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
    return (
        {"path": path, "line": start, "end_line": end, "detail": detail},
        {"path": path, "line": start, "end_line": end, "sha256": digest, "excerpt": excerpt},
    )


def add_proofs(finding: dict, specs: list[tuple[str, int, int, str]]) -> list[dict]:
    added = []
    for path, start, end, detail in specs:
        evidence, main = proof(path, start, end, detail)
        if not any((x["path"], x["line"], x["end_line"]) == (path, start, end) for x in finding["evidence"]):
            finding["evidence"].append(evidence)
        if not any((x["path"], x["line"], x["end_line"]) == (path, start, end) for x in finding["main_validation"]["evidence"]):
            finding["main_validation"]["evidence"].append(main)
        finding.setdefault("source_hashes", {})[path] = main["sha256"]
        added.append({**main, "detail": detail, "lines": len(source(path)[1])})
    return added


def main() -> None:
    findings = load("PHAT-HIEN.json")
    by_id = {x["id"]: x for x in findings}

    migration_specs = [
        ("scripts/apply-pending-migrations.sh", 53, 61, "psql bật ON_ERROR_STOP; runner không bật --single-transaction."),
        ("scripts/apply-pending-migrations.sh", 137, 153, "Runner nối BEGIN, nội dung migration, INSERT ledger, COMMIT; internal COMMIT có thể để INSERT chạy riêng."),
        ("supabase/migrations/20260821000001_ba_ca_lam_viec.sql", 68, 78, "Replay ghi open/close 07:00–22:00 cho mọi clinic có settings.hours rồi COMMIT."),
        ("supabase/migrations/20260916000008_vi_tri_lam_viec_kim_nguu.sql", 91, 95, "Danh mục vị trí được cross join qua mọi clinic."),
        ("supabase/migrations/20260916000008_vi_tri_lam_viec_kim_nguu.sql", 136, 142, "ON CONFLICT replay cập nhật lại tên, phòng, nhóm nghề, thứ tự và trạng thái vị trí."),
        ("supabase/migrations/20260916000009_ma_tran_vai_theo_vi_tri_kim_nguu.sql", 35, 42, "Replay tắt lại các mã vị trí ngoài ma trận khai báo."),
        ("supabase/migrations/20260916000009_ma_tran_vai_theo_vi_tri_kim_nguu.sql", 63, 65, "Replay bật lại vai trò theo ma trận chuẩn."),
        ("supabase/migrations/20260916000010_gan_lai_ma_phieu_kham.sql", 22, 45, "Replay gán lại form_code mặc định cho các service_type khớp mã."),
        ("supabase/migrations/20260916000011_vi_tri_dong_ca.sql", 54, 57, "Replay xóa giá trị phòng trên hai vị trí được nêu."),
        ("supabase/migrations/20260916000012_hoi_benh_ai_cung_dung_duoc.sql", 22, 36, "Replay đặt nhóm nghề CHUNG và bật ma trận vai trò tương ứng."),
        ("supabase/migrations/20260917000001_phong_kim_nguu_va_duong_chi_dinh.sql", 64, 78, "Replay cập nhật phòng Kim Ngưu và nạp liên kết phòng–nút."),
        ("supabase/migrations/20260917000001_phong_kim_nguu_va_duong_chi_dinh.sql", 130, 158, "Replay gán lại phòng cho vị trí và actor_roles cho các mã thủ thuật."),
    ]
    pos_specs = [
        ("src/clinicai/services/pos_relay.py", 42, 101, "Poll lấy PENDING; advisory lock chỉ sống cùng session và không ghi trạng thái gửi trước lệnh gọi provider."),
        ("src/clinicai/services/pos_relay.py", 118, 158, "Adapter được gọi trước; row chỉ chuyển SENT sau khi adapter trả về và UPDATE DB hoàn tất."),
        ("src/clinicai/ports/pos.py", 43, 50, "Invoice có clinic_reference và contract yêu cầu adapter coi gọi lặp cùng reference là một invoice."),
        ("src/clinicai/ports/pos.py", 83, 103, "Port yêu cầu mọi phương thức an toàn khi được gọi hai lần cùng clinic_reference."),
        ("src/clinicai/adapters/pos/kiotviet.py", 37, 80, "KiotViet hiện từ chối thao tác; chưa có adapter vendor thật được xác minh."),
        ("src/tests/test_pos_relay.py", 127, 205, "Test đọc bao phủ lỗi/retry/DEAD/SENT; không có failpoint provider-accepted rồi worker chết trước UPDATE SENT."),
    ]
    clinical_specs = [
        ("src/clinicai/api/v1/routers/phieu_kham.py", 177, 193, "PUT route gọi trực tiếp luu_luot; không truyền release state hay amendment reason."),
        ("src/clinicai/services/phieu_kham_service.py", 413, 427, "Service lưu phiếu ở CHE_DO_MO và chỉ kiểm tra visit tồn tại trong clinic."),
        ("src/clinicai/services/phieu_kham_service.py", 435, 492, "Service khóa revision và ghi dữ liệu/revision; đường này không gọi ClinicalSignService.amend."),
        ("src/clinicai/services/clinical_sign_service.py", 581, 604, "Luồng amendment mới thu hồi clinical_release và tạo việc CSKH báo lại."),
        ("supabase/migrations/20260804000007_clinical_sign_release.sql", 108, 153, "Clinical status view tổng hợp visit, clinical_release và visit_amendment; không tham chiếu phiếu V5."),
    ]

    inf8 = by_id["INF-008"]
    inf8["summary"] = (
        "supabase-local-nap.sh chạy từng migration riêng, nhưng chỉ tạo/ghi ledger sau khi toàn chuỗi thành công; "
        "guard chỉ chặn khi ledger đã có dòng. Nếu bootstrap dừng giữa chừng, lần chạy lại có thể áp lại baseline "
        "không idempotent. Cùng bất biến schema–ledger bị phá ở apply-pending-migrations.sh: runner mở transaction, "
        "nối file migration, INSERT ledger rồi COMMIT; 23 migration có dòng BEGIN/COMMIT độc lập, nên COMMIT nội bộ "
        "có thể kết thúc transaction trước INSERT ledger. Nếu tiến trình dừng hoặc INSERT lỗi trong cửa sổ đó, version "
        "vẫn pending. Một số migration hiện có đặt lại cấu hình clinic khi replay, ví dụ giờ hoạt động về 07:00–22:00 "
        "hoặc cập nhật lại danh mục vị trí theo giá trị mẫu. Đây là rủi ro tĩnh có điều kiện, chưa chứng minh dữ liệu "
        "đã bị ghi đè hay có incident production."
    )
    inf8["trigger"] = (
        "Local bootstrap bị ngắt sau khi một migration commit nhưng trước khi ledger được ghi; hoặc runner thường gặp "
        "migration tự COMMIT và tiến trình dừng / thao tác ghi ledger thất bại trước khi INSERT được lưu. Lần tiếp theo "
        "vẫn chọn version là pending và chạy lại DDL/DML của migration."
    )
    inf8["impact"] = (
        "Bootstrap retry có thể lỗi vì object baseline đã tồn tại. Ở runner thường, retry còn có thể ghi lại dữ liệu cấu "
        "hình theo seed trong migration: migration giờ hoạt động thay mọi open/close đã cấu hình thành 07:00–22:00; "
        "migration danh mục vị trí dùng ON CONFLICT DO UPDATE để nạp lại phòng/nhóm nghề/thứ tự/trạng thái; các migration "
        "khác đặt lại ma trận vai trò hoặc mapping form. Tác động chỉ xảy ra nếu đúng cửa sổ interruption và migration đó "
        "được retry; chưa có bằng chứng cấu hình nào ở production thực sự bị ghi đè."
    )
    inf8["recommendation"] = (
        "Giữ một chủ sở hữu transaction duy nhất: cấm transaction-control tự phát trong migration nếu runner bọc transaction, "
        "hoặc điều phối transaction-control bằng runner có kiểm tra rõ; ledger phải commit cùng thay đổi schema. Tách seed "
        "cấu hình khởi tạo khỏi migration nâng cấp schema, tránh replay áp lại giá trị mặc định lên clinic đã được quản lý. "
        "Thêm lint trên SQL và fault-injection trên DB disposable cho cả local bootstrap lẫn runner thường."
    )
    inf8["acceptance"] = (
        "Fault-inject sau schema commit và trước ledger write trên DB disposable cho cả hai runner. Retry phải đưa schema "
        "và ledger về cùng version mà không lặp DDL/DML ngoài ý muốn; cài một cấu hình giờ/phòng/ma trận khác seed trước "
        "khi fault-inject và xác nhận retry không tự ghi đè cấu hình đó. Test chạy tự động trên clean disposable DB; tuyệt "
        "đối chiếu trạng thái ledger và các giá trị cấu hình trước/sau."
    )
    inf8["validation"]["result"] = (
        "Đối chiếu guard, thứ tự chạy/ghi ledger, nhánh bootstrap, replay test và baseline CREATE FUNCTION. Exact-main "
        "structural scan tìm 23 migration có standalone BEGIN; và COMMIT;. Semantically đọc các runner và 8 migration "
        "có DML cấu hình tiêu biểu; xác nhận một số câu lệnh replay có thể ghi lại giờ/danh mục/ma trận theo giá trị seed."
    )
    inf8["validation"]["limitations"] = (
        "Static trace; chưa fault-inject, chạy PostgreSQL/DB hay migration replay. Không có bằng chứng một clinic thật "
        "đã bị ghi đè hoặc production incident. Structural scan của 23 file không phải semantic review tất cả SQL; chỉ "
        "8 migration có DML cấu hình được kiểm tra mục tiêu trong slice này. Không chạy test ClinicAI."
    )
    inf8["validation"]["method"] = "exact_main_static_transaction_and_replay_effect_trace"
    inf8["main_validation"]["note"] = (
        "Exact-main static trace: transaction-control mismatch tạo ledger drift window; các migration tiêu biểu có thể "
        "ghi lại giá trị cấu hình khi bị retry. Không fault-inject, không chứng minh cấu hình thật đã đổi hay có incident."
    )
    added_inf8 = add_proofs(inf8, migration_specs)

    inf11 = by_id["INF-011"]
    inf11["summary"] += (
        " Một rủi ro phụ cần chặn trước khi bật adapter thật: relay gọi provider trước rồi mới ghi SENT; nếu provider đã "
        "nhận giao dịch nhưng worker/DB connection dừng trước UPDATE, row có thể được poll lại. PosPort yêu cầu idempotency "
        "theo clinic_reference, nhưng adapter KiotViet hiện chỉ từ chối và test chưa mô phỏng khoảng crash này. Đây là cổng "
        "readiness tương lai, chưa phải lỗi gửi trùng đang hoạt động."
    )
    inf11["trigger"] += (
        " Nếu adapter thật được bật: POS nhận invoice/void/stock movement, sau đó worker chết hoặc UPDATE SENT thất bại; "
        "advisory lock được thả theo session và row còn PENDING để lần poll sau gọi lại."
    )
    inf11["impact"] += (
        " Nếu adapter thật không khử trùng theo cùng clinic_reference, lần gửi lại sau một kết quả ngoài hệ thống không "
        "rõ có thể tạo invoice/void/stock movement trùng. Contract đã yêu cầu idempotency nhưng chưa có adapter thật để "
        "xác minh; không có bằng chứng gửi trùng trong production."
    )
    inf11["recommendation"] = (
        "Trước khi bật POS, cung cấp queue theo clinic với trạng thái/giá trị/subject, lỗi đã làm sạch, owner, thời điểm và "
        "nút retry an toàn/reconcile; thêm alert/SLO, idempotency bền theo external reference và audit thao tác thủ công. "
        "Với kết quả provider mơ hồ, tra cứu/reconcile bằng clinic_reference trước retry; không coi timeout/crash là thất bại chắc chắn."
    )
    inf11["acceptance"] = (
        "Synthetic adapter failure tạo DEAD nhìn thấy trong dashboard/health có alert; staff được ủy quyền gán owner và "
        "retry/reconcile idempotent; retry không tạo invoice/void/stock movement trùng. Fault-injection sau provider acceptance "
        "nhưng trước UPDATE SENT phải hội tụ về đúng một hiệu ứng ngoài và một dòng đã reconciled. Mọi action có audit actor/kết quả."
    )
    inf11["validation"]["result"] = (
        "Static trace relay/config/schema/test/health/API/dashboard. Relay gọi adapter trước UPDATE SENT, giữ row PENDING "
        "nếu process dừng trước cập nhật trạng thái; port yêu cầu idempotency theo clinic_reference. KiotViet adapter hiện "
        "chưa triển khai; không thấy operator recovery path."
    )
    inf11["validation"]["limitations"] = (
        "Chưa chạy relay, provider thật, HTTP/admin UI hay crash-after-provider-acceptance test. Adapter KiotViet hiện "
        "fail-closed; duplicate external side effect là rủi ro có điều kiện trước khi bật adapter, không phải incident "
        "được xác nhận. Test hiện có đã đọc nhưng không chạy."
    )
    added_inf11 = add_proofs(inf11, pos_specs)

    clin = by_id["CLIN-020"]
    conditional = (
        " Mở rộng có điều kiện: nếu chính sách xác định clinical_release bao gồm phiếu V5, autosave sau RELEASED vẫn đi "
        "qua luu_luot/CHE_DO_MO; đường đó không gọi amendment để thu hồi release hoặc tạo việc CSKH báo lại. Phạm vi "
        "release của V5 chưa được chủ sản phẩm/lâm sàng chốt, nên giữ đây là policy gate, không khẳng định vi phạm lâm sàng."
    )
    if "clinical_release bao gồm phiếu V5" not in clin["summary"]:
        clin["summary"] += conditional
    clin["validation"]["limitations"] += (
        " Release scope for phiếu V5 remains undecided in QUYET-DINH.md; the release-to-form relationship is conditional, "
        "not an established clinical-policy breach."
    )
    added_clin = add_proofs(clin, clinical_specs)

    transaction_statements: dict[str, set[str]] = {}
    for line in subprocess.check_output(
        ["git", "grep", "-n", "-E", "^(BEGIN|COMMIT);$", SHA, "--", "supabase/migrations/*.sql"],
        cwd=REPO,
        text=True,
    ).splitlines():
        _, path, _, statement = line.split(":", 3)
        transaction_statements.setdefault(path, set()).add(statement)
    migrations = sorted(path for path, statements in transaction_statements.items() if statements == {"BEGIN;", "COMMIT;"})
    if len(migrations) != 23:
        raise AssertionError(f"Expected 23 standalone transaction migrations, got {len(migrations)}")

    held = load("STATE.json")["held_observations"]
    held_id = "CLIN-V5-RELEASE-001"
    held_item = {
        "id": held_id,
        "classification": "held_product_policy_condition_not_a_new_finding",
        "snapshot_sha": SHA,
        "question": "Nếu phiếu khám V5 thuộc phạm vi clinical_release, sửa phiếu sau RELEASED có phải tạo amendment, thu hồi release và mở việc CSKH báo lại không?",
        "observation": "Route PUT gọi luu_luot; service dùng CHE_DO_MO và cập nhật nội dung/revision. Luồng amendment của clinical_sign_service mới thu hồi clinical_release và tạo việc CSKH; v_clinical_status tổng hợp visit/release/amendment, không tham chiếu phiếu V5.",
        "evidence": [
            {"path": x["path"], "lines": f"{x['line']}-{x['end_line']}", "sha256": x["sha256"]}
            for x in added_clin
        ],
        "not_promoted_reason": "QUYET-DINH.md chưa chốt FINALIZED/release có áp dụng cho phiếu V5 hay không; chưa đủ cơ sở để gọi đây là vi phạm policy lâm sàng.",
        "next": "Chủ sản phẩm/lâm sàng xác định release scope cho V5. Nếu có, đưa V5 vào cùng trạng thái/revision/amendment/revoke/renotify contract và kiểm thử; nếu không, ghi rõ phiếu V5 nằm ngoài release boundary.",
    }
    if not any(isinstance(x, dict) and x.get("id") == held_id for x in held):
        held.append(held_item)

    coverage_files = []
    unique = {}
    for item in added_inf8 + added_inf11 + added_clin:
        key = item["path"]
        entry = unique.setdefault(key, {"path": key, "sha256": item["sha256"], "lines": item["lines"], "read_ranges": [], "notes": []})
        entry["read_ranges"].append({"start": item["line"], "end": item["end_line"]})
        entry["notes"].append(item["detail"])
    coverage_files = list(unique.values())
    round41 = {
        "round": 41,
        "snapshot_sha": SHA,
        "mode": "read_only_exact_main_targeted_semantic_trace",
        "scope": ["migration runner replay effects", "POS delivery ambiguity and recovery readiness", "V5 clinical release boundary policy"],
        "method": "Read only immutable Git blobs via git show and exact-main git grep. Structural scan finds exact standalone BEGIN;/COMMIT; pair in 23 migration files. Semantic review targets 8 migrations with config DML; static relay/port/adapter/test traces; V5 route/service/release traces. No application test, DB, API, runtime, provider, production, secret or PHI access.",
        "result": "Extended INF-008 and INF-011; added no finding ID. CLIN-020 receives a conditional release-scope note; kept as a product/clinical policy hold until V5 is explicitly included/excluded from clinical_release.",
        "explicit_transaction_migrations": migrations,
        "migration_config_examples": [x[0] for x in migration_specs[2:]],
        "files": coverage_files,
        "validation": {
            "application_tests": "not run; source tests read only",
            "database_or_fault_injection": "not run",
            "pos_provider": "not called; KiotViet adapter is an unfinished fail-closed stub",
            "production": "not accessed",
            "report_qa": "pending",
            "bundle_qa": "pending",
        },
        "limitations": [
            "The migration pattern scan is structural, not semantic review of every statement in all 23 files.",
            "Replay-triggered config overwrite is a conditional code-path effect, not evidence it happened in an actual clinic.",
            "POS duplicate side effect depends on a future real adapter and its idempotency; no external delivery was attempted.",
            "V5 clinical_release scope remains a product/clinical policy question.",
            "Full source audit remains incomplete; path counts do not imply behavioral coverage.",
        ],
    }
    (ROOT / "blocks/round41.md").write_text(
        "# Round 41 — replay migration, POS retry và ranh giới release V5\n\n"
        f"Nguồn là Git main ghim `{SHA}`; chỉ đọc source và test. Không chạy ClinicAI test/runtime/API/DB/provider/production.\n\n"
        "## INF-008 — mở rộng tác động replay\n\n"
        "Exact-main structural scan xác nhận 23 migration có dòng standalone `BEGIN;` và `COMMIT;`. Runner thường nối "
        "migration vào transaction rồi ghi ledger; COMMIT bên trong có thể tách schema commit khỏi ledger. Round này đọc mục tiêu "
        "8 migration có DML cấu hình. Ví dụ cụ thể: `20260821000001_ba_ca_lam_viec.sql:68–76` ghi lại tất cả giờ mở/đóng thành "
        "07:00–22:00 cho clinic có cấu hình hours; `20260916000008_vi_tri_lam_viec_kim_nguu.sql:91–95,136–142` áp danh mục "
        "qua clinic và cập nhật lại hàng trùng bằng seed. Nếu runner dừng giữa commit và ledger, retry có thể ghi lại cấu hình "
        "được quản lý. Đây là khả năng có điều kiện từ static code; không chứng minh clinic nào đã bị ghi đè hay có incident.\n\n"
        "## INF-011 — cổng chống gửi POS trùng trước khi bật adapter\n\n"
        "Relay giữ row PENDING trong lúc gọi adapter và chỉ ghi SENT sau khi adapter trả về. Nếu provider đã nhận giao dịch nhưng "
        "worker dừng trước UPDATE SENT, row có thể được poll lại sau khi advisory lock/session kết thúc. PosPort yêu cầu adapter "
        "idempotent theo `clinic_reference`; KiotViet hiện là stub fail-closed, chưa có adapter ngoài được xác minh. Vì vậy đây là "
        "readiness gate, không phải lỗi gửi trùng hiện hành. Test được đọc nhưng không chạy và chưa mô phỏng provider-accepted/crash.\n\n"
        "## CLIN-020 — policy hold về release V5\n\n"
        "Nếu `clinical_release` bao gồm phiếu V5, đường autosave sau RELEASED hiện dùng `luu_luot`/`CHE_DO_MO`; nó không đi qua "
        "amendment để thu hồi release và tạo việc CSKH báo lại. Tuy nhiên `QUYET-DINH.md` chưa chốt V5 thuộc release scope hay không. "
        "Giữ câu hỏi này làm policy gate, không tạo finding mới và không khẳng định vi phạm lâm sàng.\n\n"
        "Coverage, line range và source hash exact-main ở `round41.coverage.json`. Full source audit vẫn chưa hoàn tất.\n"
    )
    save("PHAT-HIEN.json", findings)

    coverage_path = ROOT / "blocks/round41.coverage.json"
    coverage_path.write_text(json.dumps(round41, ensure_ascii=False, indent=2) + "\n")

    manifest = load("MAIN-PHAM-VI.json")
    for entry in coverage_files:
        record = next((x for x in manifest["files"] if x["path"] == entry["path"]), None)
        if record is not None:
            ranges = ", ".join(f"{x['start']}–{x['end']}" for x in entry["read_ranges"])
            note = f"Round 41: exact-main targeted trace {ranges}; see blocks/round41.coverage.json."
            if note not in record["method"]:
                record["method"] += " | " + note
    manifest["last_updated_round"] = 41
    save("MAIN-PHAM-VI.json", manifest)
    path_counts = Counter(item["status"] for item in manifest["files"])
    code_suffixes = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html"}
    code = [x for x in manifest["files"] if Path(x["path"]).suffix.lower() in code_suffixes]
    code_counts = Counter(x["status"] for x in code)
    state = load("STATE.json")
    state["updated_at"] = "2026-10-20"
    state["status"] = "in_progress"
    state["phase"] = "round41_v064_migration_replay_pos_delivery_clinical_release_policy_hold_audit_open"
    state["next_action"] = "Continue exact-main review of unread source paths, prioritizing API/object authorization, DB constraints, clinical lifecycle, event recovery and productization gates. Keep conditional findings and policy holds separate; full source audit is not complete."
    state["report_status"] = "v0.64 report built; report-only QA and portable bundle verification pending; full source audit remains incomplete."
    state["report_version"] = "v0.64"
    state["report_round_summary"] = "Round 41 extends INF-008 with concrete conditional clinic-config overwrite examples on migration retry and INF-011 with a conditional POS redelivery window before SENT. CLIN-020 receives a V5 release-scope policy hold; no new finding ID. No application/DB/provider/production tests ran. Full source audit remains incomplete."
    state["full_source_audit_complete"] = False
    state["report_html_sha256"] = "pending report-only QA"
    state["portable_bundle_status"] = "pending v0.64 package verification"
    state["summary"]["main_files"] = len(manifest["files"])
    state["summary"]["main_partial_traces"] = path_counts["traced"]
    state["summary"]["main_coverage"] = {k: path_counts[k] for k in ("read", "traced", "scanned", "inventoried", "excluded")}
    state["summary"]["code_like_source_files"] = {
        "definition": "Pinned-tree paths with common code/web/sql/shell suffixes; includes app, tests, tooling and styles.",
        "total": len(code),
        "coverage": {k: code_counts[k] for k in ("read", "traced", "scanned", "inventoried", "excluded")},
        "traced_is_partial": True,
    }
    state["summary"]["reviewed_slice_v064"] = "Round 41: INF-008 extended with conditional replay overwrite evidence across 8 migration config slices; INF-011 extended with provider-accepted-before-SENT retry risk; V5 release boundary held for clinical policy. No new ID, no ClinicAI tests/runtime/DB/provider/production access."
    state["summary"]["new_findings_v064"] = []
    state["blocks"]["round41"] = {
        "status": "round41_integrated_report_qa_pending_audit_open",
        "notes": "blocks/round41.md",
        "findings": "INF-008 and INF-011 extended; CLIN-020 conditional release-scope note; no new ID",
        "coverage": "blocks/round41.coverage.json",
        "next": "Continue unread source audit; resolve V5 release scope with clinical owner; only validate migration failure windows on a disposable DB within explicit read-only scope change.",
    }
    limits = state["limits"]
    limits[:2] = [
        f"Full source audit incomplete: ledger has {path_counts['inventoried']} inventoried, {path_counts['traced']} partially traced, {path_counts['scanned']} scanned and {path_counts['excluded']} excluded paths out of {len(manifest['files']):,}. Path status is not behavioral coverage.",
        f"Code-like suffix group includes runtime, tests, tooling and styles; current counts are {code_counts['read']} read, {code_counts['traced']} partially traced, {code_counts['scanned']} scanned, {code_counts['inventoried']} inventoried and {code_counts['excluded']} excluded out of {len(code):,}. This is not a percent-complete or correctness score.",
    ]
    state["held_observations"] = held
    state["artifacts"].update({
        "qa": "pending v0.64 report-only validator and browser QA; not ClinicAI behavior validation.",
        "integration_script": "Round41: integrate_round41.py; blocks/round41.md and blocks/round41.coverage.json; report QA/package pending.",
        "bundle_integrity": "pending v0.64 ZIP regeneration and verification.",
        "html_sha256": "pending v0.64 report build.",
        "html_checked_at": "pending",
        "qa_html_version": "v0.64 pending",
    })
    save("STATE.json", state)

    (ROOT / "NHAN-DINH.md").write_text(
        "# Round 41 — migration replay, POS delivery và clinical release V5\n\n"
        f"Nguồn là Git main ghim `{SHA}`. Risk register có 195 hồ sơ (26 HIGH, 141 MEDIUM, 28 LOW). Path ledger "
        f"{len(manifest['files']):,} path: {path_counts['read']} read, {path_counts['traced']} traced một phần, "
        f"{path_counts['scanned']} scanned, {path_counts['inventoried']} inventoried, {path_counts['excluded']} excluded. "
        "Đây là mức kiểm kê/đọc theo path, không phải coverage hành vi; **full source audit chưa hoàn tất**.\n\n"
        "INF-008 được mở rộng: retry sau khi schema commit nhưng ledger chưa ghi có thể áp lại một số cấu hình clinic theo seed "
        "của migration, ví dụ giờ hoạt động và danh mục vị trí. INF-011 có thêm cửa sổ gửi lại POS nếu adapter thật đã nhận "
        "nhưng worker dừng trước SENT; adapter hiện chưa được triển khai và idempotency chưa được xác minh. Cả hai là rủi ro "
        "có điều kiện, không phải incident production đã chứng minh. CLIN-020 ghi nhận policy hold: V5 có nằm trong clinical_release "
        "hay không chưa được chốt. Xem `blocks/round41.md` và `blocks/round41.coverage.json`.\n\n"
        "Không có finding ID mới; tổng risk register giữ 195. Không chạy ClinicAI test, DB, API, runtime, provider hay production. "
        "Report v0.64 và ZIP bàn giao chỉ được coi là checkpoint sau khi validator, browser QA và bundle integrity hoàn tất.\n"
    )
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(
        "# Bắt đầu từ đây — checkpoint v0.64, Round 41\n\n"
        "Round 41 mở rộng INF-008 bằng ví dụ có điều kiện migration retry ghi lại cấu hình clinic; mở rộng INF-011 bằng cửa sổ "
        "POS gửi lại khi provider đã nhận nhưng worker chưa ghi SENT. CLIN-020 giữ câu hỏi V5 thuộc clinical_release hay không làm policy gate. "
        "Không thêm finding ID. Chi tiết exact-main: `blocks/round41.md`, `blocks/round41.coverage.json`.\n\n"
        "Risk register 195 findings (26 HIGH, 141 MEDIUM, 28 LOW). Full source audit chưa hoàn tất. Path ledger: "
        f"{len(manifest['files']):,} path; {path_counts['read']} read, {path_counts['traced']} traced một phần, "
        f"{path_counts['scanned']} scanned, {path_counts['inventoried']} inventoried, {path_counts['excluded']} excluded. "
        "Đây không phải tỷ lệ hoàn tất logic.\n\n"
        "Nguồn chứng cứ chỉ là Git SHA `" + SHA + "` qua `git show`; checkout chính có WIP. Chỉ sửa audit artifacts trong thư mục này; "
        "không sửa source/migration hoặc chạy app/test/DB/API/provider/VPS/production.\n\n"
        "QA/package v0.64 đang chờ chạy. Sau QA, cập nhật STATE/NHAT-KY, rebuild ZIP, verify và lưu hash outer trong `MANIFEST-GOI.json`.\n\n"
        "## Trình tự tiếp quản\n\n"
        "1. Đọc `TIEP-TUC.md`, `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json` và block Round 41.\n"
        "2. Tiếp tục các path chưa đọc sâu; ưu tiên API/object authorization, ràng buộc DB, lifecycle lâm sàng và phục hồi event.\n"
        "3. Giữ policy hold V5 riêng; không gọi path counts là hoàn tất audit.\n"
        "4. Chỉ kết luận full audit khi semantic review và dedup các vùng còn lại thật sự xong.\n"
    )
    (ROOT / "TIEP-TUC.md").write_text(
        "# CURRENT HANDOFF — v0.64, Round 41\n\n"
        f"Evidence source: immutable Git SHA `{SHA}` in the managed audit worktree. The primary checkout has user WIP and is not evidence. "
        "Read source with `git show <SHA>:<path>`. Modify only audit artifacts under this directory; do not edit app/migrations or run ClinicAI tests/runtime/API/DB/provider/VPS/production/secrets/PHI.\n\n"
        "Round 41 extends INF-008 with conditional replay-triggered clinic config overwrites; INF-011 with a provider-success-before-SENT duplicate-delivery window gated on a future real idempotent adapter; CLIN-020 has a held V5 release-scope policy question. No new finding ID. Evidence: `blocks/round41.md`, `blocks/round41.coverage.json`.\n\n"
        f"Risk register: 195 findings (26 HIGH, 141 MEDIUM, 28 LOW). Ledger: {len(manifest['files']):,} paths "
        f"({path_counts['read']} read, {path_counts['traced']} partially traced, {path_counts['scanned']} scanned, "
        f"{path_counts['inventoried']} inventoried, {path_counts['excluded']} excluded). These are inspection stages, not semantic coverage. "
        "**Full source audit remains incomplete.**\n\n"
        "## Current checkpoint\n\n"
        "Report v0.64 is built from canonical PHAT-HIEN/STATE and Round 41 evidence. Report validator, browser QA and ZIP integrity are pending. "
        "No ClinicAI tests/runtime/DB/provider/production were run.\n\n"
        "## Next work\n\n"
        "1. Finish v0.64 validator/browser/package checks and update this handoff with final hashes.\n"
        "2. Continue exact-main review of unread source, prioritizing API/object authorization, DB relationships, clinical lifecycle and event recovery.\n"
        "3. Resolve the V5 release boundary with the clinical/product owner; keep the current note conditional.\n"
        "4. Treat migration replay/fault injection as a later disposable-DB verification task, not production activity.\n"
        "5. Do not state that all code was read: 2,890 path records remain a mixture of read, partial trace, structural scan and inventory.\n"
    )

    journal = ROOT / "NHAT-KY.md"
    existing = journal.read_text()
    if "## Round 41 — 20/10/2026" not in existing:
        journal.write_text(existing.rstrip() + "\n\n## Round 41 — 20/10/2026\n\n"
            f"Read-only exact-main review on `{SHA}`. INF-008 extended: 23 transaction-control migrations structurally scanned; 8 migration DML slices traced, including examples that can reapply clinic hours and role/position configuration after a conditional replay. INF-011 extended with provider-accepted-before-SENT retry window; actual POS adapter remains unfinished, no provider or crash injection. CLIN-020 gets a conditional V5 release-scope policy hold. No new finding ID; risk register remains 195. No ClinicAI test/runtime/DB/API/provider/production access. See `blocks/round41.coverage.json`.\n")

    print("Integrated Round 41. Findings remain 195; explicit transaction-control migrations:", len(migrations))
    print("Read slices recorded:", len(coverage_files), "files")


if __name__ == "__main__":
    main()
