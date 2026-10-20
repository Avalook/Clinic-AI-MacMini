"""Integrate the Round 47 read-only exact-main review into audit artifacts."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path("/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini")
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
CODE_SUFFIXES = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html",
}


def load(name: str):
    return json.loads((ROOT / name).read_text())


def save(name: str, data) -> None:
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def source(path: str) -> tuple[bytes, list[str]]:
    raw = subprocess.check_output(["git", "show", f"{SHA}:{path}"], cwd=REPO)
    return raw, raw.decode("utf-8").splitlines()


def proof(path: str, start: int, end: int, detail: str) -> dict:
    raw, lines = source(path)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid pinned range {path}:{start}-{end} ({len(lines)} lines)")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "excerpt": "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1)),
        "detail": detail,
        "lines": len(lines),
    }


def add_proofs(finding: dict, specs: list[tuple[str, int, int, str]]) -> list[dict]:
    added = []
    for path, start, end, detail in specs:
        item = proof(path, start, end, detail)
        key = (path, start, end)
        if not any((x["path"], x["line"], x["end_line"]) == key for x in finding["evidence"]):
            finding["evidence"].append({k: item[k] for k in ("path", "line", "end_line", "detail")})
        main_items = finding["main_validation"].setdefault("evidence", [])
        if not any((x["path"], x["line"], x["end_line"]) == key for x in main_items):
            main_items.append({k: item[k] for k in ("path", "line", "end_line", "sha256", "excerpt")})
        finding.setdefault("source_hashes", {})[path] = item["sha256"]
        added.append(item)
    return added


def append_once(text: str, addition: str) -> str:
    return text if addition in text else text + addition


def append_item_once(items: list, value: str) -> None:
    if value not in items:
        items.append(value)


def main() -> None:
    findings = load("PHAT-HIEN.json")
    by_id = {item["id"]: item for item in findings}

    complaint_specs = [
        ("src/dashboard/app/(dashboard)/customers/PhanHoiKhach.tsx", 75, 98,
         "The client POST has no idempotency key; a rejected fetch skips the following loading reset, while a manual retry after reload can repeat the intent."),
        ("src/dashboard/app/api/cskh/phan-hoi/route.ts", 12, 20,
         "The BFF forwards the complaint POST body without forwarding an idempotency key."),
        ("src/clinicai/api/v1/routers/cskh.py", 625, 639,
         "The authenticated route calls the complaint service without an idempotency guard or command identity."),
        ("src/clinicai/services/phan_hoi_khach_service.py", 45, 75,
         "Each successful call inserts a fresh complaint row and a corresponding event_log row in its transaction."),
        ("supabase/migrations/20260809000007_hanh_trinh_cskh_bam_duoc_het.sql", 75, 113,
         "The complaint table schema has no unique client command/deduplication key."),
        ("src/tests/unit/test_phan_hoi_khach.py", 67, 100,
         "Existing unit tests cover validation, clinic membership and insertion but not replay after a committed write; read only, not run."),
    ]
    preview_specs = [
        ("src/dashboard/app/(dashboard)/settings/LuatBacSiCard.tsx", 81, 109,
         "Preview state is keyed only by service; changing the calculation method/month starts a request but leaves the prior same-service result in state, and a rejected fetch is swallowed."),
        ("src/dashboard/app/(dashboard)/settings/LuatBacSiCard.tsx", 293, 316,
         "The preview is labelled as applying to the currently selected calculation method, and Save remains enabled while preview data is pending or failed."),
        ("src/dashboard/app/api/booking-rules/doctor/route.ts", 20, 29,
         "The BFF proxies the doctor-rule preview query."),
        ("src/clinicai/api/v1/routers/config.py", 1104, 1120,
         "The backend endpoint accepts the preview method and month parameters."),
        ("src/clinicai/services/luat_bac_si_service.py", 195, 225,
         "The backend computes the preview from the requested service/calculation parameters; the mismatch is in the client freshness/label state."),
        ("src/tests/unit/test_cua_ngo_ghi_moi.py", 935, 1059,
         "Existing tests cover service preview calculations, not a UI method-change/network-rejection freshness state; read only, not run."),
    ]

    clin058 = {
        "id": "CLIN-058",
        "title": "Gửi lại phản hồi CSKH sau khi mất phản hồi có thể tạo bản ghi trùng",
        "severity": "LOW",
        "evidence_level": "confirmed_static",
        "category": "cskh/idempotency-event-integrity",
        "summary": "POST ghi phản hồi khách không mang khóa idempotency từ UI qua BFF tới service. Mỗi lần gọi hợp lệ chèn một dòng phan_hoi_khach và một event_log mới. Nếu lần đầu đã commit nhưng phản hồi bị mất, thao tác gửi lại sau khi tải lại có thể ghi bản thứ hai cho cùng một ý định.",
        "trigger": "Nhân viên gửi phản hồi/khiếu nại; backend commit cả phản hồi và event_log nhưng client không nhận được response. Sau khi tải lại hoặc mở lại form, nhân viên gửi lại cùng nội dung.",
        "impact": "Có thể tạo hai hồ sơ CSKH và hai tín hiệu hoạt động cho một ý định, khiến hàng đợi theo dõi/đếm số phản hồi cần đối chiếu thủ công. Không có bằng chứng đã xảy ra trên production hoặc bệnh nhân nhận thông báo trùng.",
        "evidence": [],
        "validation": {
            "method": "exact_main_static_client_to_transaction_and_schema_trace",
            "command": None,
            "result": "Đối chiếu UI → BFF → FastAPI → service transaction và schema; không thấy idempotency key/command receipt. Unit test hiện có không kiểm retry sau commit.",
            "limitations": "Static exact-main; chưa fault-inject mất response, chạy DB/API, kiểm relay hay production. Đây là khả năng có điều kiện, không phải incident đã quan sát.",
        },
        "recommendation": "Tạo command ID ổn định trước lần gửi đầu, persist receipt cùng transaction và trả lại cùng kết quả khi replay; nếu không có receipt thì yêu cầu client giữ trạng thái intent để retry có định danh.",
        "acceptance": "Mô phỏng commit thành công rồi làm mất response: replay cùng command trả cùng receipt và chỉ có một phản hồi, một event_log; cùng key khác payload bị từ chối; hai ý định riêng biệt vẫn tạo hai bản ghi.",
        "alignment": [
            "Reality dễ nhìn thấy hơn: số phản hồi và dấu vết hoạt động phản ánh số ý định thực.",
            "Lỗi lặp lại biến thành cải tiến hệ thống: retry sau mất phản hồi không nhân đôi việc CSKH.",
        ],
        "related_tests": [
            "src/tests/unit/test_phan_hoi_khach.py — đọc, không chạy; kiểm validation/clinic/insertion, không kiểm replay sau commit.",
        ],
        "source_hashes": {},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "Exact-main static trace confirms one valid call inserts a fresh complaint row and event_log row; no retry key/receipt in the client-to-service path. No runtime or production reproduction.",
            "evidence": [],
            "production_verified": False,
        },
        "related_findings": ["FE-023", "CLIN-024", "FIN-003"],
    }
    add_proofs(clin058, complaint_specs)
    if "CLIN-058" not in by_id:
        findings.append(clin058)

    fe028 = {
        "id": "FE-028",
        "title": "Preview luật bác sĩ có thể cũ nhưng vẫn được lưu theo cách tính mới",
        "severity": "LOW",
        "evidence_level": "confirmed_static",
        "category": "settings/stale-decision-preview",
        "summary": "Thẻ luật bác sĩ gắn số preview với mã dịch vụ, không gắn với cách tính/tháng. Khi đổi cách tính cho cùng dịch vụ, request preview mới chạy nhưng số cũ vẫn hiện; nếu request lỗi, lỗi bị bỏ qua. Nút lưu vẫn bật và nội dung giải thích gọi con số ấy là kết quả của cách tính đang chọn.",
        "trigger": "Quản lý xem preview cho một dịch vụ, đổi cách tính hoặc số tháng, rồi preview mới đang tải hoặc bị lỗi; vẫn bấm Lưu luật.",
        "impact": "Người quản lý có thể quyết định theo số hồ sơ phân loại khách mới của cách tính trước đó trong khi lưu cấu hình cách tính mới. Backend vẫn tính theo payload hiện tại; finding này là lỗi thông tin quyết định ở UI, không phải sai phép tính lưu.",
        "evidence": [],
        "validation": {
            "method": "exact_main_static_ui_to_preview_endpoint_trace",
            "command": None,
            "result": "UI state/filter theo service nhưng không theo cach_tinh/so_thang; fetch rejection bị nuốt; Save chỉ bị disable khi đang lưu. Backend nhận và tính theo tham số hiện tại.",
            "limitations": "Static exact-main; chưa chạy browser, cố ý làm chậm/từ chối preview hoặc kiểm production. Không kết luận backend lưu sai cấu hình.",
        },
        "recommendation": "Gắn preview với đầy đủ tuple service + method + month; đánh dấu đang tải/lỗi và không cho lưu dựa trên preview cũ, hoặc yêu cầu người dùng xác nhận rõ cấu hình không có preview mới.",
        "acceptance": "Đổi method/month làm preview cũ biến mất hoặc bị đánh dấu cũ; khi request lỗi có trạng thái và hành động thử lại; không thể hiểu nhầm số cũ là kết quả của lựa chọn mới.",
        "alignment": [
            "Quyết định dựa trên bằng chứng tốt hơn: preview luôn khớp chính sách sắp lưu.",
            "Unknown ngắn hơn: lỗi preview được biểu thị thay vì để lại một con số trông như hiện tại.",
        ],
        "related_tests": [
            "src/tests/unit/test_cua_ngo_ghi_moi.py:935–1059 — đọc, không chạy; kiểm service preview, không kiểm UI freshness khi đổi method/month.",
        ],
        "source_hashes": {},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "Exact-main static trace confirms preview state is keyed by service only while query depends on method/month and Save remains available. No browser or production validation.",
            "evidence": [],
            "production_verified": False,
        },
        "related_findings": ["FE-023", "OPS-004"],
    }
    add_proofs(fe028, preview_specs)
    if "FE-028" not in by_id:
        findings.append(fe028)

    fe23_specs = [
        ("src/dashboard/app/(dashboard)/customers/PhanHoiKhach.tsx", 75, 98,
         "Complaint submission resets its pending flag only after fetch resolves; a network rejection can leave the form pending."),
        ("src/dashboard/app/(dashboard)/settings/new-user/NewUserForm.tsx", 36, 60,
         "New-user form sets loading before fetch and parses the response without catch/finally."),
        ("src/dashboard/app/(dashboard)/settings/PhamViViTriCard.tsx", 60, 79,
         "Role/location permission toggle sets pending before fetch and clears it only after fetch resolves."),
        ("src/dashboard/app/(dashboard)/settings/LuatBacSiCard.tsx", 111, 156,
         "Doctor-rule create/delete requests do not handle rejected fetch promises; the create button can remain pending and delete has no request-error state."),
    ]
    fe23 = by_id["FE-023"]
    fe23["summary"] = append_once(fe23["summary"], " Round 47 xác nhận cùng lỗi cleanup pending ở form phản hồi CSKH, tạo user, quyền phạm vi vị trí và thao tác luật bác sĩ; không gộp các form đã có catch/finally.")
    fe23["trigger"] = append_once(fe23["trigger"], " Thêm các request tạo phản hồi khách, user mới, đổi quyền phạm vi vị trí hoặc lưu/gỡ luật bác sĩ bị reject ở tầng mạng.")
    fe23["impact"] = append_once(fe23["impact"], " Một số thao tác quản trị/CSKH có thể trông như đang chạy hoặc không có trạng thái lỗi, buộc tải lại trang để tiếp tục; không có bằng chứng ghi dữ liệu sai hay bypass quyền.")
    fe23["validation"]["result"] = append_once(fe23["validation"]["result"], " Round 47 đọc bốn form/settings nêu trên; các request bị reject trước đoạn dọn pending không có catch/finally tương ứng.")
    fe23["validation"]["limitations"] = append_once(fe23["validation"]["limitations"], " Chưa mô phỏng network rejection trong browser; các form DayNoi/LamThem có catch/finally nên không được tính vào finding này.")
    fe23["main_validation"]["note"] = append_once(fe23["main_validation"]["note"], " Round 47 mở rộng tới complaint, tạo user, phạm vi vị trí và luật bác sĩ; loại trừ các form có catch/finally.")
    append_item_once(fe23.setdefault("related_tests", []), "Round 47: related UI sources read from pinned main; no network-rejection component test was identified or run.")
    add_proofs(fe23, fe23_specs)

    fe26_specs = [
        ("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/LichSuSuaPhieu.tsx", 55, 66,
         "The read function clears the error and awaits fetch without catch; a rejected promise never sets a visible error."),
        ("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/LichSuSuaPhieu.tsx", 103, 105,
         "With null history and no error, the panel continues to render Đang đọc… indefinitely after a network rejection."),
    ]
    fe26 = by_id["FE-026"]
    fe26["summary"] = append_once(fe26["summary"], " Round 47 bổ sung panel lịch sử sửa phiếu khám: fetch reject không được bắt, giữ dong=null và loi=null nên nhãn Đang đọc… không kết thúc.")
    fe26["trigger"] = append_once(fe26["trigger"], " Mở lịch sử sửa phiếu khám khi request đọc bị từ chối ở tầng mạng.")
    fe26["impact"] = append_once(fe26["impact"], " Nhân viên không biết lịch sử không tải được và không có trạng thái lỗi/thử lại trong panel; chưa có bằng chứng dữ liệu lịch sử sai.")
    fe26["validation"]["result"] = append_once(fe26["validation"]["result"], " Exact-main source cho thấy request await không có catch và panel giữ trạng thái spinner khi dong còn null.")
    fe26["validation"]["limitations"] = append_once(fe26["validation"]["limitations"], " Chưa fault-inject browser/network; kết luận là trạng thái tĩnh từ luồng promise và JSX.")
    fe26["main_validation"]["note"] = append_once(fe26["main_validation"]["note"], " Round 47 thêm panel lịch sử sửa phiếu với spinner không kết thúc khi fetch reject.")
    add_proofs(fe26, fe26_specs)

    fe02_specs = [
        ("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/HanhTrinhLuot.tsx", 47, 63,
         "Refresh rejection is converted to null and leaves prior journey state untouched, without a freshness/error marker."),
        ("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/HanhTrinhLuot.tsx", 71, 71,
         "The whole panel is hidden when no initial journey data exists, so an initial read failure has no visible error state."),
    ]
    fe02 = by_id["FE-002"]
    fe02["summary"] = append_once(fe02["summary"], " Round 47 bổ sung HanhTrinhLuot trong phiếu khám: refresh lỗi bị đổi thành null và giữ hành trình cũ không có dấu freshness; lần tải đầu lỗi làm panel biến mất.")
    fe02["trigger"] = append_once(fe02["trigger"], " SSE-triggered hoặc lần tải ban đầu của HanhTrinhLuot bị lỗi mạng/API.")
    fe02["impact"] = append_once(fe02["impact"], " Nhân viên có thể tiếp tục đọc hành trình cũ như hiện tại; nếu chưa có dữ liệu lần đầu thì không thấy panel hay lỗi. Không có bằng chứng production stale window.")
    fe02["validation"]["result"] = append_once(fe02["validation"]["result"], " Exact-main source xác nhận request lỗi trở thành null, không cập nhật state và component trả null khi chưa có data.")
    fe02["validation"]["limitations"] = append_once(fe02["validation"]["limitations"], " Chưa fault-inject SSE/API hoặc xác định độ trễ tối đa trên runtime.")
    fe02["main_validation"]["note"] = append_once(fe02["main_validation"]["note"], " Round 47 mở rộng cùng stale-state pattern sang hành trình ngay trên phiếu khám.")
    add_proofs(fe02, fe02_specs)

    clin57_specs = [
        ("src/dashboard/app/(dashboard)/_lam-viec/DoiLichTaiCho.tsx", 132, 134,
         "The fast-reschedule command key is generated once per mounted popover component."),
        ("src/dashboard/app/(dashboard)/_lam-viec/DoiLichTaiCho.tsx", 176, 192,
         "The key combines the component session and target slot; closing the parent-controlled popover unmounts it, so reopening creates a new key for the same intent."),
        ("src/dashboard/app/(dashboard)/appointments/LichSapToiCuaKhach.tsx", 143, 155,
         "The caller conditionally mounts DoiLichTaiCho and keys it by appointment; closing sets mo=null, confirming a fresh component instance on reopen."),
        ("src/dashboard/app/(dashboard)/home/WeeklyAppointmentsTable.tsx", 1114, 1114,
         "The weekly appointment table also mounts the active fast-reschedule component; the route is not an unreferenced UI file."),
        ("src/dashboard/app/api/appointments/doi-lich-nhanh/route.ts", 48, 60,
         "BFF forwards the client key to the backend idempotency guard."),
        ("src/clinicai/api/v1/routers/booking.py", 781, 802,
         "Backend caches a response only under the supplied key; a new key starts a new command."),
        ("src/clinicai/services/booking_service.py", 1278, 1309,
         "The service proceeds through the reschedule/check-in transaction for a new command key."),
    ]
    clin57 = by_id["CLIN-057"]
    clin57["title"] = "Gửi lại lệnh đổi lịch có thể nhân đôi lịch sử và sự kiện đổi lịch"
    clin57["summary"] = append_once(clin57["summary"], " Round 47 xác nhận thêm đường đổi lịch nhanh có idempotency key theo vòng đời component; đóng rồi mở lại popover tạo component session/key mới cho cùng target, nên cache idempotency không nhận ra replay của cùng ý định.")
    clin57["trigger"] = append_once(clin57["trigger"], " Với popover đổi lịch nhanh: lệnh đầu đã commit nhưng mất response; người dùng đóng/mở popover rồi gửi lại cùng lịch hẹn và target.")
    clin57["impact"] = append_once(clin57["impact"], " Backend có thể xử lý lệnh mới và ghi lại dấu vết đổi lịch/sự kiện cho cùng target; không có bằng chứng tạo appointment thứ hai. Chi tiết side effect của fast path chưa được fault-inject trong lượt này.")
    clin57["validation"]["result"] = append_once(clin57["validation"]["result"], " Round 47 trace component key → conditional mount/unmount ở caller → BFF → idempotency receipt backend; cùng intent sau remount nhận key mới.")
    clin57["validation"]["limitations"] = append_once(clin57["validation"]["limitations"], " Chưa chạy browser, DB hoặc response-loss fault injection cho fast-reschedule path; không kết luận production occurrence hay duplicate appointment.")
    clin57["main_validation"]["note"] = append_once(clin57["main_validation"]["note"], " Round 47 xác nhận active callers remount fast-reschedule UI khi popover đóng/mở; key mới làm replay không khớp receipt cũ.")
    add_proofs(clin57, clin57_specs)

    fin03_specs = [
        ("src/dashboard/app/api/quay-thuoc/route.ts", 34, 55,
         "The pharmacy add-lines BFF forwards the POST body to FastAPI without an Idempotency-Key."),
        ("src/clinicai/api/v1/routers/quay_thuoc.py", 90, 116,
         "The authenticated add-lines route sends line data to the service without a command/idempotency wrapper."),
        ("src/clinicai/services/quay_thuoc_service.py", 529, 555,
         "A line with no prescription id follows the fresh-row insert path and generates a new UUID on each call."),
        ("src/tests/services/test_quay_thuoc_db.py", 64, 105,
         "Existing DB test covers add/edit and source separation, not response-loss replay; read only, not run."),
    ]
    fin03 = by_id["FIN-003"]
    fin03["summary"] = append_once(fin03["summary"], " Round 47 trace thêm BFF `/api/quay-thuoc`: thao tác them không forward Idempotency-Key; backend service tạo UUID mới cho dòng thiếu id trên mỗi lần gọi. Đây là đường giao diện khác cùng lỗi command idempotency, không phải finding mới.")
    fin03["validation"]["result"] = append_once(fin03["validation"]["result"], " Round 47 xác nhận thêm route quầy thuốc/BFF và test DB hiện hữu không bao phủ replay sau commit; bằng chứng reproduction cũ vẫn chỉ áp dụng cho probe đã ghi trong finding.")
    fin03["validation"]["limitations"] = append_once(fin03["validation"]["limitations"], " BFF/service path Round 47 chỉ đọc tĩnh; không chạy lại probe, browser, HTTP hoặc production.")
    fin03["main_validation"]["note"] = append_once(fin03["main_validation"]["note"], " Round 47 đối chiếu thêm BFF thao tác them; route hiện tại không forward key và service có fresh UUID insert path.")
    add_proofs(fin03, fin03_specs)

    sec11_specs = [
        ("src/dashboard/app/api/visits/[id]/theo-doi-thu-thuat/route.ts", 15, 22,
         "The BFF GET proxies the visit follow-up read without adding an assignment/capability check."),
        ("src/clinicai/api/v1/routers/theo_doi_thu_thuat.py", 19, 28,
         "The FastAPI GET depends on get_current_identity and passes the caller and visit id to the service."),
        ("src/clinicai/services/theo_doi_thu_thuat_service.py", 26, 59,
         "The query scopes by clinic_id and supplied visit_id, but does not test physician assignment for this read."),
        ("src/clinicai/services/theo_doi_thu_thuat_service.py", 71, 95,
         "The response includes procedure completion, follow-up decision, due date, and staff identity metadata."),
        ("src/dashboard/app/(dashboard)/tasks/TheoDoiThuThuat.tsx", 3, 10,
         "The UI describes the view as procedure follow-up information consumed in the CSKH screen."),
        ("src/dashboard/app/(dashboard)/tasks/TheoDoiThuThuat.tsx", 45, 60,
         "The UI calls the GET route and renders returned metadata when a procedure exists."),
        ("src/tests/services/test_theo_doi_thu_thuat.py", 47, 90,
         "Existing service tests cover CSKH read and restrict non-physician writes, not read assignment; read only, not run."),
    ]
    sec11 = by_id["SEC-011"]
    sec11["summary"] = append_once(sec11["summary"], " Round 47 bổ sung GET theo dõi sau thủ thuật: identity-only route đọc metadata theo visit_id cùng clinic, gồm hoàn thành thủ thuật/quyết định/hạn gọi và người liên quan, không kiểm phân công bác sĩ. Đây là cùng invariant object-level assignment, không có bằng chứng cross-clinic.")
    sec11["trigger"] = append_once(sec11["trigger"], " TKYK hoặc nhân viên cùng clinic có session gọi GET theo-doi-thu-thuat bằng visit_id ngoài phạm vi bác sĩ được phân.")
    sec11["impact"] = append_once(sec11["impact"], " Có thể đọc thêm metadata theo dõi hậu thủ thuật của lượt cùng clinic ngoài phân công; phạm vi clinic vẫn được service giữ. Chưa kiểm JWT/runtime hoặc production.")
    sec11["validation"]["result"] = append_once(sec11["validation"]["result"], " Round 47 trace BFF → identity-only router → clinic+visit SQL → response projection; test hiện hữu kiểm CSKH read/non-physician write, không kiểm assignment của GET.")
    sec11["validation"]["limitations"] = append_once(sec11["validation"]["limitations"], " Chưa chạy role/assignment JWT matrix; kết luận tĩnh cùng clinic, không phải truy cập chéo tenant.")
    sec11["main_validation"]["note"] = append_once(sec11["main_validation"]["note"], " Round 47 mở rộng tới metadata theo dõi sau thủ thuật; GET có clinic scope nhưng không có assignment guard riêng.")
    append_item_once(sec11.setdefault("related_tests", []), "src/tests/services/test_theo_doi_thu_thuat.py — đọc, không chạy; kiểm CSKH đọc và quyền ghi, không kiểm phân công ở GET.")
    add_proofs(sec11, sec11_specs)

    inf27_specs = [
        ("scripts/collect_ops_status.py", 16, 28,
         "The Ops service snapshot enumerates app/worker/support services but omits self-hosted Supabase db, auth, rest, realtime and gateway containers."),
        ("src/clinicai/services/ops_status.py", 317, 340,
         "Overall status gates only api/dashboard/caddy service-down states; a missing Supabase dependency is not an overall critical gate."),
        ("caddy/Caddyfile", 41, 48,
         "The public Caddy health endpoint responds statically and does not probe upstream Supabase readiness."),
        ("caddy/Caddyfile", 191, 194,
         "The public edge routes auth, REST and realtime traffic to the Supabase gateway."),
        ("docker/supabase/Caddyfile", 58, 61,
         "The Supabase gateway health endpoint is also a static success response."),
        ("monitoring/monitors.json", 11, 64,
         "Configured external monitors do not list GoTrue, PostgREST, Realtime or the Supabase gateway as distinct endpoints."),
    ]
    inf27 = by_id["INF-027"]
    inf27["summary"] = append_once(inf27["summary"], " Round 47 mở rộng: Ops không liệt kê các container Supabase self-hosted db/auth/rest/realtime/gateway; overall chỉ gate api/dashboard/caddy. Trong khi Caddy public expose auth/rest/realtime và health route ở edge/gateway trả 200 tĩnh, monitor list không theo dõi từng dependency.")
    inf27["trigger"] = append_once(inf27["trigger"], " GoTrue, PostgREST, Realtime hoặc gateway dừng/không sẵn sàng trong khi API/dashboard/Caddy, DB probe, backup và security checks khác vẫn đạt điều kiện healthy.")
    inf27["impact"] = append_once(inf27["impact"], " Nhân viên vận hành có thể thấy overall healthy dù đăng nhập, REST hoặc realtime không dùng được. Chưa chứng minh health endpoint qua gateway đang xanh khi từng upstream hỏng trong runtime.")
    inf27["validation"]["result"] = append_once(inf27["validation"]["result"], " Đối chiếu service inventory, overall rollup, public route, static health handlers và monitor list tại SHA ghim; không kiểm container/runtime.")
    inf27["validation"]["limitations"] = append_once(inf27["validation"]["limitations"], " Chưa dừng service hoặc gọi health checks; không biết lỗi production/tần suất/monitor semantics hiện tại.")
    inf27["recommendation"] = append_once(inf27["recommendation"], " Đưa từng dependency Supabase đang chạy vào snapshot/monitor; health probe phải kiểm khả năng phục vụ có xác thực phù hợp và tổng hợp trạng thái degraded/critical theo mức ảnh hưởng.")
    inf27["acceptance"] = append_once(inf27["acceptance"], " Snapshot synthetic từng dependency auth/rest/realtime/gateway down hoặc stale không được báo healthy; monitor chỉ xanh khi probe qua đường sử dụng thật xác nhận service sẵn sàng.")
    inf27["main_validation"]["note"] = append_once(inf27["main_validation"]["note"], " Round 47 xác nhận Supabase dependencies không có trong collector/overall gate và health endpoints tĩnh; static only, chưa quan sát outage.")
    add_proofs(inf27, inf27_specs)

    held_specs = [
        ("src/dashboard/lib/roster.ts", 511, 514,
         "Malformed/impossible ISO dates can normalize to another week; display-only candidate, no write or auth effect established."),
        ("src/dashboard/lib/roster.test.mts", 56, 72,
         "Current date tests cover normal inputs, not impossible calendar dates; read only, not run."),
        ("scripts/kiem-database-ngoai.sh", 156, 190,
         "An old, apparently uncalled external-DB helper uses a fixed temporary schema name and DROP SCHEMA CASCADE; active applicability is unconfirmed."),
        ("docker-compose.supabase.yml", 113, 115,
         "GoTrue redirect allowlist is wildcarded, but exact recovery-link behavior/active runtime acceptance was not traced; do not call this an exploit."),
        ("src/dashboard/app/(dashboard)/settings/clinic-config/CoSoPhong.tsx", 456, 467,
         "Room configuration has sequential save requests; whether partial persistence violates product policy is not established."),
        ("src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/ChonThuThuatBanKham.tsx", 47, 72,
         "A response-loss retry can make the UI report a not-started state; backend guard prevents a duplicate order in the reviewed path, so keep as UX candidate."),
    ]

    coverage_specs = complaint_specs + preview_specs + fe23_specs + fe26_specs + fe02_specs + clin57_specs + fin03_specs + sec11_specs + inf27_specs + held_specs
    coverage_by_path: dict[str, dict] = {}
    for path, start, end, detail in coverage_specs:
        item = proof(path, start, end, detail)
        row = coverage_by_path.setdefault(path, {
            "path": path,
            "sha256": item["sha256"],
            "lines": item["lines"],
            "read_ranges": [],
            "full_read": False,
            "outcomes": [],
        })
        interval = {"start": start, "end": end}
        if interval not in row["read_ranges"]:
            row["read_ranges"].append(interval)
        if start == 1 and end == item["lines"]:
            row["full_read"] = True
        if detail not in row["outcomes"]:
            row["outcomes"].append(detail)
    coverage_items = []
    for row in coverage_by_path.values():
        row["read_ranges"].sort(key=lambda r: (r["start"], r["end"]))
        row["outcome"] = " ".join(row.pop("outcomes"))
        coverage_items.append(row)

    coverage = {
        "schema_version": 1,
        "round": 47,
        "report_version": "v0.70",
        "snapshot_sha": SHA,
        "mode": "read_only_exact_main_scoped_semantic_review",
        "scope": [
            "CSKH complaint replay and dashboard pending state",
            "doctor-rule settings preview freshness",
            "visit journey/history stale or pending UI state",
            "fast reschedule idempotency lifecycle",
            "pharmacy add-line BFF/service retry path",
            "procedure follow-up object authorization",
            "Ops/Supabase health visibility",
            "held date/config/legacy-script candidates",
        ],
        "method": "Immutable pinned Git blobs via git show. Every recorded range is line-checked and SHA-256 checked. Tests were read-not-run. No application code, ClinicAI tests/runtime/API/DB/provider/VPS/production/secrets/PHI was touched.",
        "result": {
            "new_findings": ["CLIN-058", "FE-028"],
            "extended_findings": ["FE-002", "FE-023", "FE-026", "CLIN-057", "FIN-003", "SEC-011", "INF-027"],
            "deduplicated": [
                "DayNoi/LamThem settings forms with catch/finally were excluded from FE-023.",
                "Procedure-order UI catches network rejection and backend has a duplicate-order guard; ambiguous message remains held, not a duplicate-order finding.",
                "Complaint replay is distinct from reschedule marker replay: it inserts a second complaint row/event, not a second appointment.",
                "Fast-reschedule key remount was confirmed through two active UI callers; the backend receipt only deduplicates a repeated key.",
                "Pharmacy add-line BFF evidence extends existing FIN-003; its earlier synthetic DB reproduction remains the only reproduced evidence for that finding.",
            ],
            "held_candidates": [
                "Impossible ISO week-start inputs normalize to another displayed week; only a low display candidate.",
                "Old external-DB helper contains DROP SCHEMA CASCADE under a fixed temporary name; no active caller/current self-hosted applicability established.",
                "GoTrue URI allowlist wildcard needs a recovery redirect acceptance review; exact behavior was not established, so no exploit finding.",
                "Sequential room-config saves could partially persist; owner policy/atomicity contract is unclear.",
                "Procedure selection response-loss text can say not-started even if a request committed; no duplicate order shown because backend guard exists.",
                "Appointment follow-up GET failure can look like no appointment, but service prevents an existing live appointment from being duplicated; held as a UI candidate.",
            ],
            "full_source_audit_complete": False,
        },
        "full_files": [x for x in coverage_items if x["full_read"]],
        "targeted_traces": [x for x in coverage_items if not x["full_read"]],
        "reviewer_note": "Round 47 is a scoped static review, not a full-repository read or runtime validation. All findings are conditional unless explicitly labeled reproduced in an earlier record.",
    }
    save("blocks/round47.coverage.json", coverage)

    round_md = f"""# Round 47 — exact-main CSKH, settings, workflow, pharmacy and Ops review

