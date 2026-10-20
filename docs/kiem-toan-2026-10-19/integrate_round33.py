from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIN_SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
PINNED = Path(json.loads((ROOT / "MAIN-PHAM-VI.json").read_text())["snapshot"])
NOW_UTC = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
NOW_LOCAL = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def excerpt(path: str, start: int, end: int, detail: str) -> dict:
    source = PINNED / path
    lines = source.read_text().splitlines()
    if start < 1 or end < start or end > len(lines):
        raise ValueError(f"invalid range {path}:{start}-{end}")
    return {
        "path": path,
        "line": start,
        "end_line": end,
        "sha256": digest(source),
        "excerpt": "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1)),
        "detail": detail,
    }

def public_evidence(specs: list[tuple[str, int, int, str]]) -> list[dict]:
    return [
        {k: v for k, v in excerpt(path, start, end, detail).items()
         if k in {"path", "line", "end_line", "detail"}}
        for path, start, end, detail in specs
    ]

def hashes(specs: list[tuple[str, int, int, str]]) -> dict[str, str]:
    return {
        path: digest(PINNED / path)
        for path, _, _, _ in specs
    }

def make_finding(
    *, finding_id: str, title: str, severity: str, category: str, summary: str,
    trigger: str, impact: str, recommendation: str, acceptance: str,
    alignment: list[str], validation_result: str, limitations: str,
    evidence_specs: list[tuple[str, int, int, str]],
    related_tests: list[str], dedupe: str,
) -> dict:
    ev = [excerpt(*spec) for spec in evidence_specs]
    return {
        "id": finding_id,
        "title": title,
        "severity": severity,
        "evidence_level": "confirmed_static",
        "category": category,
        "summary": summary,
        "trigger": trigger,
        "impact": impact,
        "evidence": public_evidence(evidence_specs),
        "validation": {
            "method": "round33_static_cross_layer_trace_on_pinned_main",
            "command": None,
            "result": validation_result,
            "limitations": limitations,
        },
        "recommendation": recommendation,
        "acceptance": acceptance,
        "alignment": alignment,
        "related_tests": related_tests,
        "source_hashes": hashes(evidence_specs),
        "status": "open",
        "reference_version": "pinned_main",
        "production_metadata_validation": None,
        "main_validation": {
            "sha": PIN_SHA,
            "status": "still_present_on_main",
            "note": dedupe,
            "evidence": ev,
        },
    }

def write_json(name: str, value: object) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

ledger_path = ROOT / "MAIN-PHAM-VI.json"
finding_path = ROOT / "PHAT-HIEN.json"
state_path = ROOT / "STATE.json"
ledger = json.loads(ledger_path.read_text())
if ledger["sha"] != PIN_SHA:
    raise SystemExit("Pinned source SHA changed; refusing integration")
if PINNED.resolve() != Path(ledger["snapshot"]).resolve():
    raise SystemExit("Snapshot root mismatch")
findings = json.loads(finding_path.read_text())
ids = {row["id"] for row in findings}
for required in ("CLIN-049", "SEC-034", "SEC-035"):
    if required in ids:
        raise SystemExit(f"{required} already exists; integration is not idempotent")

