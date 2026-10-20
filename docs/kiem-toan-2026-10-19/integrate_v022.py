"""Integrate exact-main source findings into portable audit checkpoint v0.22."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SNAPSHOT = Path("/tmp/clinicai-audit-main-956ba4f2")
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"


def read_json(name: str):
    return json.loads((ROOT / name).read_text())


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def proof(path: str, start: int, end: int, detail: str) -> dict:
    return {"path": path, "line": start, "end_line": end, "detail": detail}


FINDINGS = [
    {
        "id": "CLIN-023",
        "title": "Hàng duyệt kết quả có thể che việc chờ ngoài 200 bản ghi hoặc 60 ngày",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "clinical_worklist_completeness",
        "summary": "Truy vấn kết quả chờ duyệt chỉ lấy hồ sơ tạo trong 60 ngày và LIMIT 200; API/UI không gửi hoặc hiện tổng, cursor hay cờ còn dữ liệu. Khi có hơn 200 hồ sơ trong cửa sổ hoặc hồ sơ chưa duyệt cũ hơn 60 ngày, phần bị loại không xuất hiện trong worklist và UI có thể nói không còn kết quả chờ.",
        "trigger": "Có hơn 200 hồ sơ cần duyệt trong 60 ngày, hoặc có hồ sơ chưa duyệt cũ hơn 60 ngày, rồi người duyệt mở hàng đợi.",
        "impact": "Việc đọc kết quả có thể bị bỏ ngoài hàng chờ đang dùng; nhân viên không được báo là danh sách đã cắt. Chưa biết dữ liệu thật có chạm ngưỡng hay SLA cho bản quá 60 ngày.",
        "evidence": [
            proof("src/clinicai/services/luot_kham_doc.py", 1452, 1457, "Query lọc created_at trong 60 ngày rồi LIMIT 200, không có cursor/has_more."),
            proof("src/dashboard/app/(dashboard)/duyet-ket-qua/DuyetKetQua.tsx", 68, 96, "UI đếm mảng đã nhận và khi rỗng hiển thị không có kết quả chờ; không biết server đã cắt."),
        ],
        "validation": {
            "method": "static_service_to_worklist_trace",
            "command": None,
            "result": "Đối chiếu điều kiện ngày/limit của query với cách đếm và render UI.",
            "limitations": "Chưa tạo fixture >200, chưa xác nhận retention/SLA, không đọc production/PHI; chỉ kết luận về hợp đồng khi vượt ngưỡng.",
        },
        "recommendation": "Định nghĩa SLA/retention cho hàng chờ duyệt; phân trang ổn định và trả total/has_more. Nếu 60 ngày là chủ ý, đưa hồ sơ quá hạn sang một worklist quá hạn riêng thay vì để biến mất.",
        "acceptance": "Fixture 205 hồ sơ và hồ sơ quá 60 ngày: tất cả có owner/tuổi/trạng thái; UI báo số đang hiển thị, số còn lại và quá hạn; tải tiếp không lặp/mất hồ sơ.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Khoảng thời gian Unknown ngày càng ngắn hơn", "Bệnh nhân ít phải chờ trong bất định hơn"],
        "related_tests": ["src/tests/services/test_luot_kham_doc_db.py"],
    },
    {
        "id": "FE-010",
        "title": "Phòng tạm ngừng nhận vẫn đưa lượt vào danh sách có thể bấm Nhận",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "worklist_action_consistency",
        "summary": "Room query trả cờ accepting nhưng không loại phòng đang tạm ngừng nhận. Hàm tạo trạng thái đánh dấu sắp đến là nhan_duoc mà không xét cờ này; gom danh sách cũng tính tinh_so từ SAP_DEN không xét accepting. UI dùng nhan_duoc để hiện thao tác. Service ghi nhận cuối cùng từ chối ROOM_NOT_ACCEPTING, còn bộ đếm dem_sap_den lại tôn trọng accepting, tạo lệch giữa danh sách/huy hiệu và thao tác thực.",
        "trigger": "Phòng vẫn active nhưng accepting=false, có lượt hợp lệ chưa vào phòng và được cấu hình làm dịch vụ đó.",
        "impact": "Nhân viên thấy chỉ định có thể nhận hoặc được tính vào nhóm sắp đến, bấm vào thì bị từ chối; bộ đếm và danh sách có thể không nhất quán. Không thấy bypass ghi nhận trong lát code này.",
        "evidence": [
            proof("src/clinicai/services/nhan_tai_phong.py", 140, 171, "Query chọn pr.accepting nhưng điều kiện lọc chỉ is_active/đối tác/location/service."),
            proof("src/clinicai/services/nhan_tai_phong.py", 247, 304, "trang_thai_chi_dinh tạo nhan_duoc từ SAP_DEN hoặc chờ chéo, không xét accepting."),
            proof("src/clinicai/services/nhan_tai_phong.py", 495, 504, "Bộ đếm dem_sap_den có lọc accepting."),
            proof("src/clinicai/services/nhan_tai_phong.py", 523, 557, "gom_sap_den dùng nhan_duoc nhưng tinh_so kiểm SAP_DEN không xét accepting."),
            proof("src/dashboard/app/(dashboard)/phong/[ma]/KhungChiDinhKhach.tsx", 100, 125, "UI lấy nhan_duoc làm nguồn cho nhóm hành động Nhận."),
            proof("src/clinicai/services/service_routing_service.py", 2365, 2393, "Lệnh ghi từ chối ROOM_NOT_ACCEPTING; đây là lệch hiển thị/thao tác, chưa thấy nhận thành công."),
        ],
        "validation": {
            "method": "static_room_query_pure_helper_ui_and_command_trace",
            "command": None,
            "result": "Đối chiếu cờ accepting từ query, helper thuần, bộ đếm, UI và chốt từ chối ở service ghi.",
            "limitations": "Chưa chạy test helper/browser hoặc DB; chỉ khẳng định bất nhất logic code, không có bằng chứng nhân viên thực tế gặp.",
        },
        "recommendation": "Đưa trạng thái accepting vào cùng một hàm chính sách đầu vào để danh sách, count, badge và lệnh ghi chia sẻ cùng luật. Nếu vẫn cần hiện phòng tạm ngừng, gắn nhãn và không đưa vào nhóm thao tác.",
        "acceptance": "Fixture accepting=false: không hiện hành động Nhận/không tính sắp đến; count và list khớp. API ghi vẫn từ chối an toàn. Kiểm tra cả chờ chéo và phòng đối tác.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Con người bị gián đoạn ít hơn nhưng đúng lúc hơn", "Ownership ngày càng rõ hơn"],
        "related_tests": ["src/tests/services/test_nhan_tai_phong.py"],
    },
    {
        "id": "CLIN-024",
        "title": "Race đặt lịch trùng bị unique index chặn nhưng không được đổi thành lỗi nghiệp vụ",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "booking_concurrency_error_contract",
        "summary": "Service kiểm tra trước lịch cùng bệnh nhân/giờ rồi INSERT; khi hai request chạy đồng thời, unique partial index là hàng rào cuối. Khối INSERT chỉ đổi ExclusionViolation/CheckViolation thành ConflictError, không bắt UniqueViolation. Lỗi unique của lịch hoặc care_episode vì thế thoát khỏi route như lỗi DB thay vì phản hồi conflict có thể xử lý.",
        "trigger": "Hai request cùng clinic, bệnh nhân và slot_start vượt qua pre-check trước khi request nào commit; hoặc hai booking khác giờ cùng tạo care_episode đang sống cho cùng bệnh nhân/dịch vụ.",
        "impact": "DB vẫn giữ bất biến chống bản ghi trùng, nhưng request thua race có thể thành lỗi máy chủ chung thay vì 409/Conflict; client và nhân viên không nhận được giải thích rõ để tải lại hoặc chọn cách xử lý.",
        "evidence": [
            proof("src/clinicai/services/booking_service.py", 612, 619, "Pre-check double booking chạy trước INSERT, không serialize riêng theo bệnh nhân/slot."),
            proof("src/clinicai/services/booking_service.py", 662, 710, "INSERT chỉ map ExclusionViolation và CheckViolation; không map UniqueViolation."),
            proof("supabase/migrations/20260805000007_appointment_patient_slot_unique.sql", 67, 69, "Unique partial index clinic+patient+slot_start giữ bất biến khi race."),
            proof("src/clinicai/services/booking_service.py", 2529, 2577, "care_episode được SELECT rồi INSERT; race giữa hai slot có thể đụng unique live index."),
            proof("supabase/migrations/20260730000003_multi_tenant_foundation.sql", 198, 201, "Unique partial index giới hạn một care_episode chưa CLOSED cho clinic/patient/service."),
            proof("src/clinicai/api/v1/routers/booking.py", 457, 478, "Route gọi service rồi lưu receipt; không có map lỗi unique tại đường này."),
        ],
        "validation": {
            "method": "static_transaction_constraint_and_route_trace",
            "command": None,
            "result": "Đối chiếu pre-check, constraint migration, handlers tại INSERT, attach episode và route.",
            "limitations": "Chưa chạy concurrent DB probe; response cuối phụ thuộc error middleware chung. Không khẳng định duplicate được lưu — unique index ngăn nó.",
        },
        "recommendation": "Bắt đúng constraint unique trong transaction và đổi sang ConflictError có mã ổn định; ghi metric race riêng. Kiểm lại receipt/idempotency khi transaction rollback để lần thử lại trả kết quả có nghĩa.",
        "acceptance": "Chạy hai request đồng thời trên slot và hai slot cùng care episode: đúng một commit theo từng bất biến; request còn lại nhận 409 có mã nghiệp vụ, không 500, không receipt thành công giả và retry an toàn.",
        "alignment": ["Ownership ngày càng rõ hơn", "Lỗi lặp lại dần biến thành cải tiến hệ thống", "Quyết định dựa trên bằng chứng tốt hơn"],
        "related_tests": ["src/tests/services/test_booking_service_db.py"],
    },
    {
        "id": "CLIN-025",
        "title": "patient_kind sai bị âm thầm coi như không khai báo",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "booking_input_semantics",
        "summary": "BookingRequest nhận patient_kind dưới dạng string tự do. Service chỉ chấp nhận NEW/RETURN; giá trị khác bị đổi thành None. Comment nghiệp vụ cho biết None khi có episode đang sống sẽ nhập booking vào episode hiện hành, giống RETURN. Lỗi gõ/enum cũ vì vậy không bị từ chối mà có thể làm đổi cách nhóm hồ sơ chăm sóc.",
        "trigger": "Client gửi patient_kind khác NEW/RETURN, ví dụ lỗi chính tả hoặc phiên bản client có enum không đồng bộ, và bệnh nhân đã có care_episode đang sống cho dịch vụ đó.",
        "impact": "Booking vẫn có thể thành công nhưng liên kết episode theo nhánh mặc định; dữ liệu phân loại lần khám mất dấu lỗi đầu vào và người dùng không biết cần sửa.",
        "evidence": [
            proof("src/clinicai/api/v1/routers/booking.py", 83, 90, "BookingRequest nhận patient_kind là string tự do, chỉ giới hạn độ dài."),
            proof("src/clinicai/services/booking_service.py", 558, 561, "Giá trị ngoài NEW/RETURN bị đổi thành None."),
            proof("src/clinicai/services/booking_service.py", 2524, 2562, "None được xử lý như RETURN khi episode còn sống."),
        ],
        "validation": {
            "method": "static_request_normalization_and_episode_trace",
            "command": None,
            "result": "Theo chuỗi request → chuẩn hoá service → quy tắc attach_episode.",
            "limitations": "Chưa chạy HTTP/DB với enum sai; tác động phụ thuộc dữ liệu episode và client thực tế.",
        },
        "recommendation": "Đưa NEW/RETURN thành enum/schema ở ranh giới API; từ chối giá trị lạ bằng 422. Nếu None là hợp lệ, giữ riêng None với giá trị không hợp lệ và ghi rõ quy tắc mặc định.",
        "acceptance": "Enum sai nhận 422; NEW/RETURN/None có test riêng cho episode đang mở/đóng; không âm thầm biến lỗi gõ thành RETURN.",
        "alignment": ["Quyết định dựa trên bằng chứng tốt hơn", "Lỗi lặp lại dần biến thành cải tiến hệ thống"],
        "related_tests": ["src/tests/services/test_booking_service_db.py"],
    },
    {
        "id": "CLIN-026",
        "title": "Datetime đặt lịch không có timezone có thể gây lỗi 500 khi so sánh",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "booking_input_validation",
        "summary": "Request model nhận datetime nhưng không có validator yêu cầu timezone. Service so slot_end với datetime.now(timezone.utc); Python không cho so datetime naive với datetime aware nên input dạng giờ địa phương thiếu offset có thể ném TypeError trước khi vào transaction.",
        "trigger": "Client gửi slot_end dạng ISO local không có Z/offset, ví dụ `2026-10-20T09:00:00`, qua đường tạo/đổi lịch gọi chốt giờ quá khứ.",
        "impact": "Request lỗi ở runtime thay vì nhận 422 có giải thích; người dùng có thể thử lại hoặc gọi hỗ trợ mà không biết cần gửi múi giờ nào.",
        "evidence": [
            proof("src/clinicai/api/v1/routers/booking.py", 69, 90, "BookingRequest khai báo datetime nhưng không kiểm tzinfo trong model."),
            proof("src/clinicai/services/booking_service.py", 289, 308, "Helper so slot_end trực tiếp với datetime.now(timezone.utc)."),
            proof("src/clinicai/services/booking_service.py", 480, 515, "BookingService.create gọi helper trước mở transaction."),
        ],
        "validation": {
            "method": "static_request_type_and_datetime_comparison_trace",
            "command": None,
            "result": "Soát model và lệnh so aware/naive tại helper được gọi khi tạo booking.",
            "limitations": "Chưa gọi FastAPI với payload naive; status cuối có thể phụ thuộc middleware nhưng TypeError phát sinh từ phép so là xác định theo Python datetime semantics.",
        },
        "recommendation": "Yêu cầu offset ở boundary và trả validation 422; thống nhất biểu diễn UTC ở API, chuyển sang Asia/Ho_Chi_Minh chỉ tại UI. Kiểm cả các request đổi lịch khác dùng chung helper.",
        "acceptance": "Payload có offset hợp lệ đi qua; payload naive bị 422 với thông báo múi giờ; regression test cho create và reschedule, không ném 500.",
        "alignment": ["Bệnh nhân ít phải chờ trong bất định hơn", "Con người bị gián đoạn ít hơn nhưng đúng lúc hơn"],
        "related_tests": ["src/tests/services/test_booking_service_db.py"],
    },
    {
        "id": "CLIN-027",
        "title": "Danh sách checkout lượt treo cắt ở 300 mà không báo còn dữ liệu",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "worklist_completeness",
        "summary": "CheckoutService.stale_list lấy tối đa 300 lượt cũ và trả mảng; route chỉ bọc `items`. Proxy/UI tiếp tục dùng mảng như toàn bộ danh sách, không có tổng, cursor hoặc cờ bị cắt. Khi số lượt tồn quá ngưỡng, lượt cũ hơn không xuất hiện trong hàng xử lý.",
        "trigger": "Có hơn 300 lượt chưa checkout từ ngày trước trong phạm vi cơ sở, rồi lễ tân mở danh sách tồn đọng.",
        "impact": "Nhân viên có thể tưởng danh sách đã đủ và bỏ sót lượt cần đóng/đối soát; chưa có bằng chứng số liệu production vượt 300.",
        "evidence": [
            proof("src/clinicai/services/checkout_service.py", 690, 720, "Truy vấn stale_list ORDER BY rồi LIMIT 300 và trả list, không metadata phân trang."),
            proof("src/clinicai/api/v1/routers/dispatch.py", 337, 353, "Endpoint trả nguyên items từ stale_list."),
            proof("src/dashboard/app/api/reception/checkout/route.ts", 26, 42, "Proxy chuyển query tồn đọng và trả response backend."),
            proof("src/dashboard/app/(dashboard)/reception/checkout/LuotTonDong.tsx", 40, 50, "Client chỉ đọc items; không có trường total/has_more."),
        ],
        "validation": {
            "method": "static_service_api_proxy_ui_trace",
            "command": None,
            "result": "Đối chiếu cap, response route, proxy và client contract.",
            "limitations": "Chưa seed >300; không kết luận số lượt thật. Đây là điều kiện completeness khi vượt cap.",
        },
        "recommendation": "Thêm phân trang cursor theo checked_in_at/visit_id và has_more/total; UI ghi rõ còn việc và ưu tiên theo tuổi/SLA. Không để một danh sách tồn đọng không có cách lật sang phần sau.",
        "acceptance": "Fixture 305 lượt treo: có thể xem/xử lý đủ, page tiếp không trùng/mất; UI phân biệt không có việc với đã tải trang đầu còn việc.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Ownership ngày càng rõ hơn", "Vấn đề được phát hiện sớm hơn"],
        "related_tests": ["src/tests/services/test_checkout_service_db.py"],
    },
    {
        "id": "INF-012",
        "title": "50 event thông báo lỗi lâu ngày có thể giữ chỗ đầu hàng đợi và health vẫn xanh",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "notification_queue_observability",
        "summary": "Relay luôn lấy 50 event event_published=false cũ nhất. Lỗi gửi hoặc thiếu cấu hình giữ event ở false nên nếu 50 event đầu đều lỗi, poll sau chọn lại cùng nhóm và event mới hơn bị đói. Worker vẫn heartbeat sau poll rỗng/thất bại; health/su-kien đếm event_delivery và hen_gio, không đo backlog event_log.",
        "trigger": "Ít nhất 50 event cũ nhất có template không gửi được hoặc thiếu provider config; các event vẫn chưa published qua nhiều poll.",
        "impact": "Thông báo mới hơn có thể không được thử trong lúc queue đầu bị kẹt, nhưng worker liveness/health vẫn xanh. Điều kiện chỉ xảy ra khi đủ một batch 50 event bị lỗi; event không có template được xử lý theo nhánh riêng và không nhất thiết chặn queue.",
        "evidence": [
            proof("src/clinicai/services/notification_relay.py", 134, 146, "Chọn event_published=false cũ nhất, giới hạn BATCH_SIZE."),
            proof("src/clinicai/services/notification_relay.py", 216, 245, "Lỗi hoặc skipped không đổi event_published; poll sau vẫn chọn lại."),
            proof("src/clinicai/worker.py", 155, 163, "Heartbeat chạy sau poll kể cả không gửi được event."),
            proof("src/clinicai/api/v1/health.py", 68, 105, "Health đếm event_delivery và hen_gio; không có backlog event_log."),
        ],
        "validation": {
            "method": "static_relay_batch_retry_worker_heartbeat_and_health_trace",
            "command": None,
            "result": "Đối chiếu thứ tự/chặn lô query, nhánh lỗi, heartbeat và metric health.",
            "limitations": "Chưa dựng 50 event trên DB hoặc thử provider; không có log/prod evidence. Kết luận bị giới hạn đúng điều kiện batch nêu trên.",
        },
        "recommendation": "Lưu next_attempt_at/attempt_count và trạng thái quarantine/dead-letter cho event relay; query due item có fairness/partition. Đưa backlog age, oldest pending và blocked count vào health/alert, không để liveness thay cho delivery health.",
        "acceptance": "Synthetic DB tạo 50 event cũ bị lỗi cùng event mới hợp lệ: event mới vẫn được thử theo fairness policy; retry có backoff, dead-letter có owner/reason; health báo backlog/tuổi vượt SLO dù worker còn sống.",
        "alignment": ["Khoảng thời gian Unknown ngày càng ngắn hơn", "Vấn đề được phát hiện sớm hơn", "Ownership ngày càng rõ hơn", "Con người bị gián đoạn ít hơn nhưng đúng lúc hơn"],
        "related_tests": [],
    },
]


def snapshot_evidence(evidence: list[dict]) -> tuple[list[dict], dict[str, str]]:
    rendered, hashes = [], {}
    for item in evidence:
        source = SNAPSHOT / item["path"]
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        lines = source.read_text().splitlines()
        if item["line"] < 1 or item["end_line"] > len(lines):
            raise ValueError(f"Invalid evidence range: {item}")
        excerpt = "\n".join(
            f"{n}: {lines[n - 1]}" for n in range(item["line"], item["end_line"] + 1)
        )
        rendered.append({
            "path": item["path"], "line": item["line"],
            "end_line": item["end_line"], "sha256": digest, "excerpt": excerpt,
        })
        hashes[item["path"]] = digest
    return rendered, hashes


def append_extension(finding: dict, evidence: list[dict], *, summary: str | None = None) -> None:
    rendered, hashes = snapshot_evidence(evidence)
    existing_keys = {
        (item["path"], item["line"], item["end_line"])
        for item in finding["main_validation"]["evidence"]
    }
    finding["main_validation"]["evidence"].extend(
        item for item in rendered
        if (item["path"], item["line"], item["end_line"]) not in existing_keys
    )
    finding["source_hashes"].update(hashes)
    known = {(x["path"], x["line"], x["end_line"]) for x in finding["evidence"]}
    finding["evidence"].extend(
        item for item in evidence
        if (item["path"], item["line"], item["end_line"]) not in known
    )
    if summary:
        finding["summary"] = summary


def append_note(path: str, heading: str, body: str) -> None:
    target = ROOT / path
    text = target.read_text()
    if heading not in text:
        target.write_text(text.rstrip() + "\n\n" + heading + "\n\n" + body.strip() + "\n")


def main() -> None:
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"Missing pinned source snapshot: {SNAPSHOT}")
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    findings = read_json("PHAT-HIEN.json")
    existing = {item["id"]: item for item in findings}
    duplicate_ids = set(existing) & {item["id"] for item in FINDINGS}
    if duplicate_ids:
        raise SystemExit(f"Refusing duplicate finding IDs: {sorted(duplicate_ids)}")

    for finding in FINDINGS:
        rendered, hashes = snapshot_evidence(finding["evidence"])
        finding["source_hashes"] = hashes
        finding["status"] = "open"
        finding["reference_version"] = "pinned_main"
        finding["main_validation"] = {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "Còn hiện diện trên source exact-main ghim; kết luận chỉ trong phạm vi evidence và trigger đã nêu, không suy ra production.",
            "evidence": rendered,
            "production_verified": False,
        }

    # The stale-lease concern is now reproduced in a synthetic database, with a
    # narrow claim: generic callback effects can overlap; no business consumer
    # side effect or production incident was demonstrated.
    inf005 = existing["INF-005"]
    inf005["evidence_level"] = "reproduced_local"
    inf005["summary"] += " Probe DB synthetic mới cho thấy handler cũ còn sống sau khi mất lease vẫn commit callback effect sau khi worker mới đã commit; điều này tái hiện khả năng callback trùng của worker chung, chưa chứng minh consumer nghiệp vụ cụ thể gây tác dụng phụ bên ngoài."
    inf005["validation"] = {
        "method": "synthetic_disposable_postgres_two_worker_lease_interleaving",
        "command": "PATH=/tmp/clinicai-audit-git-wrapper:$PATH scripts/test-nhanh.sh /Users/quangdang/Projects/Dr4Women-MacMini/docs/kiem-toan-2026-10-19/probes/test_worker_lease_race_db.py -q -s",
        "result": "1 passed (0.20s): A bắt đầu callback rồi chờ; lease hết và được thu hồi; B nhận cùng event, ghi callback và DONE; sau đó A tiếp tục ghi. callback_count=2, hai dòng DB synthetic đã commit.",
        "limitations": "Chỉ probe generic worker với bảng audit scratch và event tổng hợp trên DB dùng một lần; không gọi consumer nghiệp vụ, provider hoặc production, không chứng minh side effect thực nào bị nhân đôi. Runner áp 42 migration pinned còn thiếu lên template main@27e010d6 có seed lệch; không phải fresh bootstrap. Test source được giữ trong probes/.",
    }
    inf005["main_validation"]["note"] = "Source claim/reclaim/finish vẫn không fencing trên main ghim; generic stale handler race đã tái hiện trong DB tổng hợp. Chưa chứng minh tác động phụ của consumer nghiệp vụ hoặc production."
    inf005["main_validation"]["evidence"].extend(snapshot_evidence([
        proof("src/clinicai/events/worker.py", 168, 198, "Callback chạy sau khi claim transaction kết thúc; finish update không gắn ownership generation.")
    ])[0])

    append_extension(
        existing["FIN-002"],
        [
            proof("src/clinicai/services/kho_thuoc_service.py", 218, 233, "Thẻ kho LIMIT 1000, helper chỉ cảnh báo log; API trả dong dạng list, không có paging metadata."),
            proof("src/dashboard/app/(dashboard)/pharmacy/inventory/TheKho.tsx", 69, 85, "UI gọi API một lần, lưu nguyên response; không có phân trang/cursor."),
        ],
        summary=existing["FIN-002"]["summary"] + " Bổ sung thẻ kho: ledger lấy tối đa 1.000 dòng; cảnh báo chỉ vào log, API/UI không có cursor hoặc total.",
    )

    append_extension(
        existing["SEC-011"],
        [
            proof("src/clinicai/services/tep_ket_qua_service.py", 1258, 1308, "Liệt kê kết quả lọc clinic+patient caller gửi và capability chung; không kiểm assignment patient-level."),
            proof("src/clinicai/services/tep_ket_qua_service.py", 1544, 1600, "Resolve nội dung bằng tep_id+clinic rồi gate capability; chưa gắn patient-assignment guard."),
            proof("src/clinicai/api/v1/routers/ultrasound.py", 230, 249, "Ảnh siêu âm chỉ yêu cầu _SONO_GUARD trước khi gọi reader."),
            proof("src/clinicai/services/media_service.py", 414, 450, "Reader xác thực clinic prefix và key có trong image_refs một record cùng clinic, không kiểm assignment của caller."),
            proof("src/clinicai/services/ultrasound_board_service.py", 32, 37, "Board service có các helper patient-assignment riêng, khác guard của đường image trực tiếp."),
        ],
        summary=existing["SEC-011"]["summary"] + " Bổ sung tệp kết quả và ảnh siêu âm: đường list/read dùng clinic + capability, image reader xác nhận key thuộc một record cùng clinic nhưng không kiểm bệnh nhân có thuộc assignment của người xem. Không kết luận cross-clinic; với ảnh cần caller đã biết key hợp lệ.",
    )
    existing["SEC-011"]["validation"]["limitations"] += " Các đường tệp kết quả/ảnh siêu âm và assignment mới static; ảnh yêu cầu key đã biết hoặc được lộ trước đó, chưa chứng minh đoán khóa, HTTP exploit hay truy cập cross-clinic."

    findings.extend(FINDINGS)
    write_json("PHAT-HIEN.json", findings)

    manifest = read_json("MAIN-PHAM-VI.json")
    by_path = {item["path"]: item for item in manifest["files"]}
    partial_notes = {
        "src/clinicai/services/luot_kham_doc.py": "v0.22: trace query duyệt kết quả 60 ngày/200 dòng; không phải full service review.",
        "src/dashboard/app/(dashboard)/duyet-ket-qua/DuyetKetQua.tsx": "v0.22: trace count/render hàng duyệt; không phải full UI review.",
        "src/clinicai/services/nhan_tai_phong.py": "v0.22: trace accepting flag qua room query/helper/count/group; không phải full service review.",
        "src/dashboard/app/(dashboard)/phong/[ma]/KhungChiDinhKhach.tsx": "v0.22: trace nhan_duoc action source; không phải full UI review.",
        "src/clinicai/services/service_routing_service.py": "v0.22: đối chiếu write guard ROOM_NOT_ACCEPTING; không phải full service review.",
        "src/clinicai/services/booking_service.py": "v0.22: trace booking precheck/unique constraints, patient_kind coercion, datetime guard và episode attach; không phải full service review.",
        "src/clinicai/api/v1/routers/booking.py": "v0.22: trace request fields và create error boundary; không phải full router review.",
        "supabase/migrations/20260805000007_appointment_patient_slot_unique.sql": "v0.22: trace unique patient/slot invariant only; not full migration review.",
        "supabase/migrations/20260730000003_multi_tenant_foundation.sql": "v0.22: trace live care_episode unique index only; not full migration review.",
        "src/clinicai/services/checkout_service.py": "v0.22: trace stale checkout cap/response only; not full service review.",
        "src/clinicai/api/v1/routers/dispatch.py": "v0.22: trace stale checkout endpoint only; not full router review.",
        "src/dashboard/app/api/reception/checkout/route.ts": "v0.22: trace stale checkout proxy only; not full route review.",
        "src/dashboard/app/(dashboard)/reception/checkout/LuotTonDong.tsx": "v0.22: trace stale list fetch contract; not full UI review.",
        "src/clinicai/services/kho_thuoc_service.py": "v0.22: trace 1,000-row ledger cap and response; not full service review.",
        "src/dashboard/app/(dashboard)/pharmacy/inventory/TheKho.tsx": "v0.22: trace single thẻ-kho fetch; not full UI review.",
        "src/clinicai/events/worker.py": "v0.22: generic stale-lease synthetic DB interleaving plus selected handler spans; not full worker/consumer review.",
        "src/clinicai/services/notification_relay.py": "v0.22: trace oldest-first batch/retry/publish fields; not full relay review.",
        "src/clinicai/worker.py": "v0.22: trace relay heartbeat placement; not full worker review.",
        "src/clinicai/api/v1/health.py": "v0.22: trace selected health counters; not full health router review.",
        "src/clinicai/services/tep_ket_qua_service.py": "v0.22: extend selected SEC-011 traces for list/content reads; not full service review.",
        "src/clinicai/api/v1/routers/ultrasound.py": "v0.22: trace direct ultrasound image read guard; not full router review.",
        "src/clinicai/services/media_service.py": "v0.22: trace ultrasound image key ownership/path checks; not full service review.",
        "src/clinicai/services/ultrasound_board_service.py": "v0.22: compare assignment-aware board helper against direct image route; not full service review.",
    }
    upgraded = 0
    for path, note in partial_notes.items():
        item = by_path.get(path)
        if item is None:
            raise ValueError(f"Evidence path missing from exact-main ledger: {path}")
        if item["status"] == "scanned":
            item["status"] = "traced"
            upgraded += 1
        item["method"] = (item.get("method", "") + " | " + note).strip(" |")
    write_json("MAIN-PHAM-VI.json", manifest)

    checks = read_json("KIEM-CHUNG.json")
    known = {(item.get("id"), item.get("path")) for item in checks["checks"]}
    for finding in FINDINGS:
        for path in finding["source_hashes"]:
            if (finding["id"], path) not in known:
                checks["checks"].append({"id": finding["id"], "path": path, "valid": True})
    for finding_id in ("INF-005", "FIN-002", "SEC-011"):
        for path in existing[finding_id]["source_hashes"]:
            if (finding_id, path) not in known:
                checks["checks"].append({"id": finding_id, "path": path, "valid": True})
    write_json("KIEM-CHUNG.json", checks)

    runs = read_json("TEST-RUNS.json")
    if any(run["id"] == "RUN-043" for run in runs):
        raise SystemExit("RUN-043 already exists; refusing to duplicate")
    runs.append({
        "id": "RUN-043",
        "at": now,
        "environment": "Synthetic disposable Postgres; exact-main source 956ba4f2; test creates audit_worker_lease_probe scratch table and synthetic event; no production/PHI.",
        "command": "PATH=/tmp/clinicai-audit-git-wrapper:$PATH scripts/test-nhanh.sh /Users/quangdang/Projects/Dr4Women-MacMini/docs/kiem-toan-2026-10-19/probes/test_worker_lease_race_db.py -q -s",
        "exit_code": 0,
        "result": "1 passed in 0.20s: old handler blocked after lease claim; lease expired/reclaimed; new handler committed event DONE; old handler resumed and also committed. Callback count=2 and both scratch rows persisted.",
        "limitations": [
            "Demonstrates generic worker callback overlap, not a side effect in a named business consumer or an external duplicate.",
            "Disposable DB template main@27e010d6 had stale seed and runner applied 42 pinned migrations; not fresh bootstrap. No production, provider, or patient data.",
            "Probe source is retained at probes/test_worker_lease_race_db.py; scratch table is confined to disposable DB.",
        ],
    })
    write_json("TEST-RUNS.json", runs)

    # Durable block notes for another account/session.
    append_note("blocks/infra_events.md", "## v0.22 — stale lease probe và notification relay",
        """- RUN-043 tái hiện generic worker callback A tiếp tục commit sau khi lease hết, event được reclaim, B commit DONE: 1 passed / 0.20s trên DB synthetic. Hai scratch effects commit; chưa chứng minh consumer nghiệp vụ/provider bị gọi trùng.
