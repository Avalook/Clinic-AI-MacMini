"""Integrate the 19 Oct 2026 patient/configuration/routing audit checkpoint."""

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
        "id": "SEC-013",
        "title": "Nhật ký tạo bệnh nhân giữ nguyên CCCD và thông tin liên hệ",
        "severity": "HIGH",
        "evidence_level": "confirmed_static",
        "category": "privacy_authorization",
        "summary": "Sự kiện patient.created lưu họ tên, ngày sinh, hai số điện thoại và số CCCD nguyên văn trong event_log. Endpoint audit lấy payload đó và trả lại cho người có audit.view; chính sách database cho phép Quản lý, Trưởng ca và CSKH đọc nhật ký cùng phòng khám.",
        "trigger": "Nhân viên có quyền tạo hồ sơ nhập dữ liệu liên hệ/CCCD; sau đó người có quyền audit.view mở nhật ký trong ngày.",
        "impact": "CCCD và dữ liệu liên hệ được nhân bản sang nhật ký vận hành append-only, mở rộng số người và thời gian lưu so với hồ sơ gốc; bản sao cũng đi theo backup và export của event_log.",
        "evidence": [
            proof("src/clinicai/services/patient_service.py", 211, 237, "patient.created ghi PII trực tiếp vào payload."),
            proof("src/clinicai/services/audit_log_service.py", 68, 88, "Đường đọc audit chọn nguyên cột payload từ v_audit_log."),
            proof("src/clinicai/services/audit_log_service.py", 215, 240, "DTO trả payload đã giải mã cho màn audit."),
            proof("src/clinicai/api/v1/routers/audit_log.py", 22, 36, "Endpoint yêu cầu audit.view; clinic lấy từ identity."),
            proof("supabase/migrations/20260803000004_realtime_and_audit_scope.sql", 54, 64, "Policy cho các vai MANAGEMENT, TRUONG_CA, CSKH đọc audit của clinic."),
        ],
        "validation": {"method": "static_cross_path_trace", "command": None, "result": "Đối chiếu liên tục đường ghi patient.created → v_audit_log → AuditLogService → endpoint và policy vai.", "limitations": "Không truy cập dữ liệu bệnh nhân thật, production log hay backup; không chạy HTTP/DB test cho finding này."},
        "recommendation": "Giữ trong audit mã hồ sơ và danh sách trường đã thay đổi; không lưu CCCD/SĐT nguyên văn trong event payload. Nếu nghiệp vụ bắt buộc cần bản chụp dữ liệu, lưu ở vùng hạn chế quyền, có thời hạn lưu và che khi đọc nhật ký.",
        "acceptance": "Test xác nhận payload patient.created không chứa CCCD hoặc số điện thoại nguyên văn; audit vẫn truy ra hồ sơ và ai tạo; migration/retention xử lý dữ liệu lịch sử theo chính sách được duyệt.",
        "alignment": ["Quyết định dựa trên bằng chứng tốt hơn", "Lỗi lặp lại dần biến thành cải tiến hệ thống"],
        "related_tests": ["src/tests/unit/test_patient_service.py"],
    },
    {
        "id": "CLIN-013",
        "title": "Cảnh báo trùng số bỏ sót số điện thoại phụ đã khai",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "patient_identity_integrity",
        "summary": "Lookup và cảnh báo trùng xét patient_sdt_them, nhưng guard trong create_patient chỉ so phone_primary và phone_secondary.",
        "trigger": "Số được nhập cho hồ sơ mới chỉ khớp một số phụ của hồ sơ hiện có; người gọi create_patient với force=false.",
        "impact": "Server có thể tạo hồ sơ thứ hai thay vì trả cảnh báo trùng, làm lịch sử cùng một bệnh nhân tách thành nhiều hồ sơ.",
        "evidence": [
            proof("src/clinicai/services/patient_service.py", 187, 202, "Guard create_patient chỉ so hai cột phone_primary/phone_secondary."),
            proof("src/clinicai/services/patient_service.py", 384, 398, "get_by_phone còn xét patient_sdt_them."),
            proof("src/clinicai/services/patient_service.py", 418, 432, "find_phone_duplicates cũng xét patient_sdt_them."),
        ],
        "validation": {"method": "static_cross_path_trace", "command": None, "result": "Đối chiếu ba truy vấn trong PatientService: create guard thiếu EXISTS, trong khi lookup và check-duplicate có truy vấn số phụ.", "limitations": "Chưa gọi API hoặc tái hiện trên DB; cảnh báo UI hiện tại có thể giúp nhân viên phát hiện trước khi lưu."},
        "recommendation": "Dùng một truy vấn/điều kiện trùng số chung cho create guard, lookup và endpoint check-duplicate; chuẩn hóa số trước khi so và giữ cơ chế force có lý do nếu số dùng chung.",
        "acceptance": "Case chỉ khớp patient_sdt_them trả duplicate ở API create khi force=false; case force=true lưu được nhưng yêu cầu lý do theo đúng hợp đồng.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Lỗi lặp lại dần biến thành cải tiến hệ thống"],
        "related_tests": ["src/tests/test_nhieu_so_dien_thoai.py", "src/tests/unit/test_patient_service.py"],
    },
    {
        "id": "CLIN-014",
        "title": "PATCH hồ sơ cho phép gán bệnh nhân vào cơ sở đã ngừng hoạt động",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "patient_identity_integrity",
        "summary": "create_patient kiểm tra clinic_location.is_active; update_patient nhận location_id qua DTO và cho phép cột này trong _UPDATE_COLUMNS nhưng không kiểm tra cơ sở còn hoạt động.",
        "trigger": "Client gọi PATCH /patients/{id} với location_id thuộc cơ sở cùng clinic nhưng is_active=false.",
        "impact": "Hồ sơ sau cập nhật bị gắn vào cơ sở đã đóng dù luồng tạo hồ sơ từ chối cùng giá trị. UI hiện tại không cung cấp chọn cơ sở nên đường tác động là API.",
        "evidence": [
            proof("src/clinicai/services/patient_service.py", 122, 145, "Luồng tạo đọc và từ chối cơ sở không tồn tại/đã ngừng hoạt động."),
            proof("src/clinicai/schemas/patient.py", 164, 174, "PatientUpdateDTO nhận location_id."),
            proof("src/clinicai/services/patient_service.py", 461, 480, "update_patient chấp nhận mọi cột trong _UPDATE_COLUMNS và không kiểm tra trạng thái location."),
            proof("src/clinicai/api/v1/patients.py", 319, 328, "PATCH endpoint gọi thẳng update_patient."),
        ],
        "validation": {"method": "static_cross_path_trace", "command": None, "result": "Đối chiếu validation create, DTO update, danh sách cột cho phép và PATCH route.", "limitations": "Chưa gọi HTTP/DB. PatientAdminEditor không có trường đổi cơ sở theo lát UI đã xem."},
        "recommendation": "Xác thực location_id trong cùng transaction update: phải thuộc clinic và còn hoạt động; nếu cần cho phép sửa hồ sơ lịch sử sang cơ sở đã đóng, tạo lệnh riêng có quyền và lý do.",
        "acceptance": "Test PATCH từ chối location khác clinic và location inactive; cho phép location active đúng clinic; ghi audit field-only.",
        "alignment": ["Ownership ngày càng rõ hơn", "Quyết định dựa trên bằng chứng tốt hơn"],
        "related_tests": ["src/tests/services/test_sua_ho_so_khach_db.py"],
    },
    {
        "id": "SEC-014",
        "title": "Tắt hết phạm vi vị trí của một vai khiến guard lịch trực mở lại toàn quyền",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "authorization_fail_open",
        "summary": "_kiem_pham_vi_tram lọc is_active rồi cho qua khi không còn dòng. Điều này gộp hai trạng thái khác nhau: ma trận chưa từng khai và ma trận đã khai nhưng quản lý chủ động tắt mọi ô.",
        "trigger": "Quản lý tắt tất cả dòng của một vai qua PUT /roster/station-scope; nhân viên thuộc vai đó gửi POST /roster/shifts vào bất kỳ station.",
        "impact": "Guard backend cho phép vai đã bị cấu hình không có phạm vi nào vào mọi vị trí, kể cả vị trí không được phép theo chính ma trận. GET /roster/stations cũng báo chua_khai=true.",
        "evidence": [
            proof("src/clinicai/services/config_service.py", 409, 427, "Query bỏ dòng is_active=false và fail-open khi kết quả rỗng."),
            proof("src/clinicai/services/config_service.py", 484, 521, "Lệnh tắt giữ lại dòng is_active=false; cấu hình có thể phân biệt với chưa từng khai."),
            proof("src/clinicai/services/config_service.py", 459, 472, "Đường đọc cũng gắn chua_khai=true cho trường hợp mọi dòng đã tắt."),
            proof("src/clinicai/api/v1/routers/config.py", 279, 294, "PUT cấu hình và endpoint đọc station scope."),
        ],
        "validation": {"method": "static_trace_plus_existing_unit_test_review", "command": ".venv/bin/pytest -q src/tests/unit/test_pham_vi_vi_tri_lich_truc.py", "result": "Agent kiểm tra độc lập báo 11 passed; test hiện xác nhận empty chưa khai thì cho qua nhưng không kiểm tra trạng thái có dòng inactive cho toàn vai.", "limitations": "Unit test dùng FakeConn/FakePool; chưa chạy DB/HTTP. Hành vi fail-open khi chưa khai là chủ ý để hỗ trợ onboarding, nhưng trạng thái all-disabled phải được phân biệt."},
        "recommendation": "Truy vấn đồng thời cả cờ đã cấu hình (EXISTS bất kỳ dòng) và danh sách active. Chỉ fail-open khi thật sự chưa từng khai; đã cấu hình mà active set rỗng thì từ chối mọi station và báo rõ cho quản lý.",
        "acceptance": "Test 3 trạng thái: chưa có dòng cho phép theo chế độ onboarding; có mapping active chỉ cho phép mapping; tất cả dòng inactive từ chối mọi station và trả chua_khai=false.",
        "alignment": ["Ownership ngày càng rõ hơn", "Con người bị gián đoạn ít hơn nhưng đúng lúc hơn"],
        "related_tests": ["src/tests/unit/test_pham_vi_vi_tri_lich_truc.py", "src/tests/services/test_truong_ca_xep_lich_db.py"],
    },
    {
        "id": "INF-010",
        "title": "Thay đổi phạm vi xếp lịch không có audit trail bền vững trong ứng dụng",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "audit_history_completeness",
        "summary": "dat_vi_tri_cho_vai cập nhật quyền vai × vị trí rồi chỉ ghi logger.info; không thêm event_log/audit record. Màn nhật ký thao tác đọc v_audit_log và work_item_event.",
        "trigger": "Quản lý bật/tắt một ô ma trận vị trí, sau đó cần điều tra vì sao lịch của một nhân viên được xếp vào trạm đó.",
        "impact": "Người vận hành không truy lại được từ màn audit ai đổi phạm vi, đổi gì và lúc nào. Dòng dữ liệu giữ is_active/ghi_chu nhưng không lưu actor hoặc lịch sử trước/sau.",
        "evidence": [
            proof("src/clinicai/services/config_service.py", 501, 523, "Upsert ma trận và log ứng dụng, không gọi record_event hoặc event_log."),
            proof("src/clinicai/services/audit_log_service.py", 68, 106, "Audit UI hợp nhất v_audit_log và work_item_event."),
            proof("supabase/migrations/20260809000002_vai_duoc_vao_tram.sql", 27, 37, "Bảng lưu cờ active/ghi_chu/created_at, không có actor hoặc lịch sử update."),
        ],
        "validation": {"method": "static_trace", "command": None, "result": "Đối chiếu lệnh cập nhật, schema ma trận và nguồn dữ liệu của audit UI.", "limitations": "Không kiểm tra retention/forwarding của logger ngoài ứng dụng; kết luận chỉ là thiếu audit record bền vững trong event log và màn audit."},
        "recommendation": "Ghi event clinic_config.roster_station_scope_changed trong cùng giao dịch với upsert, gồm actor, station, vai, trạng thái trước/sau và lý do; rà cùng tiêu chuẩn này cho các cài đặt điều hành có ảnh hưởng tới phân công.",
        "acceptance": "Màn audit truy lại được actor, clinic, ô trước/sau và thời điểm; lỗi ghi audit rollback cùng cập nhật ma trận hoặc có cơ chế outbox bền vững.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Lỗi lặp lại dần biến thành cải tiến hệ thống"],
        "related_tests": ["src/tests/unit/test_pham_vi_vi_tri_lich_truc.py"],
    },
    {
        "id": "SEC-015",
        "title": "PATCH bảng gọi số có thể bật lại tên đầy đủ dù request chỉ đổi khu vực",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "privacy_configuration",
        "summary": "DisplaySettingsRequest mặc định hien_ten=true và che_ten=false; endpoint PATCH luôn ghi cả hai mặc định vào settings, kể cả khi request chỉ gửi zones.",
        "trigger": "Client gọi PATCH /display-settings chỉ với zones sau khi clinic đã tắt tên hoặc bật che tên.",
        "impact": "Bảng gọi số công khai có thể lại hiện tên đầy đủ bệnh nhân. Endpoint hiện chưa có caller UI được tìm thấy trong snapshot, nên đường kích hoạt đã chứng minh là API nhưng tần suất sử dụng chưa rõ.",
        "evidence": [
            proof("src/clinicai/api/v1/routers/config.py", 208, 220, "Pydantic defaults bật hien_ten và tắt che_ten."),
            proof("src/clinicai/api/v1/routers/config.py", 784, 817, "PATCH đọc settings hiện tại rồi luôn ghi đè cả hai trường theo body."),
            proof("src/clinicai/services/display_board_service.py", 180, 205, "Bảng gọi số lấy hai cờ này để dựng nội dung có tên."),
        ],
        "validation": {"method": "static_trace", "command": None, "result": "Đối chiếu defaults của request, merge logic PATCH và consumer hiển thị tên.", "limitations": "Không tìm thấy caller UI trong mã đã rà; chưa gọi API/browser và chưa xác nhận cấu hình production."},
        "recommendation": "Đổi schema thành partial update với Optional[bool] và chỉ cập nhật trường có trong model_fields_set; cân nhắc mặc định ẩn/che tên trên màn công khai khi cấu hình bị thiếu.",
        "acceptance": "PATCH chỉ zones giữ nguyên hai cờ tên; PATCH có field mới chỉ đổi đúng field đó; test board xác nhận tên không lộ lại sau partial update.",
        "alignment": ["Bệnh nhân ít phải chờ trong bất định hơn", "Quyết định dựa trên bằng chứng tốt hơn"],
        "related_tests": ["src/tests/services/test_display_board.py"],
    },
    {
        "id": "CLIN-016",
        "title": "Cấu hình phòng có thể đổi sau kiểm tra nhưng trước khi xếp dịch vụ commit",
        "severity": "MEDIUM",
        "evidence_level": "reproduced_local",
        "category": "configuration_race",
        "summary": "assign giữ FOR SHARE trên clinic_room khi gọi phong_lam_duoc, nhưng set_room_nodes và set_service_rooms không khóa cùng dòng phòng. Một writer có thể thay mapping sau eligibility check trong khi route transaction còn mở.",
        "trigger": "Lệnh assign kiểm tra phòng làm được; quản lý đồng thời xóa node của phòng hoặc thu hẹp dịch vụ sang phòng khác; lệnh assign tiếp tục commit.",
        "impact": "service_order và hàng chờ có thể được ghi ASSIGNED vào phòng mà cấu hình mới không còn cho phép. Hướng ngược lại cũng có thể từ chối theo cấu hình cũ khi vừa thêm mapping.",
        "evidence": [
            proof("src/clinicai/services/service_routing_service.py", 1249, 1296, "assign mở transaction, kiểm quyền, khóa lượt và gọi lõi assign."),
            proof("src/clinicai/services/service_routing_service.py", 1373, 1400, "_gan kiểm tra revision, trạng thái và gọi _kiem_phong trước khi ghi."),
            proof("src/clinicai/services/service_routing_service.py", 1428, 1465, "Sau kiểm tra, cùng transaction cập nhật queue và service_order ASSIGNED."),
            proof("src/clinicai/services/service_routing_service.py", 2365, 2405, "_kiem_phong khóa clinic_room nhưng eligibility đọc mapping node/service."),
            proof("src/clinicai/services/clinic_config_service.py", 975, 1024, "set_room_nodes xóa/chèn mapping mà không khóa clinic_room."),
            proof("src/clinicai/services/clinic_config_service.py", 1184, 1247, "set_service_rooms khóa service_price rồi thay mapping; không khóa room đang được route kiểm tra."),
        ],
        "validation": {"method": "synthetic_concurrent_database_probe", "command": "scripts/test-nhanh.sh src/tests/services/test_audit_1910_routing_config_race_db.py -x -q", "result": "1 passed trên DB tạm: test giữ lệnh route sau eligibility check, thêm mapping thu hẹp dịch vụ sang phòng khác, xác nhận phòng cũ không còn eligible nhưng assign vẫn commit ASSIGNED vào phòng cũ.", "limitations": "Probe gọi service assign thật trên DB tạm; phần writer dùng cùng khóa service_price và thao tác clinic_room_service như config writer, không gọi HTTP hoặc ClinicConfigService đầy đủ. Không chạm production."},
        "recommendation": "Thiết lập một protocol khóa chung giữa route và cấu hình, ví dụ khóa các room/mapping theo thứ tự ổn định, hoặc version hóa cấu hình và kiểm version trong transaction trước commit. Cấu hình đổi cần tạo việc rà/xếp lại những route đang hoạt động bị ảnh hưởng.",
        "acceptance": "Kiểm thử cạnh tranh chứng minh writer config hoặc route phải đợi/nhận conflict; không trạng thái ASSIGNED nào commit vào room không eligible theo version cấu hình commit cuối; các route bị ảnh hưởng có owner xử lý.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Ownership ngày càng rõ hơn", "Lỗi lặp lại dần biến thành cải tiến hệ thống"],
        "related_tests": ["src/tests/services/test_audit_1910_routing_config_race_db.py", "src/tests/services/test_service_routing_db.py"],
    },
    {
        "id": "CLIN-017",
        "title": "Lệnh hoàn tác Xong không khóa vào đúng lần làm đã hoàn tất",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "stale_command_target",
        "summary": "Undo nhận order_id nhưng không nhận attempt_id hoặc execution revision; trong transaction nó chọn lần COMPLETED có attempt_no lớn nhất rồi mở lại lần đó.",
        "trigger": "Một request undo cũ của lần #1 bị trì hoãn; dịch vụ đã chạy lại và lần #2 hoàn tất trước khi request cũ được xử lý.",
        "impact": "Lệnh dự định hoàn tác lần #1 có thể làm mở lần #2. UI gửi mã chỉ định và body xác nhận/lý do, không gắn mục tiêu vào attempt cụ thể.",
        "evidence": [
            proof("src/clinicai/services/hoan_tac_service.py", 895, 948, "Service chỉ nhận order_id rồi chọn COMPLETED attempt_no lớn nhất."),
            proof("src/clinicai/services/hoan_tac_service.py", 993, 1003, "Attempt được chọn chuyển về IN_PROGRESS."),
            proof("src/clinicai/api/v1/routers/hoan_tac.py", 68, 83, "Route chỉ truyền order_id, lý do và xác nhận."),
            proof("src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx", 890, 903, "Nút hoàn tác gửi mã chỉ định, không gửi attempt id/revision."),
        ],
        "validation": {"method": "static_cross_path_trace", "command": None, "result": "Đối chiếu service query thứ tự attempt, route request contract và lệnh nút hoàn tác.", "limitations": "Chưa tái hiện request bị trì hoãn hoặc test DB có lần #2; existing test chỉ undo lần hoàn tất hiện tại rồi lặp khi chưa có completion mới."},
        "recommendation": "Yêu cầu attempt_id và expected_execution_revision trong body; khóa lượt/order, xác nhận attempt đó đang COMPLETED và revision đúng trước khi đổi trạng thái.",
        "acceptance": "Stale undo của attempt #1 bị 409 sau khi attempt #2 được tạo/hoàn tất; lệnh có attempt_id/revision hiện hành chỉ ảnh hưởng đúng attempt mục tiêu.",
        "alignment": ["Ownership ngày càng rõ hơn", "Quyết định dựa trên bằng chứng tốt hơn"],
        "related_tests": ["src/tests/services/test_hoan_tac_moi_thao_tac_db.py"],
    },
    {
        "id": "CLIN-018",
        "title": "Lần làm tại bàn khám lưu routing revision cũ hơn sự kiện xếp phòng",
        "severity": "MEDIUM",
        "evidence_level": "confirmed_static",
        "category": "audit_history_completeness",
        "summary": "Khi start tại bàn khám tự gán/chuyển phòng, service tăng routing_revision và phát event với rev_xep mới; attempt snapshot lại lấy don.routing_revision đã đọc trước cập nhật.",
        "trigger": "Bác sĩ bắt đầu một chỉ định chưa có phòng hoặc chuyển chỉ định sang phòng của bàn khám.",
        "impact": "service_execution_attempt.routing_revision_snapshot thấp hơn một bước so với routing_revision của trạng thái và event cùng lần bắt đầu; hiện chưa làm sai trạng thái chạy nhưng làm yếu đối chiếu lịch sử/sự cố.",
        "evidence": [
            proof("src/clinicai/services/service_execution_service.py", 1296, 1333, "UPDATE tăng revision và event service.routed mang revision mới."),
            proof("src/clinicai/services/service_execution_service.py", 1334, 1353, "INSERT attempt lại truyền don.routing_revision cũ."),
        ],
        "validation": {"method": "static_data_lineage_trace", "command": None, "result": "Cùng service path đối chiếu giá trị RETURNING rev_xep với tham số routing_revision_snapshot.", "limitations": "Chưa có DB assertion so snapshot với event; ảnh hưởng được xác nhận là provenance của revision, không phải trạng thái execution hiện thời."},
        "recommendation": "Lấy revision trả về từ UPDATE hoặc đọc revision mới sau update trong cùng transaction và dùng cùng giá trị cho event lẫn attempt snapshot.",
        "acceptance": "DB test cho cả gán phòng ban đầu và chuyển phòng bàn khám xác nhận attempt snapshot, service_order và event đều cùng routing_revision.",
        "alignment": ["Reality ngày càng dễ nhìn thấy hơn", "Quyết định dựa trên bằng chứng tốt hơn"],
        "related_tests": ["src/tests/services/test_dieu_tri_ban_kham_db.py"],
    },
]