# Extend existing patient-lookup risk with the still-registered profile endpoints.
profile_specs = [
    ("src/clinicai/api/v1/routers/thu_ky.py", 68, 77,
     "GET hành chính chỉ yêu cầu get_current_identity rồi trả hồ sơ qua service."),
    ("src/clinicai/api/v1/routers/thu_ky.py", 95, 106,
     "GET nhật ký CSKH cũng chỉ yêu cầu identity; trả cskh_followup và note."),
    ("src/clinicai/services/ho_so_khach_doc.py", 46, 69,
     "Luật mở hồ sơ cho mọi vai ngoài TKYK (TKYK chưa phân công được mở toàn clinic)."),
    ("src/clinicai/services/ho_so_khach_doc.py", 72, 117,
     "Hồ sơ hành chính trả thông tin liên hệ, địa chỉ, người giám hộ và lịch hẹn."),
    ("src/clinicai/services/ho_so_khach_doc.py", 200, 218,
     "Nhật ký CSKH trả nội dung follow-up và ghi chú tự do; không có capability riêng."),
]
patient = next(row for row in findings if row["id"] == "SEC-027")
patient["title"] = "Một số API hồ sơ bệnh nhân trả PII mà thiếu capability đọc nhất quán"
patient["summary"] = (
    "GET /patients/{id} và /patients?phone= chỉ dùng get_current_identity, không "
    "yêu cầu patient.list.view. Cùng router, /patients/danh-sach có capability này; "
    "preset PHARMACIST không có. Một đường API hồ sơ cũ còn tồn tại: "
    "/ho-so-khach/{id}/hanh-chinh trả dữ liệu liên hệ/người giám hộ/lịch hẹn và "
    "/cskh trả cskh_followup cùng ghi chú tự do. Hai route chỉ yêu cầu identity; "
    "duoc_mo cho phép hầu hết vai nội bộ, ngoại trừ TKYK có thể bị giới hạn bởi "
    "phân công. Các truy vấn được scope theo clinic. Đây là phạm vi đọc rộng trong "
    "cùng clinic, không có bằng chứng cross-clinic; dashboard hiện không thấy gọi "
    "hai route hồ sơ này."
)
patient["trigger"] = (
    "Một thành viên nội bộ cùng clinic nhưng không được cấp patient.list.view gọi "
    "API theo UUID/số điện thoại, hoặc gọi trực tiếp endpoint hồ sơ hành chính/CSKH "
    "với UUID bệnh nhân đã biết."
)
patient["impact"] = (
    "Vai không có capability xem danh sách vẫn có thể lấy PII hồ sơ trong cùng "
    "clinic; endpoint hồ sơ còn trả ghi chú CSKH. Mã nguồn chủ ý mở hồ sơ cho phần "
    "lớn vai nội bộ, nhưng không có capability/ma trận trường riêng để thu hẹp và "
    "đo quyền truy cập. Không có bằng chứng đọc chéo clinic hay caller dashboard "
    "hiện tại cho hai route hồ sơ."
)
patient["recommendation"] = (
    "Định nghĩa một capability đọc hồ sơ theo use case và áp dụng nhất quán cho "
    "mọi route ID/phone/profile; tách quyền đọc hành chính khỏi ghi chú CSKH, trả "
    "projection tối thiểu, giữ predicate clinic và thêm audit/negative tests theo "
    "role."
)
patient["acceptance"] = (
    "Vai không có capability bị từ chối ở ID, phone, hành chính và CSKH; vai được "
    "cấp chỉ nhận các trường cần thiết; kiểm tra hai clinic, assignment TKYK, "
    "audit log và che định danh bằng dữ liệu giả."
)
patient["evidence"].extend(public_evidence(profile_specs))
patient["main_validation"]["evidence"].extend(
    excerpt(*spec) for spec in profile_specs
)
patient["main_validation"]["note"] = (
    "Exact-main: ID/phone và các route hồ sơ hành chính/CSKH không áp một "
    "capability đọc hồ sơ thống nhất. get_current_identity chỉ chặn DISPLAY/PARTNER; "
    "profile helper cho phần lớn vai nội bộ mở hồ sơ. Dữ liệu vẫn được scope theo "
    "clinic; dashboard hiện không thấy caller cho route hồ sơ."
)
patient.setdefault("source_hashes", {}).update(hashes(profile_specs))
patient["related_tests"] = list(dict.fromkeys(
    patient.get("related_tests", []) + [
        "src/tests/services/test_ho_so_khach_doc_db.py:24-44 — chỉ kiểm một số luồng đọc; không có negative role/capability case.",
        "src/tests/unit/test_ho_so_khach_quan_ly.py:18-40 — kiểm bypass DB của MANAGEMENT; không kiểm ma trận role đọc hồ sơ.",
    ]
))

