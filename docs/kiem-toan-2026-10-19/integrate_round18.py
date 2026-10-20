"""Integrate the round-18 static audit slices into durable audit artifacts.

The script only edits files inside this audit folder. It refuses to run against
any source revision other than the pinned exact-main checkout.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
SNAPSHOT = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
PINNED_SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
CODE_SUFFIXES = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html",
}


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def source(path: str) -> tuple[list[str], str]:
    raw = (SNAPSHOT / path).read_bytes()
    return raw.decode().splitlines(), hashlib.sha256(raw).hexdigest()


def evidence(path: str, start: int, end: int, detail: str) -> dict:
    lines, digest = source(path)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid source range {path}:{start}-{end}")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": digest,
        "excerpt": "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1)),
        "detail": detail,
    }


def review_ranges() -> dict[str, list[tuple[int, int, str]]]:
    return {
        "src/clinicai/events/worker.py": [
            (96, 115, "Claim rule blocks a newer aggregate version while any older delivery is unfinished."),
            (182, 217, "Callback failure can set DEAD, aggregates the error and notifies staff only when the event has an actor."),
            (226, 270, "Dead-event notification is role-based; the helper requires actor_staff_id and creates no per-delivery retry action."),
        ],
        "src/clinicai/api/v1/routers/ops.py": [
            (112, 126, "The event operations endpoint returns counts grouped by consumer, not delivery rows or retry actions."),
            (132, 165, "The separate error endpoint groups scrubbed error types and changes acknowledgement state; it does not reset an event delivery."),
        ],
        "src/clinicai/events/phat_lai.py": [
            (7, 14, "Projection replay explicitly leaves event_delivery unchanged and is not a delivery retry path."),
        ],
        "src/clinicai/events/hen_gio.py": [
            (145, 190, "Missing handler or exhausted callback attempts can leave a timer CHET; alerting is attempted only on the exhausted-error branch."),
            (193, 224, "Timer alerting returns without a notification when chi_tiet.nguoi_goi is absent."),
        ],
        "src/clinicai/api/v1/health.py": [
            (68, 101, "Health counts aged DEAD/CHET and overdue work in aggregate; it does not expose individual records."),
        ],
        "supabase/migrations/20260923000001_domain_event.sql": [
            (151, 225, "Delivery rows retain status/error fields while the health view exposes grouped counts."),
        ],
        "src/tests/services/test_event_worker_db.py": [
            (164, 201, "The related test checks transition to DEAD and aggregate count, not row-level ownership or retry/recovery."),
        ],
        "src/tests/services/test_hen_gio_db.py": [
            (187, 205, "The related timer test checks stale-lease reclaim to CHO, not CHET management or operator recovery."),
        ],
        "src/tests/test_health_su_kien.py": [
            (38, 51, "Health tests assert that aggregate counters create alert reasons; they do not exercise a per-record recovery flow."),
        ],
        "src/clinicai/services/phan_thu.py": [
            (144, 146, "A mixed payment cycle's scalar primary method becomes TRANSFER whenever any part is transfer."),
        ],
        "src/clinicai/services/tien_thua_service.py": [
            (84, 100, "Excess-refund query obtains one effective scalar method for the payment cycle, not its tender breakdown."),
            (133, 160, "The service returns that scalar method on each invoice line and aggregates the displayed method summary from it."),
            (201, 230, "Checkout summary groups excess amounts by each line's scalar hinh_thuc."),
        ],
        "src/clinicai/services/hoan_tien_service.py": [
            (133, 150, "The refund contract says default to the original method for each collection cycle."),
            (159, 197, "With method omitted, the service groups every excess line using d.hinh_thuc and creates one refund method per group."),
        ],
        "supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql": [
            (186, 220, "The database already provides phan_thu_hieu_luc as an exact per-tender breakdown."),
        ],
        "src/clinicai/api/v1/routers/dispatch.py": [
            (475, 510, "The refund method is optional; omitted input is passed as None to the service's default behavior."),
        ],
        "src/dashboard/app/api/reception/checkout/route.ts": [
            (59, 75, "The BFF forwards hinh_thuc only when supplied; the default action sends null/omitted method."),
        ],
        "src/dashboard/app/(dashboard)/_lam-viec/NutHoanTienThua.tsx": [
            (46, 54, "The button labels the default action from the supplied method breakdown, but falls back to a generic original-method label."),
            (60, 70, "The default request sends hinh_thuc as null."),
            (82, 96, "The selector has a single-method override and a default option, but no split-method allocation control."),
        ],
        "src/tests/services/test_thu_nhieu_hinh_thuc_db.py": [
            (45, 101, "A real 100k CASH + 50k TRANSFER cycle stores and displays both tender parts; this test does not refund its excess."),
        ],
        "src/tests/services/test_mo_phong_dong_tien_db.py": [
            (363, 403, "Default excess refund is tested for a single TRANSFER method, not a mixed-tender cycle."),
        ],
        "src/clinicai/services/tep_ket_qua_service.py": [
            (1131, 1160, "The revoke query does not select gui_luc, so the service cannot branch on whether staff marked the file sent."),
            (1199, 1256, "Before review starts, a valid file can be revoked and emits result_file.revoked without creating a corrective follow-up task."),
            (1267, 1298, "The current-file list reads the effective view, from which revoked files are excluded."),
            (1673, 1682, "gui_luc is a staff confirmation of a manual send, not proof of automated delivery."),
            (1709, 1750, "The send flow records gui_luc and emits sent_to_patient after staff confirmation."),
        ],
        "supabase/migrations/20260920000005_xac_nhan_tep_ket_qua.sql": [
            (124, 140, "The database permits HOP_LE to THU_HOI and preserves approval history; it does not gate on gui_luc."),
        ],
        "src/clinicai/events/catalogue.py": [
            (1852, 1860, "result_file.revoked is subscribed to by the timeline and review-round consumer, not CHUONG."),
        ],
        "src/clinicai/events/consumers/chuong.py": [
            (34, 52, "The default notification map includes uploaded and confirmed result files, not revoked files."),
        ],
        "src/clinicai/events/consumers/dong_thoi_gian.py": [
            (90, 103, "Timeline detail allowlist includes confirmation and send events but not revoke reason/detail."),
            (215, 239, "The timeline consumer still writes an event label for revoke, so audit trace is not absent."),
        ],
        "src/tests/services/test_xac_nhan_tep_ket_qua_db.py": [
            (945, 1007, "The test covers revoke before sending and the review boundary."),
            (1589, 1679, "The test covers that a revoked file cannot be sent later; it never marks gui_luc before revoking."),
        ],
    }


def finding_definitions() -> list[dict]:
    worker = {
        "id": "INF-022",
        "title": "Dead-letter event và timer chưa có khôi phục theo từng bản ghi trong ứng dụng",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "worker_dead_letter_recovery",
        "summary": "Khi callback event hết lượt, event_delivery chuyển DEAD và có thể chặn version mới hơn của cùng aggregate; timer có thể chuyển CHET. Ops hiện trả số lượng theo consumer và health tổng hợp. Event có actor được gửi thông báo theo vai, còn timer chỉ báo khi chi_tiet.nguoi_goi có giá trị; các tín hiệu này không cung cấp màn xem lỗi của từng delivery, giao người phụ trách, hay thao tác retry/reconcile an toàn. Lệnh replay chỉ dựng projection và không thay đổi event_delivery.",
        "trigger": "Một callback event hết retry hoặc một timer hết retry/không có handler; nhân viên nhận được thông báo nếu điều kiện actor/nguoi_goi được đáp ứng, rồi cần xác định và khôi phục đúng hàng đợi.",
        "impact": "Event DEAD cũ có thể chặn các sự kiện sau của cùng đối tượng; timer CHET có thể làm lời nhắc không chạy. Trong các route vận hành và replay đã rà không có hành động phục hồi theo bản ghi, nên việc khôi phục phải đi qua kỹ thuật hoặc quy trình ngoài ứng dụng. Đây là thiếu sót về khả năng xử lý, không phải thiếu mọi cảnh báo hay bằng chứng đang có sự cố production.",
        "recommendation": "Tạo hàng đợi xử lý theo clinic với event/timer đã làm sạch thông tin, consumer/loại việc, số lần thử, lỗi gần nhất, tuổi, đối tượng bị chặn, owner và trạng thái acknowledged. Chỉ cho retry/replay sau khi có guard idempotency, fencing và audit thao tác; tách projection rebuild khỏi giao lại tác vụ.",
        "acceptance": "Tạo event DEAD và timer CHET trong DB dùng một lần; người có quyền xem đúng bản ghi và nguyên nhân, giao owner, sửa điều kiện, retry an toàn; xác nhận event kế tiếp chỉ chạy sau khi event cũ hoàn tất; tenant khác không đọc/điều khiển được; mọi thao tác có audit.",
        "validation": {
            "method": "static_worker_timer_dead_letter_to_ops_and_replay_trace_on_pinned_main",
            "command": None,
            "result": "Exact-main trace confirms event/timer terminal state and aggregate Ops/health views. Existing event DEAD notifications are role-level and conditional; timer alerting requires nguoi_goi. Projection replay deliberately does not touch event_delivery. The reviewed Ops and timer paths expose no per-record retry or assignment action.",
            "limitations": "No DB, API, UI, retry, fault-injection or production test was run. The repository may be complemented by external runbooks or direct operator procedures. Event notification exists when actor_staff_id is present; timer notification exists when chi_tiet.nguoi_goi is present. Finding concerns in-product row-level ownership and safe recovery.",
        },
        "related_tests": [
            {"path": "src/tests/services/test_event_worker_db.py", "scope": "Confirms callback failure reaches DEAD and increments an aggregate consumer count; does not test row-level recovery."},
            {"path": "src/tests/services/test_hen_gio_db.py", "scope": "Confirms stale lease returns to CHO; does not test CHET operator management."},
            {"path": "src/tests/test_health_su_kien.py", "scope": "Asserts aggregate health counters produce reasons; does not test recovery actions."},
        ],
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PINNED_SHA,
            "status": "still_present_on_main",
            "note": "Round 18 exact-main review. Existing alerts and aggregate counters are acknowledged; the finding is the missing per-record in-product recovery path.",
            "production_verified": False,
        },
        "dedup_note": "Khác INF-017 (DEAD alert tự hết sau 24 giờ) và INF-018 (lease reclaim vượt retry cap): finding này nói về owner và thao tác xử lý theo bản ghi sau khi đã vào DEAD/CHET. Khác INF-011 vì queue POS, đối tượng nghiệp vụ và đường retry là khác; không khẳng định mọi alert đều thiếu.",
    }
    finance = {
        "id": "FIN-016",
        "title": "Hoàn tiền mặc định gộp hình thức của giao dịch thu hỗn hợp",
        "severity": "LOW",
        "evidence_level": "confirmed_static",
        "category": "refund_tender_attribution",
        "summary": "Payment cycle có thể lưu breakdown nhiều tender, nhưng hinh_thuc_chinh chọn TRANSFER nếu bất kỳ phần thu nào là chuyển khoản. Query tiền thừa lấy hinh_thuc_hieu_luc dạng scalar thay vì phan_thu_hieu_luc. Khi request hoàn tiền để trống hình thức, HoanTienService gắn toàn bộ số thừa của dòng/cycle vào scalar đó. Ví dụ 100.000 tiền mặt + 50.000 chuyển khoản có thể được hiển thị/ghi mặc định thành 150.000 chuyển khoản. Tổng amount không bị chứng minh sai; sai lệch là ở breakdown đối soát tender gốc.",
        "trigger": "Một payment cycle thu bằng nhiều hình thức, sau đó dòng dịch vụ bị hủy/không làm hoặc dịch vụ khám bị bỏ; người dùng bấm hoàn tiền thừa với lựa chọn mặc định ‘Như khách đã trả’.",
        "impact": "Báo cáo và thao tác hoàn có thể gán toàn bộ tiền thừa vào một phương thức, khiến nhân viên không đối chiếu được số tiền hoàn với từng tender gốc. Chưa chứng minh mất tiền, sai tổng tiền hoặc giao dịch thực tế bị ghi sai; override một hình thức vẫn có thể được chọn thủ công.",
        "recommendation": "Khi để mặc định, lấy breakdown hiệu lực từ phan_thu_hieu_luc và phân bổ khoản hoàn theo từng tender gốc trong cùng payment cycle; nếu nghiệp vụ cho phép hoàn khác tender, yêu cầu chọn rõ và ghi lý do. UI phải hiển thị breakdown thực sự được gửi và tổng các phần phải bằng số hoàn.",
        "acceptance": "Với payment cycle 100.000 CASH + 50.000 TRANSFER và toàn bộ 150.000 tiền thừa, mặc định tạo đúng 100.000 CASH + 50.000 TRANSFER; override ghi riêng lựa chọn và không làm đổi tổng; test cả checkout và quầy, đồng thời đối chiếu báo cáo tiền mặt/chuyển khoản.",
        "validation": {
            "method": "static_mixed_tender_to_excess_refund_trace_on_pinned_main",
            "command": None,
            "result": "Exact-main source trace connects mixed-tender storage, scalar effective-method lookup, default refund grouping, optional API override and the UI default. The DB test creates and verifies a 100k/50k mixed cycle; nearest refund tests cover single-tender defaults only.",
            "limitations": "No DB refund reproduction or production accounting data was checked. The inferred discrepancy concerns method attribution; no amount loss, duplicate refund or cash-balance mismatch is established.",
        },
        "related_tests": [
            {"path": "src/tests/services/test_thu_nhieu_hinh_thuc_db.py", "scope": "Persists and displays a 100k CASH + 50k TRANSFER cycle but does not refund its excess."},
            {"path": "src/tests/services/test_mo_phong_dong_tien_db.py", "scope": "Default excess refund is covered for a single TRANSFER method; no mixed-tender refund case."},
        ],
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PINNED_SHA,
            "status": "still_present_on_main",
            "note": "Round 18 exact-main static trace; contract and accounting effect are limited to tender-method attribution, not total refund amount.",
            "production_verified": False,
        },
        "dedup_note": "Khác FIN-004 (làm tròn số tiền hoàn) và FIN-012 (cờ khớp là phép đồng nhất): đây là breakdown CASH/TRANSFER của một khoản hoàn mặc định, không phải sai tổng hoặc phép kiểm tra tautology.",
    }
    clinical = {
        "id": "CLIN-036",
        "title": "Thu hồi tệp đã đánh dấu gửi chưa tạo luồng đính chính có người phụ trách",
        "severity": "MEDIUM",
        "evidence_level": "design_gap",
        "category": "clinical_result_correction_handoff",
        "summary": "Tệp external ở HOP_LE có thể được thu hồi trước khi vòng đọc bắt đầu; thao tác này không kiểm tra gui_luc, chuyển trạng thái sang THU_HOI và phát result_file.revoked. Event được gửi tới timeline và VONG_DOC, không tới CHUONG; tệp bị thu hồi biến khỏi danh sách kết quả còn hiệu lực. Nếu CSKH đã đánh dấu gửi thủ công trước đó, code slice không tạo thông báo đính chính, yêu cầu liên hệ lại hay owner cho người nhận. gui_luc chỉ là staff confirmation, không chứng minh khách đã nhận tệp.",
        "trigger": "CSKH đã ghi nhận gui_luc cho tệp kết quả external, sau đó người có quyền thu hồi tệp trong lúc phiên đọc kết quả chưa bắt đầu/đóng.",
        "impact": "Nếu khách thực sự đã nhận bản cũ, họ có thể tiếp tục dựa vào bản đó trong khi ClinicAI chỉ bỏ file khỏi danh sách hiện hành. Dòng timeline vẫn ghi nhận sự kiện thu hồi, nên đây là khoảng hở corrective handoff/owner chứ không phải mất audit event. Chính sách nghiệp vụ về thu hồi sau gửi cần được xác định.",
        "recommendation": "Định nghĩa rõ state machine sau khi đã gửi: hoặc chặn thu hồi trực tiếp và chuyển sang quy trình đính chính, hoặc tạo ngay task ưu tiên cao cho CSKH với owner/đích hạn, trạng thái liên hệ bệnh nhân, lý do thu hồi và liên kết bản thay thế. Giữ bản cũ ở lịch sử với cảnh báo đã thu hồi và audit đầy đủ.",
        "acceptance": "Test HOP_LE → xác nhận đã gửi → thu hồi: hệ thống không được kết thúc ở trạng thái chỉ ẩn file. Phải tạo corrective work item có clinic, owner/role, deadline, trạng thái xác nhận liên hệ và liên kết bản thay thế; hoặc từ chối chuyển trạng thái và yêu cầu quy trình đính chính. Kiểm tra cùng clinic, quyền và timeline.",
        "validation": {
            "method": "static_result_file_revoke_after_manual_send_to_notification_and_timeline_trace_on_pinned_main",
            "command": None,
            "result": "Exact-main trace confirms revoke is allowed before review begins without reading gui_luc, while the current-file list excludes revoked files. The event keeps a timeline label but has no CHUONG consumer. Existing DB tests cover revoke before send and block send after revoke, not send-then-revoke.",
            "limitations": "gui_luc records a staff confirmation of a manual send; it does not prove delivery to the patient. No DB repro, patient workflow test or production behavior was checked. Whether revocation after send must create a correction task is a policy/design decision; impact is conditional on the patient having received the earlier file.",
        },
        "related_tests": [
            {"path": "src/tests/services/test_xac_nhan_tep_ket_qua_db.py", "scope": "Tests revoke before review and the review-state guard; another case blocks sending after revoke, but no test marks gui_luc before revoke."},
        ],
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PINNED_SHA,
            "status": "still_present_on_main",
            "note": "Round 18 static/design-gap review. The code records a revoke event; patient receipt and the intended correction policy are not proven.",
            "production_verified": False,
        },
        "dedup_note": "Khác CLIN-019: CLIN-019 là marker/H7 của kết quả đối tác bị thu hồi trước khi bác sĩ đọc; CLIN-036 là luồng đính chính sau khi nhân viên đã ghi nhận gửi tệp cho khách. Cùng chủ đề thu hồi nhưng khác trigger, consumer và người cần handoff.",
    }
    return [worker, finance, clinical]


def main() -> None:
    actual_sha = subprocess.check_output(["git", "-C", str(SNAPSHOT), "rev-parse", "HEAD"], text=True).strip()
    if actual_sha != PINNED_SHA:
        raise SystemExit(f"Pinned source mismatch: expected {PINNED_SHA}, got {actual_sha}")

    manifest = read_json("MAIN-PHAM-VI.json")
    if manifest["sha"] != PINNED_SHA:
        raise SystemExit("MAIN-PHAM-VI.json does not reference the pinned source SHA")
    by_path = {row["path"]: row for row in manifest["files"]}
    ranges = review_ranges()
    definitions = finding_definitions()
    existing = read_json("PHAT-HIEN.json")
    ids = {row["id"] for row in existing}
    collisions = sorted(ids.intersection(row["id"] for row in definitions))
    if collisions:
        raise SystemExit(f"Round 18 finding IDs already exist: {collisions}; refusing to append")

    status_rank = {"inventoried": 0, "scanned": 1, "traced": 2, "read": 3, "excluded": 4}
    coverage_files = []
    for path, spans in ranges.items():
        if path not in by_path:
            raise SystemExit(f"Reviewed source is missing from the main path ledger: {path}")
        lines, digest = source(path)
        row = by_path[path]
        if row["sha256"] != digest or row["lines"] != len(lines):
            raise SystemExit(f"Main path ledger fingerprint mismatch: {path}")
        old_status = row["status"]
        status = "traced" if old_status == "scanned" else old_status
        row["status"] = status
        method = "Round 18 targeted semantic trace; not a full-file read. " + "; ".join(
            f"{start}-{end}" for start, end, _ in spans
        )
        row["method"] = f"{row.get('method', '')} | {method}".strip(" |")
        coverage_files.append({
            "path": path,
            "status": status,
            "prior_status": old_status,
            "read_level_this_round": "targeted_semantic_trace",
            "full_file_read_this_round": False,
            "ranges": [{"start": start, "end": end, "purpose": purpose} for start, end, purpose in spans],
            "sha256": digest,
            "line_count": len(lines),
        })

    for finding in definitions:
        spans = ranges
        used_paths = set()
        # The evidence table is narrowly scoped per finding, avoiding unrelated source rows.
        if finding["id"] == "INF-022":
            used_paths = {
                "src/clinicai/events/worker.py", "src/clinicai/api/v1/routers/ops.py",
                "src/clinicai/events/phat_lai.py", "src/clinicai/events/hen_gio.py",
                "src/clinicai/api/v1/health.py", "supabase/migrations/20260923000001_domain_event.sql",
                "src/tests/services/test_event_worker_db.py", "src/tests/services/test_hen_gio_db.py",
                "src/tests/test_health_su_kien.py",
            }
        elif finding["id"] == "FIN-016":
            used_paths = {
                "src/clinicai/services/phan_thu.py", "src/clinicai/services/tien_thua_service.py",
                "src/clinicai/services/hoan_tien_service.py", "supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql",
                "src/clinicai/api/v1/routers/dispatch.py", "src/dashboard/app/api/reception/checkout/route.ts",
                "src/dashboard/app/(dashboard)/_lam-viec/NutHoanTienThua.tsx",
                "src/tests/services/test_thu_nhieu_hinh_thuc_db.py",
                "src/tests/services/test_mo_phong_dong_tien_db.py",
            }
        else:
            used_paths = {
                "src/clinicai/services/tep_ket_qua_service.py",
                "supabase/migrations/20260920000005_xac_nhan_tep_ket_qua.sql",
                "src/clinicai/events/catalogue.py", "src/clinicai/events/consumers/chuong.py",
                "src/clinicai/events/consumers/dong_thoi_gian.py",
                "src/tests/services/test_xac_nhan_tep_ket_qua_db.py",
            }
        evidence_rows = []
        for path in sorted(used_paths):
            for start, end, detail in ranges[path]:
                evidence_rows.append(evidence(path, start, end, detail))
        finding["evidence"] = [
            {k: item[k] for k in ("path", "line", "end_line", "sha256", "detail")}
            for item in evidence_rows
        ]
        finding["source_hashes"] = {
            path: source(path)[1] for path in sorted(used_paths)
        }
        finding["main_validation"]["evidence"] = evidence_rows

    write_json("MAIN-PHAM-VI.json", manifest)
    write_json("PHAT-HIEN.json", existing + definitions)
    write_json("blocks/round18_lifecycle_worker_finance.findings.json", definitions)
    write_json("blocks/round18_lifecycle_worker_finance.coverage.json", {
        "schema_version": 1,
        "audit": "round18_lifecycle_worker_finance",
        "snapshot": {"path": str(SNAPSHOT), "sha": PINNED_SHA},
        "review_mode": "static_read_only_cross_layer_trace",
        "scope": [
            "result-file revoke after staff-recorded patient send",
            "event and timer dead-letter ownership and recovery surface",
            "mixed-tender payment-cycle excess refund attribution",
        ],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "All reviewed paths were already present in the source ledger. Three previously scanned paths were upgraded to targeted traced; no full-file read is claimed for this round.",
        "files": coverage_files,
    })

    checks = read_json("KIEM-CHUNG.json")
    known = {(row["id"], row["path"]) for row in checks["checks"]}
    for finding in definitions:
        for ev in finding["main_validation"]["evidence"]:
            key = (finding["id"], ev["path"])
            if key not in known:
                checks["checks"].append({"id": finding["id"], "path": ev["path"], "valid": True})
                known.add(key)
    write_json("KIEM-CHUNG.json", checks)

    state = read_json("STATE.json")
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    all_counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    findings = existing + definitions
    severity = Counter(row["severity"] for row in findings)
    evidence_levels = Counter(row["evidence_level"] for row in findings)
    main_status = Counter(row["main_validation"]["status"] for row in findings)

    state["updated_at"] = now
    state["phase"] = "round18_lifecycle_worker_finance_checkpoint"
    state["next_action"] = (
        "Tiếp tục đọc các đường luồng còn mỏng; ưu tiên kiểm thử DB dùng một lần cho hoàn tiền tender hỗn hợp, "
        "thu hồi tệp sau khi xác nhận gửi và dead-letter event/timer; sau đó mở lát mới ở các module chưa có semantic read. "
        "Bám exact-main, cập nhật ledger theo file thật sự đọc và không suy rộng thành lỗi production. Full source audit remains incomplete."
    )
    state["report_status"] = "v0.39_140_findings_HTML_and_portable_ZIP_pending_final_QA; full source audit incomplete"
    summary = state["summary"]
    summary["findings"] = len(findings)
    summary["severity"] = {key: severity.get(key, 0) for key in ("HIGH", "MEDIUM", "LOW")}
    summary["evidence_levels"] = {key: evidence_levels.get(key, 0) for key in ("reproduced_local", "design_gap", "confirmed_static", "hypothesis")}
    summary["main_status"] = {key: main_status.get(key, 0) for key in ("still_present_on_main", "partially_addressed_on_main", "addressed_on_main")}
    summary["main_coverage"] = {key: all_counts.get(key, 0) for key in ("inventoried", "read", "traced", "scanned", "excluded")}
    summary["main_read_files"] = all_counts["read"]
    summary["main_partial_traces"] = all_counts["traced"]
    summary["code_like_source_files"] = {
        "definition": "Pinned-tree paths with common source-code/web/sql/shell suffixes used by the report generator; includes app, tests, tooling and styles, not only runtime code.",
        "total": len(code_files),
        "coverage": {key: code_counts.get(key, 0) for key in ("inventoried", "traced", "scanned", "read")},
        "traced_is_partial": True,
    }
    summary["reviewed_slice_v039"] = "round18_lifecycle_worker_finance; 3 domain slices with targeted traces across 25 files; CLIN-036 design_gap, INF-022 and FIN-016 confirmed_static; no app/DB tests run. Three scanned paths upgraded to traced; no full-file reads claimed."
    summary["new_findings_v039"] = ["INF-022", "FIN-016", "CLIN-036"]
    state["blocks"]["round18_lifecycle_worker_finance"] = {
        "status": "round18 static slices triaged; CLIN-036, INF-022 and FIN-016 added",
        "scope": "Clinical file revoke after staff-recorded send; event/timer dead-letter recovery; mixed-tender excess refund attribution",
        "artifacts": "blocks/round18_lifecycle_worker_finance.md; blocks/round18_lifecycle_worker_finance.findings.json; blocks/round18_lifecycle_worker_finance.coverage.json",
        "findings": "CLIN-036 MEDIUM design_gap; INF-022 MEDIUM and FIN-016 LOW confirmed_static; all still_present_on_main.",
        "next": "Verify the three triggers with isolated DB/API/UI tests and confirm policy for post-send result correction; continue unread modules after the targeted probes.",
    }
    state["artifacts"]["qa"] = "HTML-QA.json; v0.39 pending rebuild and desktop/mobile browser QA; report-only, not ClinicAI application validation."
    state["artifacts"]["integration_script"] = "integrate_round18.py; round18 evidence/coverage in blocks/round18_*; prior checkpoints retained."
    state["artifacts"]["bundle_integrity"] = "Pending v0.39 package regeneration and verification after HTML QA."
    state["artifacts"]["html_sha256"] = "pending v0.39 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.39 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.39 package verification"
    state["runtime_summary"]["audit_report_qc"] = "Pending v0.39 report regeneration and desktop/mobile QA; no ClinicAI application test was run for round 18."
    write_json("STATE.json", state)

    print(json.dumps({
        "new_findings": [row["id"] for row in definitions],
        "findings_total": len(findings),
        "severity": dict(severity),
        "evidence_levels": dict(evidence_levels),
        "main_status": dict(main_status),
        "coverage": dict(all_counts),
        "code_like_total": len(code_files),
        "code_like_coverage": dict(code_counts),
        "updated_at": now,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