Source SHA: `{SHA}`. Evidence was read from immutable Git blobs using `git show`; current checkout WIP was not used as source evidence. This is a targeted static review, not a full repository read. Tests were read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI were accessed.

## Findings

- **Added CLIN-058 LOW:** complaint POST has no stable command receipt. A replay after commit/response loss can insert another complaint and event row. Existing unit tests do not cover retry after commit; no runtime reproduction or production incident is claimed.
- **Added FE-028 LOW:** doctor-rule preview state is keyed by service only. Changing method/month can leave an old number visible while the new preview is pending or failed; Save remains enabled. Backend calculation still uses current parameters.
- **Extended FE-023:** found rejected-request pending-state gaps in complaint, new-user, location-scope and doctor-rule forms. Forms with catch/finally were excluded.
- **Extended FE-026:** history-of-edits panel can stay on “Đang đọc…” after fetch rejection.
- **Extended FE-002:** visit journey refresh keeps stale data unmarked; initial failure hides the panel.
- **Extended CLIN-057:** the fast-reschedule UI is actively mounted by two callers; closing/remounting gives the same intent a new idempotency key. No duplicate appointment was demonstrated.
- **Extended FIN-003:** QuayThuoc BFF add-line route also does not forward an idempotency key; the prior synthetic DB reproduction remains the only reproduced evidence.
- **Extended SEC-011:** procedure-follow-up metadata GET checks identity and clinic, but not the doctor assignment for the requested visit.
- **Extended INF-027:** Ops inventory/rollup/monitoring omit self-hosted Supabase dependencies, while public auth/REST/realtime routes exist and health handlers are static responses. Runtime outage behavior was not tested.