# Last selected room -> empty array -> null -> CLINIC scope.
sec34 = [
    ("src/dashboard/app/(dashboard)/phan-quyen/LegoCuaNguoi.tsx", 71, 89,
     "UI gửi quyền bat=true; danh sách rỗng được serialize thành phong_ids=null."),
    ("src/dashboard/app/(dashboard)/phan-quyen/LegoCuaNguoi.tsx", 145, 179,
     "Bỏ checkbox phòng cuối vẫn gọi doi(..., true, []); copy chỉ giải thích tắt toàn lego."),
    ("src/dashboard/app/api/phan-quyen/route.ts", 132, 141,
     "BFF chuyển du_lieu nguyên trạng tới API quyền."),
    ("src/clinicai/api/v1/routers/phan_quyen.py", 55, 62,
     "DTO nhận phong_ids=null và mô tả rỗng là toàn phòng."),
    ("src/clinicai/api/v1/routers/phan_quyen.py", 250, 264,
     "Router chuẩn hóa null/rỗng thành None rồi gọi PermissionService."),
    ("src/clinicai/services/permission_service.py", 400, 428,
     "Danh sách trống được đổi thành [None], sau đó cấp scope_type=CLINIC."),
    ("src/clinicai/permissions/catalogue.py", 1000, 1008,
     "Lego Phòng dịch vụ cấp capability thuc_hien theo phòng."),
    ("src/clinicai/permissions/can.py", 32, 40,
     "Scope CLINIC làm capability đúng cho mọi room_id."),
    ("supabase/migrations/20260923000003_capability.sql", 46, 74,
     "Schema lưu CLINIC/null là toàn clinic, ROOM/id là từng phòng."),
    ("src/tests/services/test_lego_21_db.py", 97, 143,
     "Test kiểm một phòng và chọn tất cả; không kiểm bỏ phòng cuối qua UI."),
]
findings.append(make_finding(
    finding_id="SEC-034",
    title="Bỏ phòng cuối trong quyền đang bật có thể cấp quyền toàn phòng khám",
    severity="MEDIUM",
    category="permission_scope_escalation",
    summary=(
        "Trong lego Phòng dịch vụ đang bật, bỏ checkbox phòng cuối gửi bat=true với "
        "phong_ids rỗng. UI biến danh sách rỗng thành null; PermissionService quy "
        "ước null/rỗng là tất cả phòng, thu các cấp phòng cũ rồi cấp capability "
        "thuc_hien ở scope CLINIC. Bộ kiểm tra quyền coi scope này hợp lệ cho mọi "
        "phòng. Đây là mở rộng quyền trong cùng clinic do affordance bỏ chọn phòng "
        "cuối; sau phản hồi, checkbox “Tất cả phòng” sẽ thể hiện phạm vi mới."
    ),
    trigger=(
        "Quản lý đang bật lego “Phòng dịch vụ” cho một nhân viên với đúng một "
        "phòng được chọn rồi bỏ chọn phòng đó, với ý định gỡ phòng cuối."
    ),
    impact=(
        "Thay vì không còn phòng được cấp, nhân viên nhận capability thuc_hien cho "
        "mọi phòng trong clinic. UI có checkbox “Tất cả phòng” và sau khi tải lại "
        "sẽ hiện nó được chọn, nhưng việc mở rộng quyền đã được ghi ngay trong "
        "request. Không thấy đường đi sang clinic khác."
    ),
    recommendation=(
        "Tách rõ ba trạng thái: chưa bật, bật theo các phòng được chọn, và bật "
        "toàn clinic. Không diễn giải danh sách rỗng thành tất cả khi người dùng "
        "bỏ phòng cuối; yêu cầu chọn rõ “Tất cả phòng” hoặc tắt lego, đồng thời "
        "hiển thị xác nhận khi phạm vi sắp rộng hơn."
    ),
    acceptance=(
        "Từ một grant một phòng, thao tác bỏ phòng cuối không tạo grant CLINIC; "
        "chỉ thao tác “Tất cả phòng” được cấp CLINIC. UI, BFF và service có test "
        "cho chuyển scope ROOM→none và ROOM→CLINIC; quyền hiệu lực ở phòng khác "
        "được kiểm bằng fixture tổng hợp."
    ),
    alignment=[
        "Ownership ngày càng rõ hơn",
        "Vấn đề được phát hiện sớm hơn",
        "Con người bị gián đoạn ít hơn nhưng đúng lúc hơn",
        "Quyết định dựa trên bằng chứng tốt hơn",
    ],
    validation_result=(
        "Trace UI → BFF → router → PermissionService → capability evaluator/schema. "
        "Đối chiếu test room-scope hiện có; test chỉ chọn đúng một phòng và gọi "
        "đường explicit all, không thử bỏ phòng cuối. Không chạy test."
    ),
    limitations=(
        "Static exact-main behavior; chưa mô phỏng click/browser/HTTP/DB. Phạm vi "
        "rủi ro là quản trị quyền nội bộ cùng clinic. Checkbox “Tất cả phòng” "
        "phản ánh kết quả sau khi lưu; không có bằng chứng cross-clinic."
    ),
    evidence_specs=sec34,
    related_tests=[
        "src/tests/services/test_lego_21_db.py:97-143 — chọn một phòng và explicit all; không test bỏ phòng cuối.",
        "src/tests/services/test_permission_db.py — grant/revoke event; đã đọc, không chạy; không compose last-room UI path.",
    ],
    dedupe=(
        "Still present on pinned main 956ba4f2. Bỏ phòng cuối gửi bat=true/[]; "
        "backend đổi rỗng thành scope CLINIC và evaluator cho phép mọi phòng. "
        "Không trùng SEC-012 (retry thu capability theo skill), SEC-026 (projection "
        "audit), SEC-033 (authorization TOCTOU)."
    ),
))

