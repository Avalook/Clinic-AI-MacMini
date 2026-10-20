"""Integrate round-19 static audit slices into durable audit artifacts.

This script edits only the audit folder. All source evidence is extracted from
the immutable exact-main worktree and fingerprinted before being recorded.
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


def evidence(ref: tuple[str, int, int, str]) -> dict:
    path, start, end, detail = ref
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


def finding(
    *, id: str, title: str, severity: str, level: str, category: str,
    summary: str, trigger: str, impact: str, recommendation: str, acceptance: str,
    note: str, refs: list[tuple[str, int, int, str]],
    tests: list[str] | None = None, related: list[dict] | None = None,
    method: str = "static_cross_layer_trace_on_pinned_main",
    result: str = "Exact-main source trace confirms the described control flow and response surface.",
    limitations: str = "Static review only. No ClinicAI application test, DB, HTTP request, production runtime, secrets or patient data was used in round 19.",
) -> dict:
    main_evidence = [evidence(ref) for ref in refs]
    return {
        "id": id,
        "title": title,
        "severity": severity,
        "evidence_level": level,
        "category": category,
        "summary": summary,
        "trigger": trigger,
        "impact": impact,
        "evidence": [
            {k: e[k] for k in ("path", "line", "end_line", "detail")}
            for e in main_evidence
        ],
        "validation": {
            "method": method,
            "command": None,
            "result": result,
            "limitations": limitations,
        },
        "recommendation": recommendation,
        "acceptance": acceptance,
        "alignment": [
            "Reality dễ nhìn thấy hơn",
            "Unknown ngắn hơn",
            "Ownership rõ hơn",
            "Quyết định dựa trên bằng chứng tốt hơn",
        ],
        "related_tests": tests or [],
        "source_hashes": {path: source(path)[1] for path in sorted({r[0] for r in refs})},
        "status": "open",
        "reference_version": "pinned_main",
        "main_validation": {
            "sha": PINNED_SHA,
            "status": "still_present_on_main",
            "note": note,
            "evidence": main_evidence,
            "production_verified": False,
        },
        "related_findings": related or [],
    }


def finding_definitions() -> list[dict]:
    items = [
        finding(
            id="FE-019",
            title="Lỗi tải chuông được trình bày như không có thông báo",
            severity="MEDIUM", level="confirmed_static", category="notification_read_state",
            summary="Khi GET /api/thong-bao trả non-2xx hoặc fetch ném lỗi, docThongBao chỉ return/catch và không cập nhật trạng thái lỗi. Danh sách khởi tạo rỗng được giữ nguyên, trong khi GlobalHeader hiển thị ‘Chưa có thông báo nào’. BFF đã trả 502 đúng khi backend không tới được, nhưng client không đưa lỗi đó lên chuông.",
            trigger="Mở trang hoặc tải lại khi API thông báo chưa phản hồi, trả 502 hay mất mạng trước lần đọc thành công.",
            impact="Nhân viên có thể hiểu nhầm là không có việc, trong đó có thông báo KHẨN điều phối. Poll sau có thể phục hồi; chưa có bằng chứng thông báo bị mất vĩnh viễn hoặc sự cố production.",
            recommendation="Phân biệt loading, empty, stale và error; khi lỗi hiển thị lần cập nhật thành công gần nhất cùng nút thử lại. Chỉ dùng câu ‘không có thông báo’ sau response thành công.",
            acceptance="Synthetic cold-load 502 phải hiện lỗi/retry, không hiện empty state; response 200 với items=[] vẫn hiện empty state; lỗi sau dữ liệu cũ phải giữ dữ liệu và đánh dấu stale.",
            note="Exact-main trace: BFF phát 502 khi backend không tới được, còn client bỏ qua non-2xx và lỗi mạng; empty state dựa trên mảng đang rỗng. Lần poll sau có thể tự phục hồi.",
            refs=[
                ("src/dashboard/app/(dashboard)/NotificationContext.tsx", 140, 179, "Client bỏ qua non-2xx và lỗi mạng; lỗi không được lưu thành trạng thái render."),
                ("src/dashboard/app/(dashboard)/GlobalHeader.tsx", 488, 494, "Danh sách rỗng luôn render thông báo ‘Chưa có thông báo nào’."),
                ("src/dashboard/app/api/thong-bao/route.ts", 21, 30, "BFF trả 502 khi backend không đọc được, không trả danh sách rỗng."),
            ],
            tests=["src/tests/unit/test_cua_ngo_ghi_moi.py — kiểm filter/merge/close, không kiểm client network error.", "src/tests/services/test_chuong_mot_thong_bao_moi_nguoi_db.py — kiểm phạm vi thông báo server-side."],
            related=[{"id": "FE-004", "relationship": "Cùng kiểu empty state có thể tạo số 0 sai, nhưng FE-004 là lỗi nguồn KPI; FE-019 là lỗi tải chuông và có thể che thông báo điều phối."}],
            result="Static trace nối response 502 của BFF với client catch/return và empty state; không có client-side error branch trong đoạn render đã theo.",
        ),
        finding(
            id="FE-020",
            title="Chuông chỉ trả 50 việc đang mở và không cho xem phần còn lại",
            severity="MEDIUM", level="confirmed_static", category="notification_inbox_truncation",
            summary="ThongBaoService.cua_toi lọc việc chưa xử lý rồi sắp KHẨN trước, mới nhất sau và LIMIT 50. API trả danh sách này; GlobalHeader chỉ render items nhận được, không có has_more, cursor hay phân trang.",
            trigger="Người nhận có hơn 50 thông báo chưa xử lý cùng lúc.",
            impact="Các việc ngoài 50 dòng đầu không xem được từ chuông, dù vẫn đang mở; việc ít khẩn hoặc cũ hơn có thể bị bỏ sót. Đây là điều kiện theo số lượng, chưa kiểm tra dữ liệu production hoặc tần suất chạm ngưỡng.",
            recommendation="Tạo inbox có cursor pagination/has_more và bộ lọc đã xử lý/chưa xử lý; nếu popover chỉ giữ 50 mục gần nhất thì hiển thị rõ rằng còn việc phía sau và liên kết tới inbox đầy đủ.",
            acceptance="Fixture 51+ thông báo đang mở phải cho tải đủ trang tiếp theo, không lặp hoặc bỏ ID; số còn lại và trạng thái hoàn tất phải khớp API.",
            note="Exact-main query có LIMIT 50 và API/UI không truyền trạng thái cắt hay phân trang; tác động chỉ phát sinh khi người nhận vượt ngưỡng.",
            refs=[
                ("src/clinicai/services/thong_bao_service.py", 346, 365, "Query loại việc đã xử lý/đã ẩn, ưu tiên KHẨN rồi mới nhất và giới hạn 50."),
                ("src/dashboard/app/(dashboard)/GlobalHeader.tsx", 488, 505, "UI chỉ duyệt danh sách đã nhận; không có pagination/overflow indicator ở chuông."),
            ],
            tests=["src/tests/services/test_chuong_mot_thong_bao_moi_nguoi_db.py — chưa thấy case vượt 50 items."],
            result="Static trace xác nhận server cắt danh sách và client không có hợp đồng tiếp trang; chưa đo số dòng thật.",
        ),
        finding(
            id="CLIN-037",
            title="Bản in phiếu khám không phân biệt dữ liệu đang nhập với bản đã chốt",
            severity="MEDIUM", level="confirmed_static", category="clinical_document_release_state",
            summary="PhieuKhamService.doc_luot đọc nội dung phiếu theo visit nhưng không chọn trạng thái lượt, luôn trả che_do=editable. Trang in cho quầy đọc endpoint này và dựng nội dung hiện có mà không hiện nhãn nháp hay kiểm trạng thái lượt. Một lượt IN_PROGRESS có thể có nội dung tự lưu một phần nhưng vẫn đủ dữ liệu để tạo bản in.",
            trigger="Quầy tiếp đón/thu tiền/nhà thuốc in phiếu cho khách khi bác sĩ vẫn đang ghi hoặc chưa chốt lượt.",
            impact="Người nhận không phân biệt được tài liệu chưa hoàn tất với bản đã chốt; có thể gây chờ hỏi lại hoặc dùng nhầm nội dung chưa đủ. Chưa có bằng chứng bản in như vậy đã được giao trong production.",
            recommendation="Trả trạng thái/version phát hành cùng phiếu; chỉ in bản đã chốt, hoặc in bản nháp có watermark rõ và không gọi là phiếu chính thức. Đồng bộ quy tắc với cổng FINALIZED/amendment.",
            acceptance="Với visit IN_PROGRESS có phiếu tự lưu, preview/PDF phải bị chặn hoặc ghi rõ NHÁP; sau khi chốt, bản in phải gắn revision đã phát hành và không đổi khi có chỉnh sửa mới chưa duyệt.",
            note="Exact-main trace: endpoint đọc phiếu không lấy visit.status và trả editable; route in dành cho quầy, component in render dữ liệu hiện tại không có nhãn trạng thái.",
            refs=[
                ("src/clinicai/services/phieu_kham_service.py", 269, 302, "Đọc form row theo visit; query không chọn visit.status."),
                ("src/clinicai/services/phieu_kham_service.py", 319, 339, "Payload trả dữ liệu phiếu và che_do=editable, không kèm trạng thái release của lượt."),
                ("src/dashboard/app/print/phieu-kham/[visitId]/page.tsx", 1, 15, "Trang in được mở cho nhóm quầy/tiếp đón để in cho khách."),
                ("src/dashboard/app/print/phieu-kham/[visitId]/InPhieuKham.tsx", 373, 410, "Component lấy phiếu và đưa dữ liệu hiện tại vào bản in mà không nhãn nháp."),
            ],
            tests=["src/tests/services/test_phieu_kham_luot_db.py — đọc phiếu với RECEPTION; không kiểm nhãn/trạng thái bản in.", "src/tests/services/test_phieu_kham_db.py — fixture có visit IN_PROGRESS."],
            related=[
                {"id": "CLIN-020", "relationship": "CLIN-020 là ghi phiếu sau FINALIZED; CLIN-037 là phát hành bản in trước khi lượt chốt."},
                {"id": "CLIN-021", "relationship": "CLIN-021 là kết quả form_instance chưa release; CLIN-037 là phiếu khám v5 của visit."},
            ],
            result="Static trace nối trạng thái bị bỏ khỏi projection với luồng in dành cho quầy; không chạy UI hoặc in tài liệu thật.",
        ),
        finding(
            id="CLIN-038",
            title="Backend cho phép gắn mẫu kết quả sai dịch vụ vào chỉ định",
            severity="MEDIUM", level="confirmed_static", category="clinical_form_service_binding",
            summary="Khi chưa có gợi ý mẫu theo service_code, chon_mau đánh dấu mọi mẫu cua_dich_vu=True. UI chỉ chặn lựa chọn được đánh dấu false. POST /phieu/mo kiểm quyền và mẫu đã xuất bản nhưng không đối chiếu form_id với service_code của service_order_id; service_order_id chỉ được dùng cho giới hạn việc đối tác. Vì vậy request có quyền phù hợp có thể mở form loại khác dưới một chỉ định dịch vụ.",
            trigger="Người có quyền điền kết quả mở chỉ định dịch vụ A bằng form_id của dịch vụ B, đặc biệt khi mapping/gợi ý chưa được cấu hình.",
            impact="Kết quả sai loại có thể được lưu và hiển thị dưới chỉ định đó; bác sĩ hoặc khách hàng có thể hiểu nhầm dữ liệu là kết quả của dịch vụ đã đặt. Chưa tái hiện qua HTTP/DB hay thấy sự cố thực tế.",
            recommendation="Kiểm tra quan hệ form–service ở backend trong cùng clinic; chỉ cho phép mẫu gắn với dịch vụ hoặc mẫu CHUNG được duyệt. Thiếu mapping phải trả chưa xác minh/không cho lưu, không tự coi mọi mẫu là hợp lệ.",
            acceptance="API phải từ chối form không gắn với service order; mẫu CHUNG được duyệt vẫn hoạt động; test bao gồm doctor/partner, cùng clinic, service/form đúng và sai.",
            note="Exact-main trace: client kiểm cua_dich_vu, nhưng backend mo_phieu kiểm permission + published form và không xác nhận form/service binding.",
            refs=[
                ("src/clinicai/phieu_kham/mau_goi_y.py", 64, 89, "Không có gợi ý thì mọi form được trả cua_dich_vu=True."),
                ("src/dashboard/app/(dashboard)/_lam-viec/PhieuKetQua.tsx", 420, 447, "Việc chặn form khác dịch vụ chỉ nằm trong UI."),
                ("src/clinicai/api/v1/routers/phieu.py", 65, 78, "Route nhận service_order_id và form_id rồi gọi service."),
                ("src/clinicai/services/form_engine_service.py", 176, 207, "Service kiểm quyền, form_definition published và tạo form_instance; không đối chiếu form với service của chỉ định."),
            ],
            tests=["src/tests/services/test_ket_qua_chung_lam_them_db.py — xác nhận mẫu không ánh xạ được đánh dấu cho phép; không kiểm API từ chối mẫu sai dịch vụ."],
            result="Static call trace xác nhận validation cua_dich_vu ở client không có bản kiểm tương đương trong FormEngineService.mo_phieu.",
        ),
        finding(
            id="CLIN-039",
            title="Hai người sửa cùng ô phiếu khám có thể ghi đè nhau mà cả hai tab báo đã lưu",
            severity="MEDIUM", level="confirmed_static", category="clinical_form_concurrent_edit",
            summary="ServiceFormEngine tính các ô thay đổi trên baseline cục bộ, gửi ghep=true và đánh dấu baseline cục bộ mới là đã lưu sau bất kỳ 2xx. BFF không chuyển revision/base version. Backend khóa visit để tuần tự hóa request rồi merge JSONB theo key, nhưng không so revision. Hai tab cùng sửa một key từ baseline giống nhau nên lần ghi sau thắng mà không có 409; tab trước vẫn hiện đã tự lưu.",
            trigger="Hai nhân viên mở cùng phiếu, cùng sửa một trường lâm sàng trước khi nhận được trạng thái mới từ người kia.",
            impact="Giá trị đã lưu của người đầu bị thay thế âm thầm trong DB; tab người đầu có thể vẫn hiển thị giá trị cũ và báo đã lưu. Chưa tái hiện bằng concurrency test ở vòng này và chưa có bằng chứng occurrence production.",
            recommendation="Thêm revision compare-and-swap hoặc conflict detection theo field; trả 409 kèm bản remote mà không xóa bản local. Cho người dùng so sánh/hợp nhất và chỉ xác nhận đã lưu khi server xác nhận đúng revision.",
            acceptance="Hai request cùng base revision sửa cùng field: request sau nhận conflict có local+remote giữ nguyên; sửa field khác nhau vẫn merge nếu contract cho phép; audit giữ actor/revision và autosave không báo xanh cho bản stale.",
            note="Exact-main trace: client gửi chỉ các ô đổi nhưng không gửi revision; backend merge theo key dưới transaction mà không kiểm baseline, nên cùng key là last-writer-wins.",
            refs=[
                ("src/dashboard/app/(dashboard)/tasks/ServiceFormEngine.tsx", 160, 208, "Client diff theo baseline và đánh dấu chuỗi cục bộ đã lưu sau response 2xx."),
                ("src/dashboard/app/api/clinical-form/route.ts", 73, 119, "BFF gửi form_data/ghep/bo_truong, không gửi revision/base version."),
                ("src/clinicai/services/clinical_form_service.py", 254, 322, "Transaction khóa visit và upsert JSONB merge theo key; không có điều kiện revision."),
            ],
            tests=[],
            related=[{"id": "FE-005", "relationship": "FE-005 là ghi chú lượt có 409 nhưng client làm mất local draft; CLIN-039 là form tự lưu không có revision conflict response."}],
            result="Static sequence trace xác nhận last-writer-wins semantics, không chạy interleaving test.",
        ),
        finding(
            id="SEC-027",
            title="API tra bệnh nhân theo ID hoặc số điện thoại trả hồ sơ mà thiếu quyền xem danh sách",
            severity="MEDIUM", level="confirmed_static", category="privacy_authorization",
            summary="GET /patients/{id} và GET /patients?phone= chỉ dùng get_current_identity. Dependency này chặn DISPLAY/PARTNER nhưng không yêu cầu patient.list.view. Cùng router, /patients/danh-sach có guard patient.list.view; preset PHARMACIST không có capability đó. Hai đường đọc SELECT * trả PatientDTO gồm số điện thoại, email, địa chỉ, ngày sinh, người giám hộ và dữ liệu hành chính; national ID được che. Query giới hạn clinic_id đúng identity.",
            trigger="Một vai đã đăng nhập nhưng không có patient.list.view, như PHARMACIST preset, gọi endpoint theo UUID hoặc số điện thoại cùng clinic.",
            impact="Vai không được cấp quyền xem danh sách có thể đọc PII hồ sơ bệnh nhân trong cùng clinic; không có bằng chứng đọc chéo clinic hay dashboard hiện tại gọi các endpoint này.",
            recommendation="Đặt permission guard cho mọi route đọc PatientDTO theo ma trận được duyệt hoặc trả projection tối thiểu theo use case. Giữ clinic predicate và thêm audit/negative tests cho role không có quyền.",
            acceptance="Role thiếu patient.list.view bị từ chối ở cả ID và phone endpoint; role được duyệt chỉ nhận field cần thiết; kiểm tra hai clinic và masked national ID bằng identity giả tổng hợp.",
            note="Exact-main trace: endpoint theo ID/phone chỉ có get_current_identity; danh sách chính thức có patient.list.view; PHARMACIST preset không chứa capability đó; query trả PatientDTO đầy đủ trong cùng clinic.",
            refs=[
                ("src/clinicai/api/v1/patients.py", 253, 264, "GET by ID chỉ phụ thuộc get_current_identity."),
                ("src/clinicai/api/v1/patients.py", 273, 316, "Route danh sách dùng patient.list.view; route phone chỉ dùng get_current_identity."),
                ("src/clinicai/services/patient_service.py", 333, 345, "GET by ID SELECT * và chuyển toàn dòng thành PatientDTO."),
                ("src/clinicai/services/patient_service.py", 384, 402, "Phone lookup SELECT * và giới hạn clinic_id."),
                ("src/clinicai/schemas/patient.py", 328, 356, "PatientDTO có phone/email/address/DOB/guardian; national ID chỉ được mask."),
                ("src/clinicai/api/identity.py", 638, 659, "get_current_identity chặn DISPLAY/PARTNER nhưng không áp patient.list.view."),
                ("src/clinicai/permissions/catalogue.py", 791, 792, "PHARMACIST preset có quyền quầy thuốc, không có patient.list.view."),
            ],
            tests=["src/tests/api/test_patients_api.py:182-266 — kiểm đường đọc với Reception; không kiểm role thiếu capability bị từ chối."],
            related=[{"id": "SEC-018", "relationship": "Cùng lớp least-privilege PII nội clinic; SEC-018 là PostgREST contact tables, SEC-027 là FastAPI PatientDTO endpoints."}],
            result="Static route-to-service-to-schema trace; không gọi API hoặc query dữ liệu bệnh nhân.",
            limitations="No runtime API/JWT test; exact-main static evidence only. The API queries retain clinic_id scoping, national ID masking, and no dashboard callsite was found in the agent's source search.",
        ),
        finding(
            id="INF-023",
            title="Một kênh Telegram lỗi làm các kênh đã nhận tin bị gửi lặp khi relay thử lại",
            severity="MEDIUM", level="confirmed_static", category="notification_fanout_delivery",
            summary="send_telegram gửi tuần tự cùng message tới các TELEGRAM_CHAT_ID. Nếu một chat lỗi, kết quả tổng thể là lỗi dù chat trước đã nhận. notification_relay retry toàn event tối đa MAX_RETRIES và để event chưa published khi hết lượt, nên poll sau có thể gửi lại tới các chat đã thành công. Code comment chấp nhận tradeoff này; relay hiện bị tắt mặc định và phải bật tường minh.",
            trigger="Relay được bật với nhiều chat ID; ít nhất một kênh lỗi/timeout trong khi kênh khác đã nhận message.",
            impact="Nhân viên ở kênh khỏe có thể nhận trùng nhiều lần, làm loãng cảnh báo hoặc gây nhầm lẫn. Không khẳng định tin bị mất hoặc lỗi production; đây là hệ quả delivery at-least-once đã ghi rõ trong code.",
            recommendation="Theo dõi delivery riêng từng chat ID, chỉ retry đích thất bại, lưu message/provider ID khi có và hiển thị trạng thái đối soát; giữ relay opt-in đến khi có fixture multi-recipient failure.",
            acceptance="Fake Telegram: chat A thành công, B lỗi rồi thành công; A nhận đúng một tin, B được thử lại, event chỉ hoàn tất khi tất cả đích đạt chính sách; timeout vẫn đi vào trạng thái chưa rõ có thể đối soát.",
            note="Static trace xác nhận fanout trả một kết quả tổng, relay retry toàn message và event chưa publish được poll lại. Relay bị tắt mặc định; rủi ro chỉ áp dụng khi cấu hình bật.",
            refs=[
                ("src/clinicai/services/providers/telegram.py", 33, 79, "Fanout tới mọi channel; return cuối phản ánh lỗi, không có trạng thái per-chat."),
                ("src/clinicai/services/notification_relay.py", 216, 245, "Relay retry toàn event và chỉ publish khi toàn lần gửi trả success."),
                ("src/clinicai/worker.py", 94, 108, "Notification relay yêu cầu NOTIFICATION_RELAY_ENABLED=true; hiện tắt mặc định."),
            ],
            tests=["src/tests/unit/test_notification_relay.py::test_failed_sends_wait_between_attempts", "src/tests/unit/test_notification_relay.py::test_relay_does_not_publish_unaccepted_delivery — kiểm retry event, không kiểm partial success giữa nhiều chat."],
            result="Static exact-main trace. Không gửi Telegram thật; relay opt-in được ghi rõ.",
        ),
        finding(
            id="INF-024",
            title="Timeout Zalo không lưu trạng thái gửi chưa rõ để nhân viên đối soát",
            severity="MEDIUM", level="design_gap", category="external_delivery_unknown_state",
            summary="Provider trả HET_GIO và nói rõ chưa chắc đã gửi. GuiZaloService thoát trước khi ghi tương tác; route gửi không nhận Idempotency-Key và không lưu attempt UNKNOWN. Nếu Zalo đã nhận request nhưng response timeout, hệ thống không có trạng thái bền để kiểm tra; gửi lại có thể gửi trùng. Tracking ID hiện là clinic_patient_id, không phân biệt từng lần gửi.",
            trigger="POST gửi ZNS tới Zalo bị timeout sau khi request được gửi nhưng trước khi nhận phản hồi.",
            impact="Nhân viên phải kiểm tra thủ công; lần thử không nằm trong sổ CSKH. Nếu họ thử lại sau khi Zalo đã nhận, khách có thể nhận lặp. Route tồn tại nhưng chưa tìm thấy callsite dashboard hiện tại; chưa xác minh luồng này được dùng trên production.",
            recommendation="Ghi durable send attempt trước external call với ID riêng, trạng thái PENDING/UNKNOWN/ACCEPTED/FAILED, provider tracking ID và thời điểm; cho đối soát trước retry và áp idempotency key nếu vendor hỗ trợ.",
            acceptance="Fault test provider nhận request nhưng làm rơi response: DB giữ UNKNOWN và attempt ID; retry không tạo message thứ hai nếu vendor idempotent, hoặc bắt người dùng xác nhận sau bước đối soát; sổ CSKH chỉ ghi đã liên hệ khi có acceptance bằng chứng.",
            note="Design gap tĩnh: response timeout có nội dung ‘chưa chắc đã gửi’, nhưng service không ghi lại attempt và route không có request idempotency; chưa thấy dashboard caller.",
            refs=[
                ("src/clinicai/services/providers/zalo.py", 129, 154, "Gửi request tới Zalo; timeout trả HET_GIO với trạng thái chưa rõ."),
                ("src/clinicai/services/tuong_tac_cskh_service.py", 891, 919, "Thất bại/timeout return trước khi ghi sổ CSKH; tracking dùng clinic_patient_id."),
                ("src/clinicai/api/v1/routers/cskh.py", 1074, 1092, "POST Zalo nhận body không có idempotency key và gọi service."),
            ],
            tests=["src/tests/services/test_zalo_provider.py::test_het_gio_noi_ro_la_chua_chac_da_gui", "src/tests/unit/test_so_tuong_tac_cskh.py::test_zalo_that_bai_thi_khong_ghi_so — xác nhận không giả ghi đã gửi, không kiểm attempt reconciliation."],
            result="Đối chiếu provider, service và endpoint; không gọi Zalo/vendor hoặc HTTP thật.",
            limitations="The route has no current dashboard caller in source search; usage by external scripts or production operators is unknown. No vendor behavior, delivery receipt or production configuration was checked.",
        ),
        finding(
            id="INF-025",
            title="Dữ liệu bệnh nhân được ghép vào HTML Telegram mà không escape",
            severity="LOW", level="confirmed_static", category="telegram_message_markup",
            summary="Template đưa tên khách, patient_code, giờ, dịch vụ và tên bác sĩ trực tiếp vào chuỗi HTML; Telegram provider gửi với parse_mode=HTML. Giá trị có ký tự markup có thể làm thay đổi cách hiển thị hoặc khiến Telegram từ chối tin.",
            trigger="Một giá trị động được lưu có ký tự &, < hoặc > và template phát sự kiện tương ứng khi relay bật.",
            impact="Tin có thể hiển thị sai hoặc thất bại vì markup; đây không phải browser XSS và không mở quyền đọc dữ liệu. Relay đang opt-in/tắt mặc định.",
            recommendation="Escape mọi giá trị động theo HTML Telegram trước khi nội suy, hoặc bỏ parse_mode và gửi plain text; giữ bold markup tĩnh riêng.",
            acceptance="Unit tests dùng tên/dịch vụ chứa &, <b>, </b> và chuỗi giả tag; Telegram nhận văn bản nguyên nghĩa hoặc plain text, không lỗi parse; trường không được dùng vẫn không xuất hiện.",
            note="Exact-main template nội suy field động vào HTML và provider bật parse_mode=HTML; mức ảnh hưởng giới hạn định dạng/khả năng gửi.",
            refs=[
                ("src/clinicai/services/notification_templates.py", 37, 57, "Giá trị tên, mã khách, dịch vụ và bác sĩ được nội suy trực tiếp."),
                ("src/clinicai/services/providers/telegram.py", 52, 62, "Provider gửi text với parse_mode=HTML."),
            ],
            tests=["src/tests/unit/test_notification_templates.py::test_lich_moi_du_du_lieu — không dùng markup trong dữ liệu và không kiểm escaping."],
            result="Static string construction trace; không gửi message tới Telegram.",
        ),
        finding(
            id="FE-021",
            title="Bảng lịch vẫn mời nhân viên tự đăng ký dù backend đã đóng luồng",
            severity="LOW", level="confirmed_static", category="roster_ui_contract",
            summary="Backend ghi rõ luồng tự đăng ký đã đóng, ROSTER_ROLES chỉ còn nhóm người xếp lịch và route POST dùng _ROSTER_GUARD. Nhưng RosterRegisterTable vẫn hiển thị cho vai không phải approver chọn ca và bấm tự đăng ký; khi POST bị từ chối, UI hiện lỗi chung ‘Lỗi khi xếp ca’. Đây là mismatch UI/API theo chính sách backend hiện tại.",
            trigger="Nhân viên có roster.view nhưng không có roster.manage/config.clinic.manage mở bảng đăng ký rồi bấm đăng ký ca.",
            impact="Người dùng được mời làm thao tác không thể hoàn tất và có thể nghĩ lịch trực đang lỗi. Chính sách backend hiện tại chủ ý để quản lý xếp lịch; không kết luận tự đăng ký phải được mở lại.",
            recommendation="Nếu chính sách tiếp tục đóng self-service, ẩn/disable nút và nói rõ liên hệ người xếp lịch; nếu muốn mở lại thì cập nhật guard, workflow duyệt và hiển thị PENDING đồng bộ.",
            acceptance="Với non-approver, giao diện không đưa nút tự đăng ký khi backend đóng; với approver, thao tác xếp người vẫn hoạt động; test matrix đối chiếu quyền API và trạng thái UI.",
            note="Backend comment ghi rõ self-registration đã đóng và guard hạn chế POST; UI non-approver vẫn vẽ luồng tự đăng ký. Mức LOW vì chính sách xếp bởi quản lý có thể là chủ ý.",
            refs=[
                ("src/clinicai/services/config_service.py", 87, 97, "Backend ghi rõ luồng tự đăng ký ca đã đóng và ROSTER_ROLES chỉ còn roster admin."),
                ("src/clinicai/api/v1/routers/config.py", 48, 60, "POST roster dùng guard yêu cầu quyền xếp lịch; GET có guard riêng roster.view."),
                ("src/dashboard/app/(dashboard)/schedule/RosterRegisterTable.tsx", 489, 535, "Handler non-approver tự gửi POST và chỉ hiện lỗi chung khi server từ chối."),
                ("src/dashboard/app/(dashboard)/schedule/RosterRegisterTable.tsx", 1171, 1198, "Non-approver vẫn thấy nội dung và controls ‘tự đăng ký ca’."),
            ],
            result="Static UI/API contract comparison; không thực hiện POST hoặc kiểm production policy.",
            limitations="Backend comment is explicit that self-registration is intentionally closed. The finding is only the stale/misleading UI affordance; the audit does not recommend changing the policy without product confirmation.",
        ),
        finding(
            id="OPS-003",
            title="Áp dụng tuần coi mọi ca cùng ngày là ca phủ lịch hẹn",
            severity="MEDIUM", level="confirmed_static", category="roster_booking_coverage",
            summary="Trước khi áp dụng tuần, query tìm lịch hẹn có doctor_id nhưng chỉ coi lịch mất bác sĩ nếu không tồn tại bất kỳ work_roster row cùng bác sĩ/ngày/cơ sở. Query không lọc status APPROVED và không so giờ hẹn với ca. CapacityService lại chỉ tính ca APPROVED rồi xét theo shift/time. Vì vậy ca PENDING/REJECTED hoặc ca sáng có thể làm query bỏ qua lịch hẹn buổi tối không được phủ.",
            trigger="Áp dụng tuần có lịch hẹn đã gán bác sĩ nhưng ca cùng ngày chỉ ở trạng thái chờ/từ chối hoặc không bao phủ giờ hẹn.",
            impact="Không tạo cảnh báo ‘mất bác sĩ’ cho CSKH và lịch vẫn mang tên bác sĩ dù không có ca đã duyệt phù hợp giờ. Đây là khoảng trống cảnh báo; chưa chứng minh lịch hẹn thực tế bị bỏ lỡ.",
            recommendation="Dùng cùng hàm xác định ca đã duyệt và khung thời gian như CapacityService; cảnh báo từng appointment không có ca phủ, gồm ca pending/rejected/khác buổi; giao owner xử lý trước khi coi tuần là áp dụng an toàn.",
            acceptance="Fixture lịch 19:00 + ca sáng APPROVED, ca tối PENDING và ca tối REJECTED phải tạo cảnh báo; ca tối APPROVED đúng cơ sở phải không cảnh báo; kiểm tenant/location và không lộ tên khách ngoài role nhận việc.",
            note="Exact-main query kiểm bất kỳ dòng roster theo ngày/cơ sở; capacity query chỉ lấy APPROVED và ánh xạ ca theo bác sĩ. Chưa chạy DB/API test cho interleaving các trạng thái.",
            refs=[
                ("src/clinicai/services/config_service.py", 1125, 1158, "Apply-week query dùng NOT EXISTS theo ngày/cơ sở, không lọc status hoặc phủ giờ."),
                ("src/clinicai/services/capacity_service.py", 145, 181, "Capacity chỉ lấy ca APPROVED và giữ shift theo bác sĩ để xác định khung."),
            ],
            result="Static comparison giữa cảnh báo khi áp tuần và bộ lọc lịch được dùng cho sức chứa.",
            limitations="Không dùng DB production hoặc dữ liệu lịch thật; tác động phụ thuộc appointment/roster state cụ thể.",
        ),
        finding(
            id="SEC-028",
            title="Ca PENDING có thể cấp quyền làm thay bác sĩ trước khi được duyệt",
            severity="MEDIUM", level="confirmed_static", category="clinical_authorization_state",
            summary="_lich_hom_nay đưa vào phép tính mọi work_roster status khác REJECTED, nên PENDING cũng được dùng để xác định ca/phòng của bác sĩ và nhân viên hỗ trợ. duoc_lam_thay sau đó cấp phép TKYK/NURSE_ULTRASOUND làm thay khi cùng phòng/ca. Luồng sức chứa và gỡ ca chỉ dùng APPROVED, tạo hai cách hiểu khác nhau về trạng thái ca.",
            trigger="Có ca PENDING cho bác sĩ và người hỗ trợ cùng ngày/phòng/ca; người hỗ trợ gọi nghiệp vụ đi qua kiem_dung_ca trước khi ca được duyệt.",
            impact="Có thể cho phép thao tác lâm sàng nhân danh bác sĩ theo một phân công chưa được duyệt. Luồng self-registration hiện đóng, nên điều kiện phụ thuộc dữ liệu PENDING cũ hoặc đường ghi khác; chưa kiểm DB production và không kết luận có hàng pending thực tế.",
            recommendation="Chỉ ca APPROVED (và quy tắc legacy NULL đã duyệt rõ) mới cấp quyền lâm sàng; thêm test fail-closed cho PENDING/REJECTED và tái tính cache ngay khi duyệt/từ chối.",
            acceptance="Synthetic PENDING không cấp quyền thay bác sĩ; APPROVED cùng phòng/ca cấp đúng quyền; REJECTED/khác cơ sở/khác ca từ chối; kiểm các callsite clinical gate.",
            note="Exact-main helper loại REJECTED nhưng không yêu cầu APPROVED; capacity/remove paths yêu cầu APPROVED. Điều kiện phụ thuộc dữ liệu PENDING có tồn tại.",
            refs=[
                ("src/clinicai/permissions/ca_truc.py", 73, 99, "Query đưa status khác REJECTED vào danh sách ca để xác định substitute."),
                ("src/clinicai/permissions/ca_truc.py", 150, 194, "kiem_dung_ca gọi duoc_lam_thay từ danh sách lấy ở trên."),
                ("src/clinicai/services/capacity_service.py", 145, 165, "Đối chiếu: capacity lấy duy nhất ca APPROVED."),
            ],
            tests=["src/tests/test_vai_theo_vi_tri.py::test_chi_dong_da_duyet_moi_cap_vi_tri — kiểm trạng thái ở luồng role/position, không kiểm gate substitute lâm sàng."],
            result="Static trace nối trạng thái work_roster với clinical authorization helper; không dùng identity hay lượt khám thật.",
            limitations="The self-registration flow is intentionally closed in current source. Impact requires an existing PENDING row from legacy data or another write path; no production roster rows were read.",
        ),
        finding(
            id="INF-026",
            title="Gỡ ca giữ một kết nối rồi mượn kết nối thứ hai từ cùng pool",
            severity="MEDIUM", level="confirmed_static", category="database_pool_starvation",
            summary="RosterService.remove mở pool connection và transaction, sau đó gọi _xep_lich để kiểm quyền. _xep_lich lại acquire từ cùng pool trong khi connection đầu chưa được trả. Một request cần đồng thời hai connection; nếu nhiều request remove cùng chiếm mỗi request một connection rồi chờ connection thứ hai, pool bị cạn và các request cùng chờ.",
            trigger="Nhiều request gỡ/xem trước ca trực chạy đồng thời, đủ để các transaction giữ connection đầu trong lúc chờ acquire thứ hai; rủi ro rõ nhất khi POOL_MAX_SIZE được đặt thấp.",
            impact="Request gỡ ca có thể treo/timeout dù DB query bên trong chưa chạy lâu; cản việc đổi lịch và xử lý lịch hẹn. Pool API mặc định 20, cấu hình cho phép 2–60; chưa chạy saturation test để xác nhận ngưỡng hoặc timeout cụ thể.",
            recommendation="Tính quyền trước khi mở transaction hoặc truyền conn hiện có vào permission check; giữ transaction ngắn và theo dõi thời gian chờ pool. Thêm concurrency test với pool max=2 và nhiều remove.",
            acceptance="Với disposable pool size 2, hai request remove đồng thời hoàn tất hoặc trả lỗi nghiệp vụ xác định mà không kẹt; không có connection leak và permission vẫn đúng.",
            note="Static trace cho thấy nested acquire trên cùng pool trong lúc connection đầu đang ở transaction; ngưỡng gây nghẽn chưa được động tái hiện.",
            refs=[
                ("src/clinicai/services/config_service.py", 143, 151, "_xep_lich tự acquire connection từ pool để kiểm capability."),
                ("src/clinicai/services/config_service.py", 598, 612, "remove đang giữ conn/transaction rồi gọi _xep_lich."),
                ("src/clinicai/core/database.py", 14, 27, "Pool API mặc định max 20 và comment nêu ngân sách kết nối."),
                ("src/clinicai/core/database.py", 43, 61, "Cấu hình POOL_MAX_SIZE cho phép giá trị thấp nhất 2."),
            ],
            tests=[],
            result="Static pool topology trace; không chạy load/concurrency test.",
            limitations="No deadlock, timeout, pool statistics or production config was observed. The finding identifies a possible exhaustion cycle, not an observed outage.",
        ),
        finding(
            id="OPS-004",
            title="API có thể từ chối ca đã duyệt mà không chạy luồng gỡ lịch an toàn",
            severity="MEDIUM", level="confirmed_static", category="roster_state_transition",
            summary="PATCH quyết định ca ánh xạ approve/reject và UPDATE work_roster theo id+clinic, không yêu cầu trạng thái hiện tại PENDING. Vì vậy stale request hoặc request trực tiếp có thể đổi ca APPROVED thành REJECTED. Khác remove(), decide không kiểm lịch hẹn đã gán bác sĩ, không gỡ assignment ngoài khung và không giao việc chờ xếp.",
            trigger="Quản lý gửi reject cho một id đã APPROVED, ví dụ tab hàng chờ cũ hoặc thao tác gọi API ngoài UI hiện hành.",
            impact="Ca bị coi là từ chối trong quyền theo ca nhưng appointment vẫn giữ doctor_id; không có chuyển giao lịch tương đương thao tác gỡ ca. Rủi ro phụ thuộc lời gọi hợp lệ của manager; chưa tái hiện và chưa kiểm caller UI hiện tại.",
            recommendation="Chỉ cho approve/reject khi row đang PENDING bằng UPDATE có điều kiện status='PENDING' và kiểm rowcount; thay đổi ca đã duyệt phải dùng luồng remove/reassign có dry-run, chuyển appointment không phủ vào worklist và audit.",
            acceptance="Hai manager thao tác cùng một pending row: chỉ một quyết định thắng; reject row APPROVED trả conflict; gỡ ca APPROVED chuyển đúng appointment không phủ sang hàng chờ có owner và không tự hủy lịch.",
            note="Exact-main route cho manager gọi decide; UPDATE không kiểm status. Service remove có bước reconciliation lịch ngoài ca, còn decide chỉ đổi status.",
            refs=[
                ("src/clinicai/api/v1/routers/config.py", 294, 308, "PATCH decision nhận approve/reject và chuyển trực tiếp tới service."),
                ("src/clinicai/services/config_service.py", 524, 558, "UPDATE chỉ lọc id+clinic, không lọc trạng thái hiện tại."),
                ("src/clinicai/services/config_service.py", 614, 626, "Luồng remove ghi audit và sau đó có bước xử lý lịch bác sĩ bị gỡ."),
            ],
            tests=[],
            related=[{"id": "OPS-003", "relationship": "OPS-003 nói query áp tuần bỏ qua trạng thái/giờ ca; OPS-004 là mutation có thể đổi ca APPROVED sang REJECTED mà không reconciliation."}],
            result="Static route/state-transition trace; không gọi API hoặc thay đổi roster data.",
            limitations="No current dashboard caller for rejecting an approved row was established; trigger includes direct API or stale concurrent request. No production roster state was inspected.",
        ),
    ]
    return items


def round_ranges(findings: list[dict]) -> dict[str, list[tuple[int, int, str]]]:
    ranges: dict[str, list[tuple[int, int, str]]] = {}
    for item in findings:
        for ev in item["evidence"]:
            ranges.setdefault(ev["path"], []).append(
                (ev["line"], ev["end_line"], ev["detail"])
            )
    # Existing security findings receive supporting evidence from this round.
    extras = [
        ("src/dashboard/app/api/ho-so-kham/route.ts", 49, 62, "BFF xác thực người gọi rồi chuyển visit UUID và nội dung ghi chú tới API backend."),
        ("src/clinicai/api/v1/routers/ho_so_kham.py", 171, 185, "Router gọi ghi_chu_luot.luu bằng identity hiện tại."),
        ("src/clinicai/services/ghi_chu_luot.py", 122, 159, "Lưu ghi chú kiểm capability, clinic và status nhưng không kiểm phân công bác sĩ."),
        ("src/clinicai/services/thu_ky_bac_si.py", 53, 74, "Helper nêu mọi chặn TKYK phải kiểm assignment qua một luật chung."),
        ("supabase/migrations/20260815000002_nhieu_so_dien_thoai.sql", 47, 64, "patient_sdt_them cấp SELECT authenticated với RLS theo clinic_ids, không lọc role."),
        ("supabase/migrations/20260730000003_multi_tenant_foundation.sql", 235, 246, "current_clinic_ids trả mọi clinic có membership active, không lọc role."),
    ]
    for path, start, end, detail in extras:
        ranges.setdefault(path, []).append((start, end, detail))
    return ranges


def main() -> None:
    actual_sha = subprocess.check_output(["git", "-C", str(SNAPSHOT), "rev-parse", "HEAD"], text=True).strip()
    if actual_sha != PINNED_SHA:
        raise SystemExit(f"Pinned source mismatch: expected {PINNED_SHA}, got {actual_sha}")

    manifest = read_json("MAIN-PHAM-VI.json")
    if manifest["sha"] != PINNED_SHA:
        raise SystemExit("MAIN-PHAM-VI.json does not reference the pinned source SHA")
    by_path = {row["path"]: row for row in manifest["files"]}
    definitions = finding_definitions()
    ranges = round_ranges(definitions)
    existing = read_json("PHAT-HIEN.json")
    ids = {row["id"] for row in existing}
    collisions = sorted(ids.intersection(row["id"] for row in definitions))
    if collisions:
        raise SystemExit(f"Round 19 finding IDs already exist: {collisions}; refusing to append")

    # Exact-main extensions: same root control gap, new independent caller/table.
    by_id = {row["id"]: row for row in existing}
    sec16 = by_id["SEC-016"]
    sec16["title"] = "TKYK có thể ghi ghi chú khám hoặc thai kỳ ngoài phạm vi bệnh nhân được phân"
    sec16["summary"] += " Thêm PUT ghi_chu_luot: route chỉ kiểm quyền đổi trong hồ sơ và visit status, không gọi assignment helper, nên TKYK có thể lưu ghi chú tự do cho lượt cùng clinic của bác sĩ khác."
    sec16["impact"] += " Bổ sung: ghi chú tự do của lượt khám ngoài phân công cũng có thể được tạo thành phiên bản mới. Không có bằng chứng cross-clinic hoặc occurrence production."
    sec16["recommendation"] = "Áp assignment policy tại mọi boundary ghi lâm sàng. PATCH thai kỳ phải lấy clinic_patient_id từ row đã khóa; ghi chú phải lấy attending doctor của visit rồi gọi kiem_thu_ky_duoc_lam trước INSERT. Giữ audit actor/visit và không ghi nội dung bệnh án vào log."
    sec16["acceptance"] = "Với TKYK được phân Dr A, ghi pregnancy/note ở Dr A hoạt động; same-clinic visit Dr B bị từ chối ở cả hai API; role bác sĩ đúng phạm vi tiếp tục hoạt động; kiểm tenant isolation và audit actor/visit."
    sec16["main_validation"]["note"] += " Round 19 bổ sung static trace ghi chú lượt: identity TKYK có thể qua capability nhưng service không kiểm assignment bác sĩ của visit."
    sec16["validation"]["result"] += " Round 19 đối chiếu thêm BFF → route → ghi_chu_luot; service note thiếu helper assignment dù helper chung yêu cầu mọi chặn TKYK phải đi qua."
    sec16["related_tests"] = list(dict.fromkeys(sec16.get("related_tests", []) + [
        "src/tests/services/test_ghi_chu_luot_db.py — kiểm version/status/roles, không có deny test cho TKYK ngoài assignment.",
        "src/tests/test_phieu_chuyen_khoa_pham_vi_thu_ky.py — kiểm assignment ở luồng form, không kiểm note route.",
    ]))
    sec16_refs = [
        ("src/dashboard/app/api/ho-so-kham/route.ts", 49, 62, "BFF chuyển lệnh ghi chú có visit UUID sau auth."),
        ("src/clinicai/api/v1/routers/ho_so_kham.py", 171, 185, "PUT route gọi service mà không kiểm phạm vi assignment."),
        ("src/clinicai/services/ghi_chu_luot.py", 122, 159, "Service kiểm permission, clinic và status; không đọc attending doctor hoặc gọi assignment helper."),
        ("src/clinicai/services/thu_ky_bac_si.py", 53, 74, "Policy helper nói các chặn TKYK phải cùng đi qua assignment helper."),
    ]
    sec16_evidence = [evidence(ref) for ref in sec16_refs]
    sec16["evidence"].extend({k: e[k] for k in ("path", "line", "end_line", "detail")} for e in sec16_evidence)
    sec16["main_validation"]["evidence"].extend(sec16_evidence)
    sec16["source_hashes"].update({p: source(p)[1] for p in sorted({r[0] for r in sec16_refs})})

    sec18 = by_id["SEC-018"]
    sec18["summary"] += " Round 19 adds patient_sdt_them: authenticated SELECT with clinic-only RLS exposes secondary phone values/type through PostgREST to any active role in that clinic."
    sec18["impact"] += " This also includes additional patient phone numbers and their type within the same clinic; cross-clinic access is still not evidenced."
    sec18["main_validation"]["note"] += " Round 19 extends the same clinic-only read policy to patient_sdt_them; static migration evidence, no PostgREST runtime request."
    sec18_refs = [
        ("supabase/migrations/20260815000002_nhieu_so_dien_thoai.sql", 47, 64, "RLS/grant cho patient_sdt_them chỉ giới hạn clinic_ids, không vai."),
        ("supabase/migrations/20260730000003_multi_tenant_foundation.sql", 235, 246, "current_clinic_ids lọc membership active nhưng không lọc role."),
    ]
    sec18_evidence = [evidence(ref) for ref in sec18_refs]
    sec18["evidence"].extend({k: e[k] for k in ("path", "line", "end_line", "detail")} for e in sec18_evidence)
    sec18["main_validation"]["evidence"].extend(sec18_evidence)
    sec18["source_hashes"].update({p: source(p)[1] for p in sorted({r[0] for r in sec18_refs})})
    sec18["validation"]["result"] += " Round 19 traced the additional patient_sdt_them table grant and RLS helper; still static, no JWT/PostgREST runtime query."

    status_rank = {"inventoried": 0, "scanned": 1, "traced": 2, "read": 3, "excluded": 4}
    full_reads = {
        "src/clinicai/voice/transcribe.py",
        "src/clinicai/api/v1/routers/voice.py",
        "src/tests/voice/test_voice_router.py",
        "src/tests/voice/test_transcribe.py",
        "src/clinicai/api/nghi_huu.py",
    }
    coverage_files = []
    all_ranges = {path: list(spans) for path, spans in ranges.items()}
    for path in full_reads:
        lines, _ = source(path)
        all_ranges.setdefault(path, []).append((1, len(lines), "Full-file read; no distinct new finding in this slice."))
    for path, spans in sorted(all_ranges.items()):
        if path not in by_path:
            raise SystemExit(f"Reviewed source is missing from main path ledger: {path}")
        lines, digest = source(path)
        row = by_path[path]
        if row["sha256"] != digest or row["lines"] != len(lines):
            raise SystemExit(f"Main path ledger fingerprint mismatch: {path}")
        old_status = row["status"]
        if path in full_reads:
            status = "read"
        else:
            status = "traced" if status_rank[old_status] < status_rank["traced"] else old_status
        row["status"] = status
        read_mode = "full_file_read" if path in full_reads else "targeted_semantic_trace"
        detail_ranges = "; ".join(f"{start}-{end}" for start, end, _ in spans)
        row["method"] = f"{row.get('method', '')} | Round 19 {read_mode}: {detail_ranges}".strip(" |")
        coverage_files.append({
            "path": path,
            "status": status,
            "prior_status": old_status,
            "read_level_this_round": read_mode,
            "full_file_read_this_round": path in full_reads,
            "ranges": [{"start": start, "end": end, "purpose": purpose} for start, end, purpose in spans],
            "sha256": digest,
            "line_count": len(lines),
        })

    write_json("MAIN-PHAM-VI.json", manifest)
    write_json("PHAT-HIEN.json", existing + definitions)
    write_json("blocks/round19_findings.json", definitions)
    write_json("blocks/round19_coverage.json", {
        "schema_version": 1,
        "audit": "round19_notifications_clinical_privacy_roster",
        "snapshot": {"path": str(SNAPSHOT), "sha": PINNED_SHA},
        "review_mode": "static_read_only_cross_layer_trace",
        "scope": [
            "notification bell failure state, visible list cap, Telegram fanout/markup, Zalo timeout record",
            "clinical print release state, form/service binding, concurrent form autosave",
            "patient API least privilege and PostgREST secondary phone access",
            "roster approval, appointment coverage, substitute authorization, pool usage and UI/API contract",
            "voice transcription boundary and retired endpoint source reads",
        ],
        "tests_run": False,
        "runtime_db_vps_secrets_phi_touched": False,
        "coverage_note": "Candidate paths have targeted source ranges and exact SHA excerpts. Five explicitly read files are marked full-file; all other round-19 paths are partial traces. No app/DB/API/production tests were run in this round. Existing tests named in findings were not executed.",
        "files": coverage_files,
    })

    checks = read_json("KIEM-CHUNG.json")
    known = {(row["id"], row["path"]) for row in checks["checks"]}
    for item in definitions + [sec16, sec18]:
        for ev in item["main_validation"]["evidence"]:
            key = (item["id"], ev["path"])
            if key not in known:
                checks["checks"].append({"id": item["id"], "path": ev["path"], "valid": True})
                known.add(key)
    write_json("KIEM-CHUNG.json", checks)

    state = read_json("STATE.json")
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    all_counts = Counter(row["status"] for row in manifest["files"])
    code_files = [row for row in manifest["files"] if Path(row["path"]).suffix.lower() in CODE_SUFFIXES]
    code_counts = Counter(row["status"] for row in code_files)
    all_findings = existing + definitions
    severity = Counter(row["severity"] for row in all_findings)
    evidence_levels = Counter(row["evidence_level"] for row in all_findings)
    main_status = Counter(row["main_validation"]["status"] for row in all_findings)
    summary = state["summary"]
    state["updated_at"] = now
    state["phase"] = "round19_notifications_clinical_privacy_roster_checkpoint"
    state["next_action"] = (
        "Continue semantic reads across remaining scanned/inventoried paths. Prioritize isolated tests for patient API permission matrix, "
        "clinical form/service binding and concurrent edits, notification partial delivery/Zalo unknown state, and roster approval-state transitions/pool saturation. "
        "Keep product policy questions separate from confirmed code behavior. Use exact-main SHA and do not claim source audit complete."
    )
    state["report_status"] = "v0.40_154_findings_HTML_and_portable_ZIP_pending_final_QA; full source audit incomplete"
    summary["findings"] = len(all_findings)
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
    summary["reviewed_slice_v040"] = (
        "round19: 14 new findings (12 MEDIUM, 2 LOW) across clinical forms/print/concurrency, notification UI/providers, patient API privacy and roster state/pool. "
        "SEC-016 expanded to assignment-guarded notes; SEC-018 extended to patient_sdt_them. Static exact-main traces; 5 full-file reads, no application tests."
    )
    summary["new_findings_v040"] = [item["id"] for item in definitions]
    state.setdefault("blocks", {})["round19_notifications_clinical_privacy_roster"] = {
        "status": "round19 static slices integrated; 14 new findings and 2 existing security findings extended",
        "scope": "Notification read/delivery, clinical form print/binding/concurrency, patient API privacy, roster status/coverage/authorization/pool, voice boundary read",
        "artifacts": "blocks/round19-summary.md; blocks/round19_findings.json; blocks/round19_coverage.json; integrate_round19.py",
        "findings": "12 MEDIUM and 2 LOW; all still_present_on_main. SEC-016 and SEC-018 retain existing IDs with additional evidence.",
        "next": "Run bounded synthetic permission, concurrency, notification retry and roster interleaving tests; continue semantic source reads. Full source audit incomplete.",
    }
    state["artifacts"]["qa"] = "HTML-QA.json; v0.40 report rebuild and desktop/mobile browser QA pending. Report-only, not ClinicAI application validation."
    state["artifacts"]["integration_script"] = "integrate_round19.py; round19 evidence/coverage in blocks/round19_*; earlier checkpoints retained."
    state["artifacts"]["bundle_integrity"] = "Pending v0.40 package regeneration and verification after HTML QA."
    state["artifacts"]["html_sha256"] = "pending v0.40 QA"
    state["artifacts"]["html_checked_at"] = "pending v0.40 QA"
    state["artifacts"]["bundle_entries"] = "pending v0.40 package verification"
    state["runtime_summary"]["round19"] = "Static exact-main traces only; no ClinicAI app/DB/API tests, provider calls, production checks, secrets or PHI. Report QA pending."
    write_json("STATE.json", state)

    print(json.dumps({
        "new_findings": [item["id"] for item in definitions],
        "findings_total": len(all_findings),
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