## Held observations

Impossible ISO week dates can display a normalized week; an old external-DB helper has a fixed-name `DROP SCHEMA CASCADE` but no active caller was found; GoTrue wildcard redirect semantics need exact recovery-flow review; sequential room saves lack an established atomicity policy; procedure-selection ambiguous response and appointment-follow-up UI cases were not promoted because duplicate business writes were not shown.

## Coverage and limits

Exact ranges, line counts and SHA-256 values are recorded in `blocks/round47.coverage.json`; new and extended finding excerpts are in `PHAT-HIEN.json`. The fast-reschedule session/remount trace was checked against active callers. Path states are not behavioral coverage. Full source audit remains incomplete.
"""
    (ROOT / "blocks/round47.md").write_text(round_md)

    manifest = load("MAIN-PHAM-VI.json")
    for record in manifest["files"]:
        item = coverage_by_path.get(record["path"])
        if not item:
            continue
        if item["full_read"]:
            record["status"] = "read"
            record["full_file_read"] = True
        elif record["status"] in {"scanned", "inventoried"}:
            record["status"] = "traced"
        ranges = ", ".join(f"{r['start']}–{r['end']}" for r in item["read_ranges"])
        note = f"Round 47 exact-main {ranges}; see blocks/round47.coverage.json."
        if "Round 47 exact-main" not in record.get("method", ""):
            record["method"] = (record.get("method", "") + " | " + note).strip(" |")
        record["round47_note"] = item["outcome"]
    manifest["last_updated_round"] = 47
    save("MAIN-PHAM-VI.json", manifest)
    save("PHAT-HIEN.json", findings)

    main_counts = Counter(x["status"] for x in manifest["files"])
    code_files = [x for x in manifest["files"] if Path(x["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(x["status"] for x in code_files)
    finding_counts = Counter(x["main_validation"]["status"] for x in findings)
    severity_counts = Counter(x["severity"] for x in findings)
    state = load("STATE.json")
    state.update({
        "updated_at": "2026-10-20",
        "status": "in_progress",
        "report_version": "v0.70",
        "phase": "round47_v070_cskh_settings_workflow_ops_audit_open",
        "report_round_summary": "Round 47 adds CLIN-058 and FE-028; extends FE-002, FE-023, FE-026, CLIN-057, FIN-003, SEC-011 and INF-027. Other observations remain explicitly held.",
        "next_action": "Continue exact-main review of unread or structurally scanned files. Prioritize object-level authorization matrices, clinical lifecycle transitions, migrations/restore, API retry receipts and dashboard stale/pending state. Preserve full_source_audit_complete=false until all required source scope and validation gaps are actually closed.",
        "report_status": "Round 47 evidence integrated; report-only QA and portable package refresh pending; full source audit remains incomplete.",
        "full_source_audit_complete": False,
        "new_findings_v070": ["CLIN-058", "FE-028"],
        "round47": {
            "status": "integrated_static_review_report_qa_pending_audit_open",
            "notes": "blocks/round47.md",
            "coverage": "blocks/round47.coverage.json",
            "new_findings": ["CLIN-058", "FE-028"],
            "extended_findings": ["FE-002", "FE-023", "FE-026", "CLIN-057", "FIN-003", "SEC-011", "INF-027"],
            "held_candidates": coverage["result"]["held_candidates"],
            "tests": "Related tests read-not-run; no ClinicAI tests executed in Round 47.",
            "runtime": "No ClinicAI app/API/DB/provider/VPS/production/secrets/PHI access.",
            "full_source_audit_complete": False,
            "targeted_paths": len(coverage_items),
            "full_file_reads": sum(1 for x in coverage_items if x["full_read"]),
        },
    })
    state["summary"]["findings"] = len(findings)
    state["summary"]["severity"] = {k: severity_counts[k] for k in ("HIGH", "MEDIUM", "LOW")}
    state["summary"]["main_status"] = {
        "still_present_on_main": finding_counts["still_present_on_main"],
        "partially_addressed_on_main": finding_counts["partially_addressed_on_main"],
        "addressed_on_main": finding_counts["addressed_on_main"],
    }
    state["summary"]["main_files"] = len(manifest["files"])
    state["summary"]["main_partial_traces"] = main_counts["traced"]
    state["summary"]["main_coverage"] = {k: main_counts[k] for k in ("inventoried", "traced", "read", "scanned", "excluded")}
    state["summary"]["code_like_source_files"] = {
        "definition": "Pinned-tree code/web/sql/shell suffixes; includes app, tests, tooling and styles.",
        "total": len(code_files),
        "coverage": {k: code_counts[k] for k in ("inventoried", "traced", "scanned", "read")},
    }
    state["limits"][0] = (
        f"Full source audit incomplete: {main_counts['inventoried']} inventoried, {main_counts['traced']} partially traced, {main_counts['scanned']} scanned and {main_counts['excluded']} excluded paths out of {len(manifest['files'])}. Path state is not behavioral coverage."
    )
    state["limits"][1] = (
        f"Code-like suffix group includes runtime, tests, tooling and styles; current path ledger: {code_counts['read']} read, {code_counts['traced']} partially traced, {code_counts['scanned']} scanned, {code_counts['inventoried']} inventoried and {code_counts['excluded']} excluded out of {len(code_files)}. This is not a percent-complete or correctness score."
    )
    append_item_once(state["limits"], "Round 47 is static exact-main only; complaint/fast-reschedule retry, settings preview, UI network failures, role matrix and Supabase health were not reproduced at runtime or observed in production.")
    state["artifacts"]["integration_script"] = "Round47 integrated; v0.70 report-only QA and audit-only ZIP refresh pending."
    state["artifacts"]["qa"] = "Pending v0.70 report-only validator and browser check; application behavior not validated."
    state["package"]["status"] = "pending"
    state["package"]["file_count"] = None
    state["package"]["integrity"] = "Pending rebuild after report QA and final handoff checkpoint."
    state["portable_bundle_status"] = "Pending final v0.70 audit-only package rebuild and verification."
    save("STATE.json", state)

    (ROOT / "TIEP-TUC.md").write_text(
        "# CURRENT HANDOFF — v0.70, Round 47\n\n"
        f"Evidence source: immutable Git SHA `{SHA}` in `{REPO}`. The primary checkout may contain user WIP; do not use it as evidence. Read source only with `git show <SHA>:<path>`. Only edit audit artifacts in this directory; do not run ClinicAI tests/runtime/API/DB/provider/VPS/production or inspect secrets/PHI.\n\n"
        "Round 47 added CLIN-058 (CSKH complaint replay) and FE-028 (stale doctor-rule preview); extended FE-002, FE-023, FE-026, CLIN-057, FIN-003, SEC-011 and INF-027. Dedupe/held decisions and exact line/hash evidence are in `blocks/round47.md`, `blocks/round47.coverage.json`, `PHAT-HIEN.json` and `MAIN-PHAM-VI.json`. Related tests were read-not-run.\n\n"
        "Current path counters are inventory states, not percent semantic coverage. Full source audit remains incomplete. Report-only QA/package refresh is pending. Resume by reading `BAT-DAU-TU-DAY.md`, then continue from `STATE.json` and exact pinned main.\n"
    )
    (ROOT / "BAT-DAU-TU-DAY.md").write_text(
        "# Bắt đầu từ đây — checkpoint v0.70, Round 47\n\n"
        "Đọc `TIEP-TUC.md`, `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `blocks/round47.md` và `blocks/round47.coverage.json`. Source evidence chỉ từ SHA `" + SHA + "` qua `git show` trong worktree audit; không dùng working-tree WIP làm bằng chứng.\n\n"
        "Round 47 thêm CLIN-058, FE-028; mở rộng FE-002/023/026, CLIN-057, FIN-003, SEC-011 và INF-027. Tests read-not-run; không runtime/production. HTML QA và ZIP refresh pending sau integration.\n\n"
        "**Full source audit chưa hoàn tất.** Path counters không phải phần trăm đã hiểu hành vi; chỉ sửa audit artifacts. Tiếp tục theo `STATE.json.next_action`.\n"
    )
    with (ROOT / "NHAT-KY.md").open("a") as handle:
        handle.write(
            "\n\n## Round 47 — 20/10/2026, v0.70 integration\n\n"
            "Static exact-main review at SHA `" + SHA + "`. Added CLIN-058 and FE-028; extended FE-002, FE-023, FE-026, CLIN-057, FIN-003, SEC-011 and INF-027. Impossible roster date, inactive external-DB helper, GoTrue wildcard redirect, room-config partial-save and ambiguous UI outcomes remain held. Related tests were read-not-run; no ClinicAI runtime/API/DB/provider/VPS/production/secrets/PHI was accessed. Exact coverage is in `blocks/round47.coverage.json`; full source audit remains incomplete. Report-only QA/package refresh pending.\n"
        )
    print(f"Integrated Round 47: {len(findings)} findings; {len(coverage_items)} path coverage records; full audit remains open")


if __name__ == "__main__":
    main()