# Hide a proof from list but keep its ordinary authenticated GET readable.
sec35 = [
    ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 234, 235,
     "Migration định nghĩa gỡ là ẩn trên màn, giữ tệp và dòng."),
    ("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql", 264, 270,
     "Comment bảng xác nhận go_luc là ẩn, không xóa; bảng bật RLS theo clinic."),
    ("src/clinicai/services/anh_chuyen_khoan_service.py", 74, 83,
     "Danh sách ảnh hiện hành loại các hàng go_luc khác NULL."),
    ("src/clinicai/services/anh_chuyen_khoan_service.py", 186, 205,
     "doc() tra theo clinic+id nhưng không lọc go_luc, rồi đọc bytes từ kho."),
    ("src/clinicai/api/v1/routers/payment.py", 537, 557,
     "GET yêu cầu cashier-history read scope rồi gọi doc(history_authorized=True); response no-store."),
    ("src/clinicai/services/payment_access_service.py", 48, 56,
     "Proof lookup lấy cycle_id không loại ảnh đã gỡ."),
    ("src/clinicai/services/payment_access_service.py", 93, 108,
     "Đường read tiếp tục yêu cầu receipt/history scope; không phải anonymous access."),
    ("src/dashboard/app/(dashboard)/thu-ngan/AnhChuyenKhoan.tsx", 83, 118,
     "UI gỡ ảnh khỏi danh sách và dùng GET URL theo id để mở/hiển thị ảnh."),
    ("src/dashboard/app/api/payment/anh-ck/route.ts", 18, 43,
     "BFF yêu cầu auth, proxy GET với no-store và không mở public link."),
    ("src/tests/services/test_thu_nhieu_hinh_thuc_db.py", 221, 261,
     "Test xác nhận ảnh bị ẩn khỏi danh sách sau go; không gọi doc() lại với id đó."),
]
findings.append(make_finding(
    finding_id="SEC-035",
    title="Ảnh chuyển khoản đã gỡ khỏi danh sách vẫn đọc được qua URL cũ",
    severity="LOW",
    category="proof_retention_access_contract",
    summary=(
        "Gỡ ảnh đặt go_luc và loại ảnh khỏi danh sách, nhưng file và row được giữ "
        "cố ý. GET theo id không lọc go_luc; người đã có quyền đọc lịch sử thu và "
        "biết id vẫn lấy được bytes qua URL cũ hoặc tab đã mở. Đây là quyền cùng "
        "clinic của cashier-history, không phải truy cập ẩn danh hay chéo tenant. "
        "Migration nói rõ gỡ = ẩn, không xóa; rủi ro còn lại là hợp đồng UI không "
        "nói rõ việc ẩn không thu hồi đường đọc."
    ),
    trigger=(
        "Một ảnh bị gỡ khỏi danh sách chứng từ nhưng tab/URL cũ còn giữ id; người "
        "đọc có quyền xem lịch sử khoản thu tải lại đúng URL đó."
    ),
    impact=(
        "Chứng từ đã ẩn khỏi danh sách vẫn có thể được xem lại qua đường đọc hiện "
        "tại khi người xem được authorize lịch sử thu. API và BFF đều yêu cầu "
        "authentication, scope receipt/history, giới hạn clinic, private/no-store "
        "và nosniff; chưa thấy public hoặc cross-clinic exposure. Nếu “gỡ” chỉ "
        "nghĩa là ẩn để giữ vết thì đây là semantics cần nói rõ, không phải xóa dữ liệu."
    ),
    recommendation=(
        "Chốt semantics thành hai thao tác rõ ràng: ẩn khỏi chứng từ hiện hành và "
        "xem chứng từ lưu trữ. Nếu ẩn phải thu hồi xem thường, lọc go_luc ở GET "
        "chuẩn; nếu cần giữ vết, chỉ mở qua lịch sử/audit có permission riêng và "
        "ghi actor/lý do."
    ),
    acceptance=(
        "Sau khi gỡ, GET chứng từ hiện hành theo id trả 404/410; nếu nghiệp vụ "
        "cần giữ ảnh, một luồng archive riêng cho phép người có quyền audit đọc "
        "lại với event/access log. Test synthetic covers both cases."
    ),
    alignment=[
        "Reality ngày càng dễ nhìn thấy hơn",
        "Ownership ngày càng rõ hơn",
        "Quyết định dựa trên bằng chứng tốt hơn",
    ],
    validation_result=(
        "Trace list query → gỡ soft-state → authenticated BFF/FastAPI GET → receipt "
        "scope and file read; test currently checks list exclusion only. No API or DB call."
    ),
    limitations=(
        "Migration explicitly defines go as hide/retain, so the intended product "
        "contract may allow authorized archive reads. No unauthorized, cross-clinic, "
        "cache, or public access was demonstrated; classify LOW pending explicit "
        "decision on whether a hidden proof remains ordinarily retrievable."
    ),
    evidence_specs=sec35,
    related_tests=[
        "src/tests/services/test_thu_nhieu_hinh_thuc_db.py:221-261 — upload/read/go/list-hidden; no read-after-go assertion.",
        "src/tests/unit/test_payment_access.py:75-121 — cashier history authorization, read not run.",
    ],
    dedupe=(
        "Still present on pinned main 956ba4f2. This concerns authenticated GET-by-ID "
        "after go_luc, distinct from INF-001/INF-013 backup/worker health, SEC-030 "
        "PostgREST metadata SELECT, and FIN-016 refund tender breakdown. Intent to "
        "retain the file is explicit; the open question is access semantics."
    ),
))