- INF-005 được nâng từ hypothesis lên reproduced_local; static source cũng còn thiếu fencing. Template DB main@27e010d6 khác seed pinned, runner áp 42 migration; không phải fresh install.
- INF-012 là confirmed_static: 50 event relay cũ lỗi/thiếu cấu hình có thể chiếm batch cũ nhất; heartbeat xanh, health không đếm backlog event_log. Chưa dựng batch runtime.
- Cần tiếp tục fairness/backoff/dead-letter của relay, metric oldest pending, và test fencing với consumer/projection thực trên DB disposable.""")
    append_note("blocks/clinical.md", "## v0.22 — queue kết quả, đặt lịch và checkout",
        """- CLIN-023: hàng duyệt kết quả lọc 60 ngày + LIMIT 200, không báo bị cắt; confirmed_static, chưa chốt SLA/retention.
- CLIN-024: unique booking/care-episode constraint chặn race nhưng UniqueViolation không được map rõ thành conflict; chưa chạy concurrency test.
- CLIN-025/026: enum patient_kind sai âm thầm thành None; datetime naive có thể TypeError khi so với UTC aware. Cả hai static, chưa HTTP probe.
- CLIN-027: checkout stale list LIMIT 300, route/proxy/UI không có paging metadata; chưa seed >300.
- Đối chiếu chính sách nghiệp vụ/SLA trước khi chọn hành vi cuối; không đọc production/PHI.""")
    append_note("blocks/frontend.md", "## v0.22 — trạng thái nhận phòng và hàng chờ duyệt",
        """- FE-010: UI dùng nhan_duoc làm nguồn hành động, trong khi helper bỏ qua accepting=false; count lọc accepting nhưng grouped tinh_so không lọc. Lệnh ghi vẫn chặn ROOM_NOT_ACCEPTING. Chỉ là bất nhất display/action đã thấy trong code; chưa browser/runtime test.