def main() -> None:
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    manifest = read_json("MAIN-PHAM-VI.json")
    by_path = {item["path"]: item for item in manifest["files"]}

    partial_notes = {
        "src/clinicai/services/patient_service.py": "Round 4: trace create phone guard vs extra-phone lookup, inactive location update, patient.created PII payload; not full service review.",
        "src/clinicai/services/audit_log_service.py": "Round 4: trace payload selection/return for privacy and config-audit paths; not full service review.",
        "src/clinicai/api/v1/routers/audit_log.py": "Round 4: trace audit.view endpoint/clinic identity for patient PII access scope; not full router review.",
        "src/clinicai/api/v1/routers/config.py": "Round 4: trace roster station-scope and display-settings routes/models; not full router review.",
        "src/clinicai/services/config_service.py": "Round 4: trace roster station-scope empty/all-disabled behavior, write and audit path; not full service review.",
        "src/clinicai/services/service_routing_service.py": "Round 4: selected trace of recommend/assign/transfer/invalidate/eligibility and routing/config race; not whole-file review.",
        "src/clinicai/services/clinic_config_service.py": "Round 4: trace room-node/service mapping writers and compare locks with service routing; not full service review.",
        "src/clinicai/services/service_execution_service.py": "Round 4: selected trace of desk-start room assignment and attempt revision snapshot; not full service review.",
        "src/clinicai/services/hoan_tac_service.py": "Round 4: selected trace of undo completion target selection; not full service review.",
        "src/clinicai/api/v1/routers/hoan_tac.py": "Round 4: trace undo-completion request contract only; not full router review.",
        "src/clinicai/api/v1/patients.py": "Round 4: trace patient update endpoint contract only; not full router review.",
        "src/clinicai/schemas/patient.py": "Round 4: trace PatientUpdateDTO location_id boundary only; not full schema review.",
        "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx": "Round 4: trace undo button payload only; not full component review.",
        "src/dashboard/app/display/DisplayBoard.tsx": "Round 4: checked display-settings consumer reference; not full UI review.",
        "src/tests/services/test_service_routing_db.py": "Round 4: reviewed existing routing test boundaries; not full test-file review.",
        "src/tests/services/test_hoan_tac_moi_thao_tac_db.py": "Round 4: reviewed undo-completion existing test coverage; not full test-file review.",
        "src/tests/services/test_dieu_tri_ban_kham_db.py": "Round 4: reviewed desk-start test coverage for revision snapshot; not full test-file review.",
        "src/tests/services/test_sua_ho_so_khach_db.py": "Round 4: reviewed update-location test boundary; not full test-file review.",
        "src/tests/test_nhieu_so_dien_thoai.py": "Round 4: reviewed extra-phone lookup coverage vs create duplicate guard; not full test-file review.",
        "src/tests/unit/test_pham_vi_vi_tri_lich_truc.py": "Round 4: independent review reports 11 passing unit cases; test intentionally covers never-configured fail-open but not all-disabled.",
        "src/tests/services/test_display_board.py": "Round 4: referenced display-name rendering controls; not full test-file review.",
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

    existing = read_json("PHAT-HIEN.json")
    ids = {f["id"] for f in existing}
    if any(f["id"] in ids for f in FINDINGS):
        raise SystemExit("One or more v0.20 finding IDs already exist; refusing duplicate integration.")

    for finding in FINDINGS:
        source_hashes = {}
        source_evidence = []
        for item in finding["evidence"]:
            source = SNAPSHOT / item["path"]
            raw = source.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            source_hashes[item["path"]] = digest
            lines = source.read_text().splitlines()
            excerpt = "\n".join(
                f"{n}: {lines[n - 1]}"
                for n in range(item["line"], item["end_line"] + 1)
            )
            source_evidence.append({
                "path": item["path"],
                "line": item["line"],
                "end_line": item["end_line"],
                "sha256": digest,
                "excerpt": excerpt,
            })
        finding["source_hashes"] = source_hashes
        finding["status"] = "open"
        finding["main_validation"] = {
            "sha": SHA,
            "status": "still_present_on_main",
            "note": "Đối chiếu trực tiếp snapshot main ghim; source excerpt và SHA-256 lưu kèm. Không suy ra hành vi production.",
            "evidence": source_evidence,
            "production_verified": False,
        }
    all_findings = existing + FINDINGS
    write_json("PHAT-HIEN.json", all_findings)
    write_json("MAIN-PHAM-VI.json", manifest)

    checks = read_json("KIEM-CHUNG.json")
    known = {(item.get("id"), item.get("path")) for item in checks["checks"]}
    for finding in FINDINGS:
        for path in finding["source_hashes"]:
            pair = (finding["id"], path)
            if pair not in known:
                checks["checks"].append({"id": finding["id"], "path": path, "valid": True})
    write_json("KIEM-CHUNG.json", checks)

    runs = read_json("TEST-RUNS.json")
    if not any(run["id"] == "RUN-038" for run in runs):
        runs.append({
            "id": "RUN-038",
            "at": now,
            "environment": "DB test tạm được scripts/test-nhanh.sh clone từ khuôn cũ rồi áp các migration exact-main; không gọi production/API bên ngoài.",
            "command": "scripts/test-nhanh.sh src/tests/services/test_audit_1910_routing_config_race_db.py -x -q",
            "exit_code": 0,
            "result": "1 passed: sau eligibility check, service mapping đổi sang phòng khác; phòng vừa bị loại vẫn được assign commit ASSIGNED.",
            "limitations": [
                "Probe gọi ServiceRoutingService.assign thật; writer dùng cùng service_price lock và clinic_room_service update pattern, không gọi HTTP hoặc ClinicConfigService đầy đủ.",
                "Chạy trên DB disposable và dữ liệu clinic/visit synthetic; không chứng minh đã xảy ra ở production.",
                "Khuôn DB test ghi main@27e010d6 từ 14/10; script áp 42 migration hiện có trong snapshot 956ba4f2 vào DB tạm trước khi chạy. Khuôn dùng chung không bị thay đổi.",
            ],
        })
    write_json("TEST-RUNS.json", runs)

    coverage = Counter(item["status"] for item in manifest["files"])
    code_suffixes = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".sh", ".bash", ".go", ".rs", ".java", ".kt", ".css", ".html"}
    code = Counter(item["status"] for item in manifest["files"] if Path(item["path"]).suffix.lower() in code_suffixes)
    severity = Counter(f["severity"] for f in all_findings)
    evidence_levels = Counter(f["evidence_level"] for f in all_findings)
    main_status = Counter(f["main_validation"]["status"] for f in all_findings)
    state = read_json("STATE.json")
    state["updated_at"] = now
    state["phase"] = "patient_privacy_roster_scope_config_race_and_execution_provenance_checkpoint"
    state["next_action"] = "Continue read-only semantic review of remaining exact-main inventory. Prioritize API/RPC authorization, restore/migration and worker retry paths, remaining patient/clinical result lifecycles, and major frontend data flows. Keep all evidence partial where only selected spans were traced; do not mark full source audit complete."
    state["report_status"] = "v0.20_65_findings_new_route_race_reproduced; HTML and bundle rebuild/QA pending; full source audit incomplete"
    state["limits"].append("RUN-038 reproduced a configuration-versus-routing race on a disposable DB using the production assign service and a synthetic mapping writer; HTTP/full ClinicConfigService/production behavior were not tested.")
    state["limits"].append("Round 4 customer identity/configuration/undo findings are static traces unless individually stated; no PHI or production behavior was accessed.")
    state["summary"] = {
        **state["summary"],
        "findings": len(all_findings),
        "severity": dict(severity),
        "evidence_levels": dict(evidence_levels),
        "main_status": dict(main_status),
        "main_partial_traces": coverage["traced"],
        "main_coverage": {"inventoried": coverage["inventoried"], "traced": coverage["traced"], "scanned": coverage["scanned"], "excluded": coverage["excluded"]},
        "code_like_source_files": {"definition": state["summary"]["code_like_source_files"]["definition"], "total": sum(code.values()), "coverage": {"inventoried": code["inventoried"], "traced": code["traced"], "scanned": code["scanned"], "excluded": code["excluded"]}, "traced_is_partial": True},
        "new_findings_v020": [f["id"] for f in FINDINGS],
    }
    state["primary_reference"]["ref"] = "Immutable Git object pinned by full SHA; do not rely on mutable origin/main for continuation."
    state["runtime_summary"]["routing_config_race"] = "RUN-038: 1 passed on disposable exact-source test DB; route assignment committed to a room after service mapping was narrowed away concurrently. HTTP and production not tested."
    write_json("STATE.json", state)

    print(f"Integrated {len(FINDINGS)} findings; upgraded {upgraded} files to traced-partial.")
    print(f"Main coverage: {dict(coverage)}; code-like coverage: {dict(code)}")
    print(f"Severity: {dict(severity)}; evidence: {dict(evidence_levels)}; main status: {dict(main_status)}")


if __name__ == "__main__":
    main()