# Same-time doctor switch leaves the former doctor's advisory marker active.
clin49 = [
    ("src/dashboard/app/(dashboard)/appointments/BookingHub.tsx", 761, 800,
     "The hold effect posts selectedSlot.doctorId and reruns when doctorId changes."),
    ("src/dashboard/app/api/appointments/slot-hold/route.ts", 47, 66,
     "BFF routes the authenticated hold request to FastAPI."),
    ("src/clinicai/api/v1/routers/booking.py", 856, 884,
     "Backend hold endpoint forwards doctor, slot start/end to SlotHoldService."),
    ("src/clinicai/services/slot_hold_service.py", 78, 105,
     "hold() releases own holds using keep=slot_start, then upserts a row keyed by doctor."),
    ("src/clinicai/services/slot_hold_service.py", 185, 218,
     "Release predicate preserves rows by slot_start only; it does not compare doctor_id."),
    ("supabase/migrations/20260804000008_slot_hold.sql", 46, 56,
     "Active uniqueness includes doctor_id; active list index groups start time."),
    ("src/dashboard/app/(dashboard)/appointments/dung-giu-cho.ts", 19, 59,
     "Other staff display active holds keyed by doctor/date/time."),
    ("src/tests/services/test_slot_hold.py", 42, 103,
     "Tests rights and 10-minute expiry, not same-time doctor switch and release."),
]
findings.append(make_finding(
    finding_id="CLIN-049",
    title="Đổi bác sĩ nhưng giữ khung giờ có thể để sót nhãn giữ chỗ cũ",
    severity="LOW",
    category="booking_advisory_state",
    summary=(
        "BookingHub gửi lại POST giữ chỗ khi selectedSlot.doctorId đổi. "
        "SlotHoldService.hold() chỉ loại các giữ chỗ cũ có slot_start khác giờ mới; "
        "unique key lại bao gồm doctor_id. Nếu đổi sang bác sĩ khác nhưng giữ cùng "
        "ngày/giờ, hàng cũ cho bác sĩ trước vẫn active. Bộ hiển thị đánh dấu theo "
        "bác sĩ/ngày/giờ nên đồng nghiệp thấy nhãn “Đang giữ” giả trên ô cũ tối đa "
        "10 phút. Đây là hold tư vấn, không chặn đặt lịch."
    ),
    trigger=(
        "Nhân viên chọn một slot, sau đó đổi bác sĩ nhưng giữ cùng ngày và giờ "
        "trong khi màn BookingHub vẫn mở."
    ),
    impact=(
        "Lịch hiển thị trạng thái giữ sai trên slot của bác sĩ cũ; đồng nghiệp có "
        "thể mất thời gian xác minh hoặc chọn slot khác. Không chứng minh việc đặt "
        "lịch bị khóa hay sai dữ liệu appointment; chưa xác nhận tần suất trên production."
    ),
    recommendation=(
        "Thay hold theo định danh đầy đủ (doctor_id + slot_start) hoặc lưu hold id "
        "hiện hành rồi release chính xác hàng cũ trong cùng transaction trước khi "
        "ghi hold mới. Giữ TTL 10 phút làm dự phòng khi request rời màn thất bại."
    ),
    acceptance=(
        "Với hai bác sĩ và cùng slot_start, POST đổi bác sĩ làm hàng hold cũ "
        "released_at khác NULL và chỉ hàng bác sĩ mới còn active; danh sách đồng "
        "nghiệp chỉ đánh dấu bác sĩ mới. Thử riêng request cancel/retry và expiry."
    ),
    alignment=[
        "Reality ngày càng dễ nhìn thấy hơn",
        "Unknown ngày càng ngắn hơn",
        "Con người bị gián đoạn ít hơn nhưng đúng lúc hơn",
    ],
    validation_result=(
        "Static UI → BFF → FastAPI → service → unique-index/display trace. "
        "Đọc test boundary/expiry hiện có; không chạy test hoặc runtime."
    ),
    limitations=(
        "Static behavior only; no occurrence count or production state was checked. "
        "Hold is advisory and expires after 10 minutes; booking acceptance is not gated by it."
    ),
    evidence_specs=clin49,
    related_tests=[
        "src/tests/services/test_slot_hold.py:42-103 — role/expiry coverage; not same-time doctor-switch behavior.",
        "src/tests/services/test_doi_lich_nhanh_db.py — read for overlap only; no new finding from quick reschedule.",
    ],
    dedupe=(
        "Still present on pinned main 956ba4f2. New condition is doctor change at identical "
        "slot_start; deduped against CLIN-005/010/035/043 appointment outcomes and "
        "CLIN-016 room configuration. The slot hold is advisory only."
    ),
))