- CLIN-023 UI hiển thị count từ mảng đã nhận mà không biết query bị giới hạn 200/60 ngày.
- Cần pure-helper/browser tests với phòng tạm ngừng, và fault/data-cap tests cho hàng duyệt.""")
    append_note("blocks/pharmacy.md", "## v0.22 — completeness thẻ kho",
        """- Mở rộng FIN-002: truy vấn thẻ kho `LIMIT 1000`, chỉ log cảnh báo khi chạm trần; API trả `dong` và UI tải một lần, không cursor/total.
- Chưa có dữ liệu chứng minh cơ sở thực tế vượt ngưỡng. Acceptance nên bao gồm đủ 1.005 ledger entries và paging không mất/trùng dòng.""")
    append_note("blocks/security.md", "## v0.22 — mở rộng object-scope cho tệp và ảnh",
        """- Mở rộng SEC-011: một số list/content file-result path chỉ scope clinic+capability; direct ultrasound image đọc key đã nằm trong image_refs của record cùng clinic nhưng không kiểm assignment của caller.
- Không có bằng chứng cross-clinic; với ảnh, key phải được biết/đưa ra trước đó. Static-only, chưa JWT/HTTP synthetic identities; xác minh role policy trước khi kết luận mọi caller đều bị giới hạn assignment.""")

    append_note("NHAN-DINH.md", "## Cập nhật v0.22 — hàng đợi, concurrency và checkout",
        """Checkpoint này tích hợp 7 hồ sơ mới (6 MEDIUM và 1 MEDIUM trong vận hành; mọi finding mới đều confirmed-static) và mở rộng FIN-002, SEC-011. RUN-043 nâng INF-005 từ giả thuyết lên reproduced-local trong phạm vi generic callback trên DB synthetic. Các điểm nổi bật: hàng duyệt kết quả/checkout/thẻ kho có cap không báo đầy đủ; giao diện Nhận chưa khớp trạng thái accepting; booking race bị DB chặn nhưng chưa có lỗi nghiệp vụ ổn định; patient_kind và timezone chưa fail-fast; relay thông báo có điều kiện starvation 50 event và health không thấy backlog. Không có bằng chứng các ngưỡng đã bị chạm hoặc có incident production. Ledger và sổ phát hiện được cập nhật ở STATE/MAIN-PHAM-VI/PHAT-HIEN; audit full source vẫn chưa hoàn tất.""")
    append_note("QUYET-DINH.md", "## Cần chốt sau checkpoint v0.22",
        """- Hàng duyệt kết quả: SLA/retention bao lâu, việc quá 60 ngày chuyển sang overdue queue nào, ai sở hữu?
