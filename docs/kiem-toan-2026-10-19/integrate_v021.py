"""Integrate the next exact-main audit checkpoint without touching app code."""

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
        "id": "CLIN-019",
        "title": "Thu hồi tệp kết quả duy nhất không mở lại hạn theo dõi của đối tác",
        "severity": "MEDIUM",
        "evidence_level": "design_gap",
        "category": "result_lifecycle",
        "summary": "Khi đối tác đã bấm Trả kết quả, hệ thống đặt `service_order.ket_qua_luc`. Nếu tệp hiệu lực duy nhất sau đó bị thu hồi trước khi bác sĩ đọc và không còn form/kết quả chữ thay thế, thao tác thu hồi đổi file sang THU_HOI nhưng không gỡ marker. H7 chỉ tạo timer khi marker NULL; đến hạn, handler coi marker khác NULL là đã xong và bỏ qua. Đây là khoảng trống có điều kiện: code chủ ý nói hoàn tác marker bằng lệnh Hoàn tác trả kết quả, nên cần chốt liệu thu hồi tệp có phải tự mở lại việc theo dõi hay phải tạo handoff rõ ràng cho người xử lý.",
        "trigger": "Đối tác trả một tệp kết quả; tệp duy nhất bị thu hồi trước khi vòng đọc kết quả bắt đầu/đóng; không còn tệp, form READY hoặc result_note hiệu lực; timer H7 chạy.",
        "impact": "Hệ thống không tạo thông báo quá hạn cho CSKH dù view kết quả hiệu lực rỗng. Nếu thu hồi đồng nghĩa kết quả không còn dùng được và không có người thực hiện lệnh hoàn tác, bệnh nhân có thể chờ mà không có owner nhắc đối tác.",
        "evidence": [
            proof("src/clinicai/services/doi_tac_service.py", 802, 865, "Đối tác yêu cầu có kết quả hiệu lực khi trả; lệnh đặt ket_qua_luc và phát partner.result_returned."),
            proof("src/clinicai/services/tep_ket_qua_service.py", 541, 560, "Helper tính lại marker cố ý loại công việc đối tác."),
            proof("src/clinicai/services/tep_ket_qua_service.py", 1210, 1223, "Thu hồi chuyển tệp sang THU_HOI nhưng không gọi helper gỡ marker."),
            proof("src/clinicai/events/consumers/hanh_trinh.py", 343, 363, "H7 chỉ đặt timer khi service_order.ket_qua_luc IS NULL."),
            proof("src/clinicai/events/consumers/hanh_trinh.py", 366, 376, "Handler hạn kết quả bỏ qua khi marker còn khác NULL."),
            proof("supabase/migrations/20260930700000_xoa_mem_tep.sql", 147, 152, "View tệp hiệu lực không bao gồm tệp đã thu hồi."),
        ],
        "validation": {
            "method": "synthetic_disposable_db_service_event_timer_probe",
            "command": "DATABASE_URL= PYTHONPATH=src scripts/test-nhanh.sh /tmp/probe_revoked_result_h7.py -q -s",
            "result": "1 passed (~0,27 giây) theo note follow-up: gọi upload, DoiTacService.tra_ket_qua, thu hồi tệp, xử lý event và H7; xác nhận view active-result rỗng, ket_qua_luc vẫn khác NULL, timer thành BO_QUA và không tạo thông báo quá hạn.",
            "limitations": "DB dùng một lần với dữ liệu giả; test source và raw stdout đã bị xóa sau run, kết quả được lưu trong blocks/scheduling-result-revoke-h7-followup.md. Runner áp 42 migration còn thiếu vào DB dùng lại; không kiểm tra dữ liệu production hay gửi notification bên ngoài. Chỉ phát sinh khi không có result khác; cần xác nhận quy trình nghiệp vụ vì code có nút hoàn tác trả kết quả riêng.",
        },
        "recommendation": "Khi thu hồi tệp duy nhất sau marker trả kết quả, hoặc tính lại marker và tạo lại H7 trong cùng transaction, hoặc tạo việc có owner/đích hạn yêu cầu người dùng xác nhận hoàn tác marker. Làm rõ trạng thái ‘đã gửi kết quả’ khác ‘kết quả còn hiệu lực’.",
        "acceptance": "Synthetic DB: trả kết quả → thu hồi tệp hiệu lực cuối cùng → marker/việc theo dõi chuyển về trạng thái cần xử lý và có đúng một timer/owner; tệp/form/note còn hiệu lực thì không tạo nhắc sai; undo/ retry không nhân đôi.",
        "alignment": ["Khoảng thời gian Unknown ngày càng ngắn hơn", "Ownership ngày càng rõ hơn", "Bệnh nhân ít phải chờ trong bất định hơn"],
        "related_tests": ["src/tests/services/test_hanh_trinh_db.py", "src/tests/services/test_ket_qua_chuong_hanh_trinh_db.py"],
    },
    {
        "id": "CLIN-020",
        "title": "Phiếu khám v5 ghi được sau FINALIZED mà không qua luồng đính chính",
        "severity": "MEDIUM",
        "evidence_level": "design_gap",
        "category": "clinical_record_integrity",
        "summary": "Route lưu phiếu khám v5 gọi `PhieuKhamService.luu_luot`, service luôn truyền CHE_DO_MO và chỉ kiểm tra visit tồn tại; probe synthetic đã lưu thành công một phiếu cho visit FINALIZED mà không có amendment/reason. Đây là mâu thuẫn hợp đồng: module v5 ghi rằng hoàn tất không khóa và sửa tiếp được, trong khi chế độ phiếu định nghĩa FINALIZED_LOCKED/amendment_mode và clinical record service từ chối ghi FINALIZED. Chưa kết luận ý định lâm sàng cuối cùng của riêng phiếu v5.",
        "trigger": "Người có quyền phiếu gọi PUT /phieu-kham/luot/{visit_id}/phieu với visit đã FINALIZED.",
        "impact": "Nếu FINALIZED là mốc bất biến theo contract/UI lâm sàng, nội dung phiếu có thể đổi sau khi chốt mà không có lý do, người duyệt hoặc amendment. Nếu phiếu v5 chủ ý được sửa tiếp, các màn/hợp đồng khác đang nói sai và người dùng không hiểu điều gì thực sự đã được chốt.",
        "evidence": [
            proof("src/clinicai/services/phieu_kham_service.py", 105, 109, "Module phiếu ghi rõ hoàn tất không khóa, phiếu sửa tiếp được."),
            proof("src/clinicai/services/phieu_kham_service.py", 413, 427, "luu_luot luôn lưu chế độ editable và chỉ kiểm tra visit tồn tại."),
            proof("src/clinicai/api/v1/routers/phieu_kham.py", 177, 193, "PUT route chuyển dữ liệu thẳng vào service; request không có reason/amendment."),
            proof("src/clinicai/phieu_kham/che_do.py", 1, 14, "Contract phiếu khám mô tả FINALIZED_LOCKED và amendment_mode, fail-closed khi thiếu chế độ."),
            proof("src/clinicai/services/clinical_record_service.py", 97, 103, "Clinical shell định nghĩa trạng thái có thể ghi; FINALIZED/AMENDED là bất biến."),
            proof("src/clinicai/services/clinical_record_service.py", 603, 607, "Service từ chối hồ sơ đã chốt và yêu cầu đính chính."),
        ],
        "validation": {
            "method": "synthetic_disposable_db_service_probe_with_real_permission_check",
            "command": "scripts/test-nhanh.sh src/tests/services/test_audit_1910_lifecycle_probe_db.py -q",
            "result": "Probe báo 2 passed; case FINALIZED gọi luu_luot thành công, revision tăng 1, visit vẫn FINALIZED, visit_amendment không có dòng mới.",
            "limitations": "Dữ liệu synthetic trên DB dùng một lần; gọi service và quyền kiem_quyen_core thật nhưng không gọi HTTP middleware/browser. Probe source tạm đã xóa; policy cho riêng module v5 cần chủ nghiệp vụ chốt. Không dùng production/PHI.",
        },
        "recommendation": "Chốt một quy tắc duy nhất cho mọi loại hồ sơ: khóa FINALIZED, hoặc cho phép sửa có revision/reason/approval và audit rõ. Truyền trạng thái/chế độ từ clinical shell vào v5; không để module tự mặc định editable khi thiếu ngữ cảnh.",
        "acceptance": "DB+HTTP matrix: editable visit lưu bình thường; FINALIZED bị từ chối hoặc tạo amendment có reason/actor/approval theo chính sách đã duyệt; mọi màn hiển thị cùng trạng thái chốt.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Quyết định dựa trên bằng chứng tốt hơn", "Lỗi lặp lại dần biến thành cải tiến hệ thống"],
        "related_tests": ["src/tests/services/test_phieu_kham_service.py", "src/tests/services/test_clinical_record_service_db.py"],
    },
    {
        "id": "CLIN-021",
        "title": "API in kết quả chọn bản sửa mới nhất dù phiên bản đó chưa được release",
        "severity": "MEDIUM",
        "evidence_level": "design_gap",
        "category": "result_release_control",
        "summary": "Khi bản v1 READY đã release rồi được sửa thành v2, `FormEngineService.in_ket_qua` vẫn lấy form_instance và trả v2 với `ban_nhap=false` dù form_result_release chỉ có v1. Query in không join/check release version. Migration mô tả bảng release hiện chưa được đường in/gửi kết quả có cấu trúc sử dụng; đây là khoảng trống nếu endpoint in được coi là đường phát hành kết quả chính thức. Không tìm thấy endpoint gửi kết quả có cấu trúc trong lát đã rà; tệp kết quả là luồng riêng.",
        "trigger": "Một kết quả cấu trúc được release ở version 1, có result correction tạo version 2 nhưng chưa release v2; người dùng gọi GET /phieu/in/{service_order_id}.",
        "impact": "Đường in có thể trả nội dung chỉnh sửa chưa được duyệt dưới nhãn không phải bản nháp. Nếu in/trao bản này cho bệnh nhân, người nhận không thể phân biệt giữa version được release và version chờ duyệt.",
        "evidence": [
            proof("src/clinicai/services/form_engine_service.py", 403, 422, "Query in lấy form_instance theo clinic+service_order, không kiểm form_result_release."),
            proof("src/clinicai/api/v1/routers/phieu.py", 199, 208, "Endpoint in mô tả trả bản chính thức hoặc nháp có nhãn BẢN NHÁP."),
            proof("supabase/migrations/20260923000014_sua_ket_qua_giu_ban_cu.sql", 150, 160, "Migration nói bảng release chưa được hỏi bởi đường in/gửi và chỉ tạo hàng rào khi kiểm đúng ban_thu hiện hành."),
        ],
        "validation": {
            "method": "synthetic_disposable_db_service_probe",
            "command": "scripts/test-nhanh.sh src/tests/services/test_audit_1910_lifecycle_probe_db.py -q",
            "result": "Probe báo 2 passed; release v1, sửa thành v2 mà không release v2, gọi in_ket_qua vẫn trả v2 với ban_nhap=false.",
            "limitations": "Synthetic DB và gọi service trực tiếp; không test HTTP middleware, browser, in thật hoặc gửi Zalo. Migration xác nhận đây là nền chưa được nối vào cổng phát hành, nên cần xác nhận policy trước khi coi là lỗi nghiệp vụ hiện hữu.",
        },
        "recommendation": "Nếu release là cổng phát hành, query in phải khóa vào đúng ban_thu có release hiện hành; nếu chưa release thì trả nháp có nhãn hoặc từ chối. Bản sửa phải thu hồi/đánh dấu bản cũ theo quy tắc rõ và audit actor/reason.",
        "acceptance": "Release v1 → sửa v2: endpoint in không trả v2 như bản chính thức cho tới khi release v2; v1/v2, actor, thời điểm duyệt và reason truy lại được; các template cũ có chính sách riêng được test.",
        "alignment": ["Quyết định dựa trên bằng chứng tốt hơn", "Bệnh nhân ít phải chờ trong bất định hơn"],
        "related_tests": ["src/tests/services/test_sua_ket_qua_db.py", "src/tests/services/test_form_engine_service_db.py"],
    },
    {
        "id": "CLIN-022",
        "title": "Danh sách CSKH liệu trình cắt ở 200 khách mà không báo còn dữ liệu",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "worklist_completeness",
        "summary": "LieuTrinhService gắn `LIMIT 200` cho các danh sách CSKH và response chỉ trả mảng, không total/has_more/cursor. UI hiển thị `ds.length` là số khách và render hết mảng mà không nói danh sách bị cắt. Khi một nhóm có hơn 200 khách đủ điều kiện, các khách sau 200 không xuất hiện trong worklist hiện tại.",
        "trigger": "Một nhóm đề xuất/đang dở/sắp hết liệu trình có hơn 200 khách thuộc cùng clinic và người CSKH mở danh sách.",
        "impact": "Các hồ sơ quá ngưỡng không có trong danh sách xử lý; nhân viên có thể hiểu 200 là toàn bộ số cần gọi và không biết còn việc chưa nhìn thấy.",
        "evidence": [
            proof("src/clinicai/services/lieu_trinh_service.py", 62, 67, "TRAN_DANH_SACH được cố định ở 200."),
            proof("src/clinicai/services/lieu_trinh_service.py", 810, 817, "Mọi nhóm được truy vấn với LIMIT nhưng không gắn metadata phân trang."),
            proof("src/clinicai/api/v1/routers/lieu_trinh.py", 64, 76, "API trả trực tiếp kết quả service, không thêm total/has_more."),
            proof("src/dashboard/app/(dashboard)/nhac-tai-kham/LieuTrinhCskh.tsx", 65, 99, "UI chỉ hiện ds.length và render mảng; không có phân trang/cảnh báo cắt."),
        ],
        "validation": {
            "method": "static_service_api_ui_trace",
            "command": None,
            "result": "Đối chiếu limit service, response router và danh sách UI; chưa chạy dataset >200.",
            "limitations": "Ảnh hưởng chỉ xuất hiện nếu một nhóm vượt 200; chưa kiểm dữ liệu production, không suy số khách thực tế. Đây là trace chọn lọc, không phải review cả module.",
        },
        "recommendation": "Thêm cursor/limit rõ ràng và total hoặc has_more; giao diện phải nêu số đang hiển thị trên tổng hoặc nút xem tiếp, tránh tự gọi 200 là toàn bộ.",
        "acceptance": "Fixture có ít nhất 205 khách: có thể xem/điều phối đủ 205 qua pagination; giao diện thể hiện tổng và trạng thái còn trang; dữ liệu không bị trùng/mất khi có cập nhật giữa các trang.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Khoảng thời gian Unknown ngày càng ngắn hơn", "Ownership ngày càng rõ hơn"],
        "related_tests": ["src/tests/services/test_lieu_trinh_db.py"],
    },
    {
        "id": "FE-009",
        "title": "Dashboard từ chối tài khoản nhân viên có nhiều clinic membership đang hoạt động",
        "severity": "MEDIUM",
        "evidence_level": "design_gap",
        "category": "multi_tenant_product_capability",
        "summary": "Schema và FastAPI tenant selector hỗ trợ một nhân viên có membership ở nhiều clinic, nhưng dashboard login gọi `resolveSingleActiveMembership` và sign out nếu số membership active khác đúng một. Trang `/chon-co-so` chỉ chọn location bên trong clinic hiện hành; backend-proxy chỉ gắn X-Location-ID. Đây là giới hạn sản phẩm cho nhóm clinic/nhân viên luân phiên, không phải bypass hay rò dữ liệu chéo tenant.",
        "trigger": "Cùng một staff/auth account có hai hoặc nhiều clinic_membership active và đăng nhập dashboard.",
        "impact": "Đăng nhập bị từ chối; tổ chức nhiều cơ sở pháp lý/clinic phải tắt membership hoặc duy trì tài khoản trùng, làm tăng chi phí vận hành và nguy cơ lịch sử phân mảnh. Hiện chưa đủ cơ sở nói đây là blocker cho single-clinic target market.",
        "evidence": [
            proof("supabase/migrations/20260730000003_multi_tenant_foundation.sql", 44, 67, "Schema ghi rõ staff có thể thuộc nhiều clinic, role gắn theo membership."),
            proof("src/clinicai/api/identity.py", 324, 341, "Backend nhận X-Clinic-ID như selector và nói multi-clinic phải chọn tường minh."),
            proof("src/clinicai/api/identity.py", 443, 510, "Backend lọc active membership theo clinic đã chọn và từ chối trường hợp không xác định."),
            proof("src/dashboard/app/(auth)/login/actions.ts", 54, 65, "Login chỉ chấp nhận đúng một active clinic membership, còn lại sign out."),
            proof("src/dashboard/lib/identity-authority.ts", 47, 56, "Helper dashboard chỉ trả một membership khi có đúng một; comment chưa có clinic selector."),
            proof("src/dashboard/app/(auth)/chon-co-so/page.tsx", 11, 34, "Trang chọn hiện hành lấy danh sách cơ sở trong clinic, không chọn tenant."),
            proof("src/dashboard/lib/backend-proxy.ts", 115, 124, "Proxy gắn auth/API key và location header; không có X-Clinic-ID."),
        ],
        "validation": {
            "method": "static_identity_flow_and_tenant_contract_trace",
            "command": None,
            "result": "Đối chiếu ADR/schema, FastAPI selector và membership guard, GoTrue login, helper authority, location picker và proxy header. Helper unit tests hiện không test clinic switch.",
            "limitations": "Không chạy login/browser với tài khoản tổng hợp; không kiểm toàn bộ RLS/tenant routes. Hành vi từ chối là fail-closed có chủ ý cho tới khi có selector, không phải lỗ phân quyền.",
        },
        "recommendation": "Nếu sản phẩm nhắm nhóm clinic, thêm màn chọn clinic sau xác thực; giữ selector riêng với location, gửi X-Clinic-ID cho request và để backend xác minh membership active mỗi lần. Giữ role lấy từ membership đã xác thực, không từ body/cookie tự do.",
        "acceptance": "Tài khoản có hai clinic active đăng nhập được và phải chọn rõ; switch clinic cập nhật context/queries/realtime đồng nhất; request forged clinic khác membership bị 403; user một clinic vẫn vào thẳng.",
        "alignment": ["Ownership ngày càng rõ hơn", "Reality ngày càng dễ nhìn thấy hơn"],
        "related_tests": ["src/dashboard/tests/identity-authority-boundary.test.mts"],
    },
    {
        "id": "INF-011",
        "title": "POS dead-letter chưa có màn owner và quy trình khôi phục",
        "severity": "MEDIUM",
        "evidence_level": "design_gap",
        "category": "operational_recovery",
        "summary": "POS outbox ghi trạng thái DEAD và log lỗi; adapter none/misconfigured chuyển giao dịch sang DEAD. Lát API/dashboard exact-main không thấy consumer pos_outbox; health đếm event_delivery và hen_gio nhưng không đếm POS. Vì vậy chưa có nơi để người vận hành xem giao dịch, nhận ownership, sửa cấu hình và retry/reconcile. POS relay đang opt-in và adapter tích hợp hiện chưa hoàn thiện; đây là cổng trước khi bán/bật POS, không phải bằng chứng sự cố đang xảy ra.",
        "trigger": "Clinic bật profile POS hoặc phát sinh payment/stock outbox trong khi adapter bị tắt, thiếu credential, lỗi hết retry hoặc cấu hình sai.",
        "impact": "Tiền đã di chuyển trong ClinicAI nhưng POS ngoài không biết giao dịch; nếu không có cảnh báo và quy trình đối soát, staff không nhìn thấy việc cần sửa hoặc có thể xử lý lại thủ công trùng lặp.",
        "evidence": [
            proof("src/clinicai/services/pos_config.py", 42, 98, "Adapter none/thiếu credential/unknown trả NullPosAdapter."),
            proof("src/clinicai/services/pos_relay.py", 105, 113, "Null adapter đưa dòng vào DEAD thay vì giả báo gửi thành công."),
            proof("src/clinicai/services/pos_relay.py", 192, 216, "Dead-letter chỉ update DB và log; không có owner/assignment action ở đây."),
            proof("src/clinicai/api/v1/health.py", 68, 105, "Health của worker đếm event_delivery và hen_gio, không đếm pos_outbox."),
            proof("supabase/migrations/20260730000007_pos_outbox.sql", 17, 52, "Schema giữ PENDING/SENT/DEAD, attempts, last_error và external_ref."),
            proof("docker-compose.yml", 260, 284, "POS relay tách profile pos và opt-in."),
            proof("src/tests/test_pos_relay.py", 194, 205, "Test xác nhận adapter tắt thành DEAD nhưng chưa test dashboard/operator recovery."),
        ],
        "validation": {
            "method": "static_worker_api_dashboard_and_schema_trace",
            "command": None,
            "result": "Đã rà relay/config/schema/test/health và tìm tham chiếu pos_outbox trong API/dashboard exact-main; không thấy consumer/operator path.",
            "limitations": "Static selected slice; chưa chạy POS relay, provider thật, HTTP/admin UI hay lỗi production. Feature được ghi rõ opt-in/chưa hoàn thiện; cần hoàn tất trước khi bật cho clinic.",
        },
        "recommendation": "Trước khi bật POS, cung cấp queue theo clinic với trạng thái/giá trị/subject, lỗi đã làm sạch, owner, thời điểm và nút retry an toàn/reconcile; thêm alert/SLO, idempotency bằng external reference và audit mọi thao tác thủ công.",
        "acceptance": "Synthetic adapter failure tạo DEAD nhìn thấy trong dashboard/health có alert; staff được ủy quyền gán owner và retry/reconcile idempotent; retry không tạo invoice/void trùng; mọi action có audit actor và kết quả.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Ownership ngày càng rõ hơn", "Vấn đề được phát hiện sớm hơn"],
        "related_tests": ["src/tests/test_pos_relay.py"],
    },
]