# Keep chronology stable: add round findings after the latest existing checkpoint.
files_to_trace: dict[str, tuple[list[tuple[int, int]], str]] = {}
def add_ranges(specs: list[tuple[str, int, int, str]], method: str) -> None:
    for path, start, end, _detail in specs:
        ranges, old_method = files_to_trace.setdefault(path, ([], method))
        ranges.append((start, end))
        files_to_trace[path] = (ranges, old_method)

add_ranges(profile_specs, "Round 33 targeted semantic trace: profile PII/CSKH role boundary; not a full-file review.")
add_ranges(sec34, "Round 33 targeted semantic trace: room-scope permission change; not a full-file review.")
add_ranges(sec35, "Round 33 targeted semantic trace: hidden transfer-proof GET/access scope; not a full-file review.")
add_ranges(clin49, "Round 33 targeted semantic trace: same-time doctor-switch hold lifecycle; not a full-file review.")
by_path = {item["path"]: item for item in ledger["files"]}
coverage_files = []
for path, (ranges, method) in sorted(files_to_trace.items()):
    source = PINNED / path
    item = by_path.get(path)
    if item is None:
        raise SystemExit(f"Coverage path missing from full tree ledger: {path}")
    actual_hash = digest(source)
    if item.get("sha256") and item["sha256"] != actual_hash:
        raise SystemExit(f"Existing ledger hash mismatch: {path}")
    item["sha256"] = actual_hash
    item["lines"] = len(source.read_text().splitlines())
    if item["status"] in {"inventoried", "scanned"}:
        item["status"] = "traced"
    item["method"] = f'{item["method"]} | {method}'
    coverage_files.append({
        "path": path,
        "sha256": actual_hash,
        "read_ranges": [
            {"start": start, "end": end}
            for start, end in sorted(set(ranges))
        ],
        "depth": "targeted_trace",
        "notes": method + " Tests read only, not run.",
    })
ledger["last_updated_round"] = 33

coverage = {
    "round": 33,
    "snapshot_sha": PIN_SHA,
    "mode": "read_only_exact_main_static_semantic_review",
    "scope": [
        "patient profile API and existing SEC-027 boundary",
        "permission UI and ROOM-to-CLINIC scope",
        "cashier transfer proof hide/read lifecycle",
        "booking same-time doctor-switch hold lifecycle",
    ],
    "method": (
        "Trace UI → BFF → router/service → permission/schema/event/test where applicable; "
        "verify file SHA-256 and excerpts against pinned Git snapshot. No ClinicAI runtime."
    ),
    "result": (
        "SEC-027 extended with legacy profile/CSKH routes; added SEC-034, SEC-035, "
        "CLIN-049. Related paths reviewed with no additional finding: quick reschedule, "
        "service switch and post-procedure follow-up."
    ),
    "files": coverage_files,
    "tests_run": [],
    "tests_read_not_run": [
        {"path": "src/tests/services/test_ho_so_khach_doc_db.py", "lines": "24-44"},
        {"path": "src/tests/unit/test_ho_so_khach_quan_ly.py", "lines": "18-40"},
        {"path": "src/tests/services/test_lego_21_db.py", "lines": "97-143"},
        {"path": "src/tests/services/test_permission_db.py", "lines": "selected grant/revoke cases"},
        {"path": "src/tests/services/test_thu_nhieu_hinh_thuc_db.py", "lines": "221-261"},
        {"path": "src/tests/unit/test_payment_access.py", "lines": "75-121"},
        {"path": "src/tests/services/test_slot_hold.py", "lines": "42-103"},
        {"path": "src/tests/services/test_doi_lich_nhanh_db.py", "lines": "read for dedupe only"},
    ],
    "deduplication": [
        "SEC-012 skill capability revocation retry differs from empty-room scope conversion.",
        "SEC-026 consolidated audit visibility differs from actual grant scope.",
        "SEC-027 retained and widened to cover profile/CSKH routes; same missing capability family, no duplicate.",
        "SEC-030 PostgREST payment metadata differs from authenticated proof bytes GET.",
        "INF-001/INF-013 backup/worker health differ from proof GET-by-id after hide.",
        "FIN-016 tender breakdown differs from proof visibility.",
        "CLIN-005/010/016/024/026/035/043 appointment/schedule overlap checked; same-time doctor-switch false hold remains distinct.",
    ],
    "limitations": [
        "Static source audit only; no tests, app, API, database, provider, production, secrets or PHI were accessed.",
        "No production occurrence counts for hidden proof re-reads, room-scope clicks, or stale holds.",
        "The proof migration explicitly defines go as hide/retain; contract decision remains open.",
        "Whole-source audit remains incomplete: scanned and inventoried paths remain.",
    ],
}