- Booking: patient_kind chỉ nhận NEW/RETURN hay cho phép None; API phải reject datetime không có offset ra sao? Chốt conflict contract khi unique race.
- Phòng: accepting=false có nên ẩn hẳn khỏi hàng sắp đến hay hiện nhãn tạm dừng? List/count/write phải cùng một policy.
- Relay: fairness theo clinic/event type, max retry, dead-letter owner và SLO oldest pending là gì?
- Checkout/thẻ kho: tải đầy đủ hay dùng cursor/total? Chốt retention và tuổi việc ưu tiên.
- Security: TKYK/siêu âm có phải assignment-limited trên từng file/ảnh hay role capability rộng hơn được chủ ý? Chốt ma trận quyền rồi test cặp identity/patient tổng hợp.""")
    append_note("NHAT-KY.md", "## Checkpoint v0.22 — 19/10/2026",
        """- RUN-043: worker lease race generic tái hiện 1 passed trên DB disposable; callback cũ + mới cùng commit scratch effect sau khi reclaim. Không suy ra consumer/provider/prod.
- Thêm CLIN-023..027, FE-010, INF-012; mở rộng FIN-002 và SEC-011; exact evidence/hash được sinh từ snapshot 956ba4f2.
- Rebuild HTML/ZIP và chạy report structural/browser QA là bước kế tiếp của checkpoint; nếu đang dở, đọc STATE/TIEP-TUC, không đọc lại từ đầu. Full audit còn thiếu.""")

    template = (ROOT / "report.template.html").read_text()
    template = template.replace("v0.21", "v0.22").replace("BẢN 0.21", "BẢN 0.22")
    template = template.replace("Đã kiểm kê và quét rộng; chỉ một phần code được truy vết sâu.",
        "Checkpoint v0.22 bổ sung 7 findings và probe worker synthetic; đã kiểm kê/quét rộng nhưng chỉ một phần code được truy vết sâu.")
    (ROOT / "report.template.html").write_text(template)

    severity = Counter(item["severity"] for item in findings)
    levels = Counter(item["evidence_level"] for item in findings)
    main_status = Counter(item["main_validation"]["status"] for item in findings)
    coverage = Counter(item["status"] for item in manifest["files"])
    suffixes = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html"}
    code = Counter(item["status"] for item in manifest["files"] if Path(item["path"]).suffix.lower() in suffixes)
    state = read_json("STATE.json")
    state["updated_at"] = now
    state["phase"] = "notification_worker_booking_and_clinical_worklist_checkpoint"
    state["next_action"] = "Continue exact-main semantic review; prioritize patient/object authorization and RLS/JWT runtime, result/booking/checkout write lifecycle, payment/refund/reconciliation, all major UI data flows, relay fairness and lease fencing with real consumers, then clean install/restore/tenant-two drills. Keep traces explicitly partial and do not claim full-source completion."
    state["report_status"] = "v0.22_78_findings_pending_html_and_bundle_QA; full source audit incomplete"
    state["limits"][0] = f"Full code audit incomplete; exact pinned tree stages: inventoried={coverage['inventoried']}, traced={coverage['traced']} partial traces, scanned={coverage['scanned']}, excluded={coverage['excluded']}; trace does not mean whole-file semantic review."
    state["limits"].append("RUN-043 reproduces a generic stale worker callback committing after lease reclaim on synthetic DB; no named business consumer/provider effect or production duplicate was demonstrated. DB template seed differed and 42 migrations were applied.")
    state["limits"].append("v0.22 worklist, booking, accepting-room and notification-relay findings are static; caps/retention policy were not validated against production volumes or owners.")
    state["blocks"]["infra_events"].update({"status": "checkpointed_probe_plus_static_slice_not_complete", "next": "INF-005 generic callback race reproduced locally; next test fencing with consumer projection and retry transaction. INF-012 relay starvation/health gap static; test fairness/backoff/dead-letter and add backlog SLO design. Continue backup/restore/deploy/CI paths."})
    state["blocks"]["clinical"].update({"status": "checkpointed_static_slice_not_complete", "next": "CLIN-023..027 integrated static only. Confirm result queue SLA, booking enum/timezone/conflict contract, checkout completeness; run DB+HTTP synthetic boundary tests. Continue clinical lifecycle and partner/referral paths."})
    state["blocks"]["frontend"].update({"status": "round5_candidates_integrated_static_only", "next": "FE-010 accepting mismatch static; run pure helper + browser tests for accepting=false and list/count consistency. Continue unseen UI/data routes and stale-context/fault injection."})
    state["blocks"]["pharmacy"].update({"status": "round4_inventory_completeness_static_only_not_complete", "next": "FIN-002 extended to 1,000-row thẻ kho; test synthetic pagination and keep pharmacy return/void/reconciliation cases open."})
    state["blocks"]["security"]["next"] = "SEC-011 extended to selected result-file and ultrasound-image routes, static only. Test role/assignment matrix with synthetic identities across API, PostgREST RPC, file keys, export and cross-clinic negative controls."
    state["summary"] = {
        "findings": len(findings),
        "severity": dict(severity),
        "evidence_levels": dict(levels),
        "main_status": dict(main_status),
        "main_files": len(manifest["files"]),
        "main_partial_traces": coverage["traced"],
        "main_coverage": dict(coverage),
        "code_like_source_files": {
            "definition": state["summary"]["code_like_source_files"]["definition"],
            "total": sum(code.values()),
            "coverage": dict(code),
            "traced_is_partial": True,
        },
        "new_static_findings_v018": state["summary"].get("new_static_findings_v018", []),
        "new_findings_v019": state["summary"].get("new_findings_v019", []),
        "new_findings_v020": state["summary"].get("new_findings_v020", []),
        "new_findings_v021": state["summary"].get("new_findings_v021", []),
        "new_findings_v022": [item["id"] for item in FINDINGS],
    }
    state["blocks"]["security"]["findings"] = "PHAT-HIEN.json (canonical integrated; SEC-001..SEC-015)"
    state["blocks"]["clinical"]["findings"] = "PHAT-HIEN.json (canonical integrated; CLIN-001..CLIN-027)"
    state["blocks"]["finance"]["findings"] = "PHAT-HIEN.json (canonical integrated; FIN-001..FIN-008; PHAR-001)"
    state["artifacts"]["integration_script"] = "integrate_v022.py"
    state["artifacts"].pop("html_sha256", None)
    state["artifacts"].pop("html_checked_at", None)
    state["artifacts"].pop("bundle_verified_at", None)
    state["runtime_summary"]["worker_lease_race"] = "RUN-043: generic callback overlap reproduced, 1 passed in 0.20s on synthetic disposable DB; business consumer/provider side effect not tested; template seed caveat applies."
    state["runtime_summary"]["round6_worklists_booking_relay"] = "CLIN-023..027, FE-010, INF-012 are exact-main static traces; no cap-volume/browser/concurrent booking/relay batch runtime probe. FIN-002 and SEC-011 extended with selected static paths."
    state["runtime_summary"]["audit_report_qc"] = "v0.21 prior artifact QA only; rebuild v0.22 and rerun structural/browser checks before handoff."
    write_json("STATE.json", state)

    # Update independent handoff documents after canonical counts are computed.
    state = read_json("STATE.json")
    counts_line = (
        f"Checkpoint **v0.22** tích hợp {len(findings)} hồ sơ: {severity['HIGH']} HIGH, {severity['MEDIUM']} MEDIUM; "
        f"{levels['reproduced_local']} reproduced_local, {levels['confirmed_static']} confirmed_static, "
        f"{levels['design_gap']} design_gap, {levels['hypothesis']} hypothesis. Trong phạm vi đã đối chiếu main: "
        f"{main_status['still_present_on_main']} vẫn hiện diện, {main_status['partially_addressed_on_main']} partial, "
        f"{main_status['addressed_on_main']} addressed. Ledger {len(manifest['files']):,} file: "
        f"{coverage['traced']:,} traced một phần, {coverage['scanned']:,} scanned, "
        f"{coverage['inventoried']:,} inventoried, {coverage['excluded']:,} excluded. Full audit còn dang dở."
    )
    handoff = ROOT / "TIEP-TUC.md"
    old = handoff.read_text()
    old = old.replace("Checkpoint **v0.21**", "Checkpoint **v0.22**", 1)
    old = old.replace("71 hồ sơ", f"{len(findings)} hồ sơ", 1)
    old = old.replace("21 HIGH, 50 MEDIUM", f"{severity['HIGH']} HIGH, {severity['MEDIUM']} MEDIUM", 1)
    old = old.replace("21\n`reproduced_local`, 38 `confirmed_static`, 11 `design_gap`, 1 `hypothesis`.", f"{levels['reproduced_local']}\n`reproduced_local`, {levels['confirmed_static']} `confirmed_static`, {levels['design_gap']} `design_gap`, {levels['hypothesis']} `hypothesis`.", 1)
    old = old.replace("67 vẫn hiện diện", f"{main_status['still_present_on_main']} vẫn hiện diện", 1)
    old = old.replace("278 traced", f"{coverage['traced']} traced", 1)
    old = old.replace("2.054 scanned", f"{coverage['scanned']:,} scanned", 1)
    old = old.replace("262 traced", f"{code['traced']} traced", 1)
    old = old.replace("2.050 scanned", f"{code['scanned']:,} scanned", 1)
    old = old.replace("HTML/ZIP v0.21 đã được dựng", "HTML/ZIP v0.22 đang được dựng", 1)
    old = old.replace("RUN-043", "RUN-043", 1)
    section = "## v0.22 mới tích hợp\n\n" + counts_line + "\n\n"
    section += "RUN-043 tái hiện generic stale worker callback vẫn commit sau reclaim; chưa chứng minh consumer nghiệp vụ/provider bị gọi trùng. Findings mới: " + ", ".join(item["id"] for item in FINDINGS) + "; FIN-002/SEC-011 được mở rộng. Khi tiếp quản, kiểm QA HTML/ZIP theo RUN mới nhất trước, rồi theo next_action.\n\n"
    if "## v0.22 mới tích hợp" not in old:
        old = section + old
    handoff.write_text(old)
    print(f"Integrated v0.22: {len(findings)} findings, {upgraded} ledger paths upgraded to partial trace; report/bundle need rebuild and QA.")


if __name__ == "__main__":
    main()