def snapshot_evidence(evidence: list[dict]) -> tuple[list[dict], dict[str, str]]:
    rendered = []
    hashes = {}
    for item in evidence:
        source = SNAPSHOT / item["path"]
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        lines = source.read_text().splitlines()
        if item["line"] < 1 or item["end_line"] > len(lines):
            raise ValueError(f"Invalid evidence range: {item}")
        excerpt = "\n".join(
            f"{n}: {lines[n - 1]}"
            for n in range(item["line"], item["end_line"] + 1)
        )
        rendered.append({
            "path": item["path"],
            "line": item["line"],
            "end_line": item["end_line"],
            "sha256": digest,
            "excerpt": excerpt,
        })
        hashes[item["path"]] = digest
    return rendered, hashes


def append_extension(finding: dict, evidence: list[dict], *, summary: str | None = None) -> None:
    rendered, hashes = snapshot_evidence(evidence)
    existing_keys = {
        (item["path"], item["line"], item["end_line"])
        for item in finding["main_validation"]["evidence"]
    }
    new_items = [
        item for item in rendered
        if (item["path"], item["line"], item["end_line"]) not in existing_keys
    ]
    finding["main_validation"]["evidence"].extend(new_items)
    finding["source_hashes"].update(hashes)
    finding["evidence"].extend(evidence)
    if summary:
        finding["summary"] = summary