# Recompute path-level counters; this is not behavioral coverage.
from pathlib import Path as _Path
code_suffixes = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html",
}
state = json.loads(state_path.read_text())
counts = Counter(row["severity"] for row in findings)
levels = Counter(row["evidence_level"] for row in findings)
main_status = Counter(row["main_validation"]["status"] for row in findings)
all_status = Counter(item["status"] for item in ledger["files"])
code_files = [item for item in ledger["files"] if _Path(item["path"]).suffix.lower() in code_suffixes]
code_status = Counter(item["status"] for item in code_files)
state["updated_at"] = NOW_UTC
state["status"] = "in_progress"
state["phase"] = "round33_integrated_awaiting_html_qa_and_bundle_full_source_audit_incomplete"
state["next_action"] = (
    "Read TIEP-TUC.md; continue exact-main semantic review on remaining scanned/inventoried "
    "paths, prioritize authorization scope, clinical/booking, finance and worker recovery. "
    "Full source audit remains incomplete."
)
state["summary"].update({
    "findings": len(findings),
    "severity": {key: counts[key] for key in ("HIGH", "MEDIUM", "LOW")},
    "evidence_levels": {key: levels[key] for key in ("reproduced_local", "design_gap", "confirmed_static")},
    "main_status": {key: main_status[key] for key in ("still_present_on_main", "partially_addressed_on_main", "addressed_on_main")},
    "main_files": len(ledger["files"]),
    "main_partial_traces": all_status["traced"],
    "main_coverage": {key: all_status[key] for key in ("inventoried", "traced", "read", "scanned", "excluded")},
    "code_like_source_files": {
        "definition": "Pinned-tree paths with common code/web/sql/shell suffixes; includes app, tests, tooling and styles.",
        "total": len(code_files),
        "coverage": {key: code_status[key] for key in ("inventoried", "traced", "scanned", "read")},
        "traced_is_partial": True,
    },
    "new_findings_v056": ["SEC-034", "SEC-035", "CLIN-049"],
    "round33_extended_findings": ["SEC-027"],
})
state["report_version"] = "v0.56"
state["report_round_summary"] = (
    "Round 33 adds SEC-034 (last-room removal widens to clinic scope), SEC-035 "
    "(hidden transfer proof remains readable to authorized history users), and CLIN-049 "
    "(same-time doctor switch leaves a stale advisory hold); extends SEC-027 to legacy "
    "profile/CSKH routes. Proof retention semantics are explicitly limited; tests read, "
    "not run. Full exact-main source audit remains incomplete."
)
state["report_status"] = (
    "v0.56 integrated; report-only HTML QA and audit ZIP verification pending; "
    "exact-main source audit remains incomplete."
)
state["artifacts"]["integration_script"] = (
    "Round33: integrate_round33.py; blocks/round33.md and round33.coverage.json."
)
state["artifacts"]["qa"] = (
    "Pending v0.56 report-only structural/evidence validation and browser QA; "
    "does not validate ClinicAI or source audit completeness."
)
state["artifacts"]["qa_html_version"] = "v0.56 pending"
state["blocks"]["security"]["status"] = "round33_SEC034_room_scope_escalation_and_SEC035_proof_contract_added; review remains open"
state["blocks"]["security"]["findings"] = "PHAT-HIEN.json (SEC-001..SEC-035; IDs non-contiguous)"
state["blocks"]["security"]["coverage"] = "blocks/round33.coverage.json plus prior security coverage blocks"
state["blocks"]["security"]["next"] = (
    "Continue API/auth/RLS object-boundary review. SEC-017/018 dynamic checks and "
    "SEC-034 synthetic permission-scope test remain unverified."
)
state["blocks"]["clinical"]["status"] = "round33_CLIN049_booking_hold_lifecycle_added; clinical/operations review remains open"
state["blocks"]["clinical"]["findings"] = "PHAT-HIEN.json (CLIN-001..CLIN-049; IDs non-contiguous)"
state["blocks"]["clinical"]["coverage"] = "blocks/round33.coverage.json plus clinical coverage blocks"
state["blocks"]["clinical"]["next"] = (
    "Continue unreviewed clinical, patient identity, CSKH and booking paths; test "
    "same-time doctor-switch hold lifecycle in a safe fixture if later authorized. "
    "Full source audit remains open."
)
write_json("PHAT-HIEN.json", findings)
write_json("MAIN-PHAM-VI.json", ledger)
write_json("blocks/round33.coverage.json", coverage)
write_json("STATE.json", state)