def main() -> None:
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"Missing pinned source snapshot: {SNAPSHOT}")
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    findings = read_json("PHAT-HIEN.json")
    existing = {finding["id"]: finding for finding in findings}
    ids = {finding["id"] for finding in FINDINGS}
    if ids & existing.keys():
        raise SystemExit(f"Refusing duplicate finding IDs: {sorted(ids & existing.keys())}")

    for finding in FINDINGS:
        rendered, hashes = snapshot_evidence(finding["evidence"])
        finding["source_hashes"] = hashes
        finding["status"] = "open"
        finding["reference_version"] = "pinned_main"
        finding["main_validation"] = {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "Đối chiếu source exact-main; behavior chỉ được khẳng định ở mức evidence nêu dưới đây, không suy ra production.",
            "evidence": rendered,
            "production_verified": False,
        }

    # Expand the existing object-scope finding instead of duplicating one actor/root cause.
    append_extension(
        existing["SEC-011"],
        [
            proof("supabase/migrations/20260915000007_prescription_draft_column_privacy.sql", 22, 44, "Authenticated SECURITY DEFINER RPC checks clinic and role but not TKYK patient assignment; final ACL grants EXECUTE."),
            proof("supabase/migrations/20260915000021_thu_ky_rls_theo_bac_si.sql", 16, 69, "Assignment helper defines which patient TKYK may see."),
            proof("supabase/migrations/20260915000021_thu_ky_rls_theo_bac_si.sql", 98, 115, "Restrictive table policies apply the assignment helper to visit-scoped clinical records."),
            proof("supabase/migrations/20261019100000_harden_public_function_acl.sql", 37, 39, "Final migration retains authenticated EXECUTE on read_prescription_draft."),
            proof("src/clinicai/services/lieu_trinh_service.py", 453, 456, "Treatment-plan read guard checks QUYEN_DOC capability only."),
            proof("src/clinicai/services/lieu_trinh_service.py", 500, 522, "Read by caller-supplied clinic_patient_id performs no assignment check."),
            proof("src/clinicai/services/lieu_trinh_service.py", 541, 563, "Read by caller-supplied visit_id performs no assignment check."),
        ],
        summary=(
            existing["SEC-011"]["summary"]
            + " Bổ sung các mặt cùng root cause: RPC PostgREST `read_prescription_draft(uuid)` là SECURITY DEFINER, role+clinic gate nhưng không gọi patient assignment guard; và API đọc liệu trình theo patient/visit cũng chỉ kiểm capability QUYEN_DOC."
        ),
    )
    existing["SEC-011"]["validation"]["limitations"] += (
        " RPC read_prescription_draft chưa được kiểm qua JWT/PostgREST DB runtime; các đường liệu trình cũng mới static trace."
    )

    # Preserve the known pharmacy finding while extending its route-level proof.
    append_extension(
        existing["PHAR-001"],
        [proof("src/clinicai/api/v1/routers/pharmacy.py", 1342, 1372, "FastAPI /pharmacy/khach-tra gọi service thật dưới capability và Idempotency-Key." )],
        summary=(
            "Đường khách trả thuốc gọi _hoan_phan_tra trước khi ghi drug_return trong cùng transaction. Helper chỉ tìm cycle PAID/PENDING_VERIFICATION; nếu phiếu đã VOIDED thì HOAN lỗi và rollback cả ghi nhận hàng trả. Probe ASGI trên DB giả xác nhận HOAN 409, GIU_LAI 200; tổng phải thu/ phải trả vẫn 50.000/0 và không có ledger medicine.returned, vì vậy cần owner xử lý đường GIU_LAI."
        ),
    )
    existing["PHAR-001"]["validation"] = {
        "method": "actual_pharmacy_service_and_fastapi_asgi_postgres_synthetic",
        "command": "PATH=/tmp/clinicai-audit-no-fetch-bin:$PATH TEST_NHANH_PYTHON=.venv/bin/python scripts/test-nhanh.sh src/tests/services/test_audit_1910_voided_return_http_probe.py -q",
        "result": "Disposable synthetic DB probe: pay→dispense→void; POST HOAN trả 409 và không ghi drug_return; GIU_LAI trả 200. General refund service trên cycle VOIDED là control thành công. PHAI_THU=50.000/PHAI_TRA=0 không đổi qua GIU_LAI; không có so_no row cho medicine.returned. 1 passed, 1 warning in 1.53s.",
        "limitations": "Probe source tạm đã xóa; captured command/output và seed/template caveat nằm trong probes/HTTP-VOIDED-RETURN-PROBE.txt. DB `tam_92618_dr4women_macmini` dùng khuôn main@27e010d6 rồi áp 42 migration còn thiếu; seed trong khuôn khác pinned seed. Không phải fresh bootstrap, không truy cập production hoặc cổng thanh toán. DOI chưa chạy trực tiếp; số dư cần chốt theo ý nghĩa nghiệp vụ của VOIDED.",
    }
    existing["PHAR-001"]["main_validation"]["note"] += (
        " Bổ sung HTTP ASGI synthetic probe: HOAN 409, GIU_LAI 200; không chứng minh production."
    )

    # Extend the existing lease/fencing hypothesis to the timer worker.
    append_extension(
        existing["INF-005"],
        [
            proof("src/clinicai/events/hen_gio.py", 129, 167, "Timer callback chạy sau claim transaction; finish update chỉ WHERE id, không ownership token."),
            proof("src/clinicai/events/hen_gio.py", 227, 238, "Reclaim timer quá lease trả về CHO không generation fencing."),
        ],
        summary=existing["INF-005"]["summary"] + " Cùng failure class xuất hiện ở hen_gio: callback chạy ngoài claim transaction; reclaim và kết thúc theo id, không theo token thế hệ/worker.",
    )
    existing["INF-005"]["validation"]["limitations"] += (
        " Timer hen_gio cũng mới static trace; chưa có slow-handler DB probe hai worker."
    )

    findings.extend(FINDINGS)
    write_json("PHAT-HIEN.json", findings)

    manifest = read_json("MAIN-PHAM-VI.json")
    by_path = {item["path"]: item for item in manifest["files"]}
    partial_notes = {
        "src/clinicai/services/doi_tac_service.py": "Round 5: trace partner return marker/undo against result-file revoke and H7; not full service review.",
        "src/clinicai/services/tep_ket_qua_service.py": "Round 5: trace result revoke/recalculation and H7 consumer lifecycle; not full service review.",
        "src/clinicai/events/consumers/hanh_trinh.py": "Round 5: trace H7 scheduling/due handler after partner result revoke; not full consumer review.",
        "src/clinicai/services/phieu_kham_service.py": "Round 5: trace finalized save policy for phiếu v5; not full service review.",
        "src/clinicai/api/v1/routers/phieu_kham.py": "Round 5: trace v5 save route contract; not full router review.",
        "src/clinicai/phieu_kham/che_do.py": "Round 5: compare declared phiếu modes against v5 service save; not full package review.",
        "src/clinicai/services/clinical_record_service.py": "Round 5: compare FINALIZED write contract against phiếu v5; selected spans only.",
        "src/clinicai/services/form_engine_service.py": "Round 5: trace result print selection against release-version table; not full service review.",
        "src/clinicai/api/v1/routers/phieu.py": "Round 5: trace structured result print endpoint contract only; not full router review.",
        "src/clinicai/services/lieu_trinh_service.py": "Round 5: trace CSKH list cap and object-scope reads; not full service review.",
        "src/clinicai/api/v1/routers/lieu_trinh.py": "Round 5: trace CSKH list response and read guards; not full router review.",
        "src/dashboard/app/(dashboard)/nhac-tai-kham/LieuTrinhCskh.tsx": "Round 5: trace worklist count/render behavior for capped lists; not full UI review.",
        "src/dashboard/app/(auth)/login/actions.ts": "Round 5: trace active clinic membership behavior at login; not full auth flow review.",
        "src/dashboard/lib/identity-authority.ts": "Round 5: trace single-clinic dashboard authority helper; not full identity library review.",
        "src/dashboard/app/(auth)/chon-co-so/page.tsx": "Round 5: trace location selector vs multi-clinic tenant selector; not full page review.",
        "src/dashboard/lib/backend-proxy.ts": "Round 5: trace tenant/location headers on backend proxy; not full proxy review.",
        "src/clinicai/services/pos_config.py": "Round 5: trace POS null/misconfigured adapter behavior; not full integration review.",
        "src/clinicai/services/pos_relay.py": "Round 5: trace POS delivery/dead-letter operator path; not full relay review.",
        "src/clinicai/api/v1/health.py": "Round 5: trace worker health counters for POS dead letters; not full health router review.",
        "src/clinicai/events/hen_gio.py": "Round 5: trace timer claim/reclaim fencing as INF-005 extension; not full worker review.",
    }
    upgraded = 0
    for path, note in partial_notes.items():
        item = by_path.get(path)
        if item is None:
            continue
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
    for finding_id in ("SEC-011", "PHAR-001", "INF-005"):
        for path in existing[finding_id]["source_hashes"]:
            if (finding_id, path) not in known:
                checks["checks"].append({"id": finding_id, "path": path, "valid": True})
    write_json("KIEM-CHUNG.json", checks)

    runs = read_json("TEST-RUNS.json")
    new_runs = [
        {
            "id": "RUN-039",
            "at": now,
            "environment": "DB disposable `chung_test_db`, local; synthetic visit/order/result/file/timer data; pinned source 956ba4f2.",
            "command": "DATABASE_URL= PYTHONPATH=src scripts/test-nhanh.sh /tmp/probe_revoked_result_h7.py -q -s",
            "exit_code": 0,
            "result": "1 passed (~0,27s): revoke-only-result leaves ket_qua_luc set; active result view empty; H7 ends BO_QUA and creates no overdue notification.",
            "limitations": [
                "Probe source and raw stdout were removed/not retained; detailed secondhand run note is blocks/scheduling-result-revoke-h7-followup.md.",
                "Runner applied 42 migrations to a disposable DB; no production data or external delivery was used.",
                "Conditional on absence of another effective file/form/note; clinic policy may require explicit undo rather than automatic marker reset.",
            ],
        },
        {
            "id": "RUN-040",
            "at": now,
            "environment": "FastAPI ASGI + disposable DB `tam_92618_dr4women_macmini`; synthetic medicine payment/dispense/return; pinned application/migrations, stale reusable seed template.",
            "command": "PATH=/tmp/clinicai-audit-no-fetch-bin:$PATH TEST_NHANH_PYTHON=.venv/bin/python scripts/test-nhanh.sh src/tests/services/test_audit_1910_voided_return_http_probe.py -q",
            "exit_code": 0,
            "result": "1 passed, 1 warning (1.53s): API HOAN returns 409; GIU_LAI returns 200; no medicine.returned ledger row; PHAI_THU=50,000 and PHAI_TRA=0 before/after GIU_LAI.",
            "limitations": [
                "Transient probe source removed; combined output is retained at probes/HTTP-VOIDED-RETURN-PROBE.txt.",
                "DB template main@27e010d6 differed from pinned seed and runner applied 42 missing migrations; not a fresh bootstrap validation.",
                "No production, provider, real patient data or external payment call.",
            ],
        },
        {
            "id": "RUN-041",
            "at": now,
            "environment": "Disposable synthetic DB under exact source 956ba4f2; no production/PHI.",
            "command": "scripts/test-nhanh.sh src/tests/services/test_audit_1910_lifecycle_probe_db.py -q",
            "exit_code": 0,
            "result": "2 passed: FINALIZED v5 save increments revision without amendment/reason; un-released v2 is returned by in_ket_qua as not-draft.",
            "limitations": [
                "Probe source was removed after run; agent reported 2 passed in 0.36s. Service-level only, not HTTP/browser/external delivery.",
                "The result-revision release gate is conditional on intended product policy; source migration describes the release table as not yet wired to print/send.",
            ],
        },
    ]
    run_ids = {run["id"] for run in runs}
    runs.extend(run for run in new_runs if run["id"] not in run_ids)
    write_json("TEST-RUNS.json", runs)

    severity = Counter(f["severity"] for f in findings)
    evidence_levels = Counter(f["evidence_level"] for f in findings)
    main_status = Counter(f["main_validation"]["status"] for f in findings)
    coverage = Counter(item["status"] for item in manifest["files"])
    suffixes = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html"}
    code = Counter(item["status"] for item in manifest["files"] if Path(item["path"]).suffix.lower() in suffixes)

    state = read_json("STATE.json")
    state["updated_at"] = now
    state["phase"] = "clinical_result_lifecycle_multi_clinic_product_and_worklist_checkpoint"
    state["next_action"] = (
        "Continue exact-main selected semantic review; prioritize untraced auth/RLS routes, "
        "remaining clinical records/result and partner lifecycles, worker fencing/retry, "
        "payment/return reconciliation, major dashboard data flows, and clean-install/restore. "
        "Keep path traces partial; do not claim full-source completion until the ledger is reviewed."
    )
    state["report_status"] = "v0.21_71_findings_result_h7_reproduced; HTML/package rebuild QA pending; full source audit incomplete"
    state["limits"].extend([
        "RUN-039 synthetic DB probe: H7 suppresses reminder after sole partner result file is revoked while ket_qua_luc remains non-null; probe source/raw stdout not retained, no external delivery/prod.",
        "RUN-040 pharmacy return ASGI probe uses a reusable DB template with stale seed plus 42 pinned migrations; not a fresh bootstrap, and VOIDED receivable/payable semantics need owner decision.",
        "RUN-041 v5 FINALIZED save and unreleased result print probes were service-level; policy for phiếu v5 and structured release gate remains to be decided.",
        "Round 5 identity/worker findings are selected static traces; multi-clinic dashboard is a product-capability gap, POS DLQ is opt-in and not yet recovery-tested.",
    ])
    state["summary"] = {
        **state["summary"],
        "findings": len(findings),
        "severity": dict(severity),
        "evidence_levels": dict(evidence_levels),
        "main_status": dict(main_status),
        "main_partial_traces": coverage["traced"],
        "main_coverage": {key: coverage[key] for key in ("inventoried", "traced", "scanned", "excluded")},
        "code_like_source_files": {
            "definition": state["summary"]["code_like_source_files"]["definition"],
            "total": sum(code.values()),
            "coverage": {key: code[key] for key in ("inventoried", "traced", "scanned", "excluded")},
            "traced_is_partial": True,
        },
        "new_findings_v021": [finding["id"] for finding in FINDINGS],
    }
    state["runtime_summary"].update({
        "result_revoke_h7": "RUN-039: 1 synthetic DB pass; revoking sole active partner result leaves completion marker, H7 timer is BO_QUA, no overdue notice. Conditional, no prod/external delivery; raw test source removed.",
        "pharmacy_return_after_void_http": "RUN-040: ASGI+disposable DB 1 pass, 1 warning; HOAN 409 and GIU_LAI 200; no ledger row for medicine.returned. Stale template/42 migration caveat in retained note.",
        "clinical_form_lifecycle": "RUN-041: 2 synthetic DB passes; finalized v5 writes without amendment and print returns un-released v2; service-level only and product policy remains open.",
        "multi_clinic_dashboard": "Exact-main static trace: schema/backend support explicit clinic membership selection; dashboard rejects more than one active clinic; product capability gap, no tenant bypass found in this slice.",
        "pos_dead_letter": "Exact-main static slice: DEAD rows have no API/dashboard operator recovery path; POS relay is opt-in and adapter incomplete; gate before enabling/selling POS integration.",
    })
    state["artifacts"]["integration_script"] = "integrate_v021.py"
    write_json("STATE.json", state)

    print(f"Integrated {len(FINDINGS)} findings and extended SEC-011/PHAR-001/INF-005.")
    print(f"Upgraded {upgraded} paths to partial trace. Coverage: {dict(coverage)}")
    print(f"Severity: {dict(severity)}; evidence: {dict(evidence_levels)}; main status: {dict(main_status)}")


if __name__ == "__main__":
    main()