round_note = f"""# Round 33 — {NOW_LOCAL}, v0.56

Source: exact pinned Git SHA `{PIN_SHA}`; only report artifacts changed.

- Added SEC-034: removing the final selected room in an enabled room-scoped lego sends an empty scope, which becomes a clinic-wide capability grant.
- Added SEC-035: a transfer proof hidden with `go_luc` remains readable via an old authenticated GET URL by a user with payment-history scope. Migration explicitly defines this as hide/retain; LOW severity and contract limitation are stated.
- Added CLIN-049: changing doctor at the same slot time leaves the former doctor's advisory hold active for up to ten minutes.
- Extended SEC-027 with the still-registered administrative-profile and CSKH routes; treated as the same missing patient-read capability family.
- Read exact-main UI → BFF → API/service → migration/evaluator/test paths. Test files were read, not run; no app, API, DB, provider, VPS, production, secrets or PHI accessed.
- Coverage hashes and ranges: `blocks/round33.coverage.json`. Whole-source audit remains incomplete; report HTML and bundle QA are pending.
"""
(ROOT / "blocks/round33.md").write_text(round_note)

handoff = f"""# CURRENT HANDOFF — v0.56 ({NOW_LOCAL} local)

Source evidence must come from Git SHA `{PIN_SHA}` at `{PINNED}`. Original primary checkout `543b9787` has unrelated WIP; never use it for source conclusions. Reply in Vietnamese. Do not edit app/migrations, run ClinicAI tests/runtime/API/DB/provider, access VPS/production, secrets or PHI.

Round 33 added SEC-034, SEC-035, CLIN-049 and extended SEC-027. Findings: {len(findings)} ({counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['LOW']} LOW); {main_status['still_present_on_main']} still present / {main_status['partially_addressed_on_main']} partial / {main_status['addressed_on_main']} addressed in checked scope. Tests were read, not run. SEC-035 is LOW and explicitly conditional: migration defines go as hide/retain; ordinary authenticated GET by a payment-history-authorized user remains available.

Path ledger: {len(ledger['files']):,} paths: {all_status['read']:,} read, {all_status['traced']:,} traced partially, {all_status['scanned']:,} scanned, {all_status['inventoried']:,} inventoried, {all_status['excluded']:,} excluded. This is file/path status, not behavior coverage. Full source audit is incomplete.

## Round33 evidence
- `blocks/round33.md`
- `blocks/round33.coverage.json`
- `PHAT-HIEN.json`
- `MAIN-PHAM-VI.json`
- Integration script: `integrate_round33.py`

## Next
1. Build HTML from durable records: `python3 docs/kiem-toan-2026-10-19/build_report.py`.
2. Validate `python3 docs/kiem-toan-2026-10-19/validate_report.py`; run report-only browser QA `node docs/kiem-toan-2026-10-19/verify_browser.cjs`; update `HTML-QA.json` and STATE with exact outcomes.
3. Repackage and verify only after all report files are final: `python3 docs/kiem-toan-2026-10-19/package_audit.py`, then `python3 docs/kiem-toan-2026-10-19/verify_bundle.py`.
4. Continue exact-main semantic review on the remaining scanned/inventoried API/auth/RLS, clinical/booking, finance and worker paths. Do not claim full audit until that work and necessary synthetic verification are complete.
"""
(ROOT / "TIEP-TUC.md").write_text(handoff)
(ROOT / "BAT-DAU-TU-DAY.md").write_text(
    f"""# Bắt đầu từ đây — checkpoint v0.56

Round 33 added SEC-034/035 and CLIN-049, extended SEC-027. Source evidence is pinned to `{PIN_SHA}`. Full source audit remains incomplete.

Read `TIEP-TUC.md`, then `STATE.json`, `NHAT-KY.md`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json`, `MAIN-COMPARISON.json`, `TEST-RUNS.json`, and `blocks/round33.*`. Do not use the dirty primary checkout as source evidence. Do not edit app/migrations or run ClinicAI tests/runtime/API/DB/provider, and do not access VPS/production/secrets/PHI. Update only audit artifacts and the offline HTML.
"""
)
with (ROOT / "NHAT-KY.md").open("a") as f:
    f.write("\n\n" + round_note)

print(f"Integrated v0.56: {len(findings)} findings; {len(coverage_files)} coverage paths.")
print(f"Path status: read={all_status['read']} traced={all_status['traced']} scanned={all_status['scanned']} inventoried={all_status['inventoried']} excluded={all_status['excluded']}")
print(f"Severity: HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}")
