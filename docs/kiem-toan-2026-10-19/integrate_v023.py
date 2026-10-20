"""Integrate verified exact-main candidates into audit checkpoint v0.23."""
from __future__ import annotations
import hashlib, json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SNAPSHOT = Path("/tmp/clinicai-audit-main-956ba4f2")
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"

def rj(name): return json.loads((ROOT / name).read_text())
def wj(name, obj): (ROOT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
def ev(path, start, end, detail): return {"path": path, "line": start, "end_line": end, "detail": detail}

F = [
dict(id="INF-013", title="Health và Ops không nhìn thấy ảnh chuyển khoản đang kẹt trên VPS", severity="MEDIUM", evidence_level="confirmed_static", category="media_backup_observability",
summary="Worker đẩy riêng tep_ket_qua và anh_chuyen_khoan, nhưng so_lieu chỉ đếm tep_ket_qua. /health/day-tep và /ops/canh-bao dùng so_lieu nên backlog/lỗi riêng của ảnh chuyển khoản không làm health degraded và không hiện ở Ops.",
trigger="CFS gián đoạn hoặc lỗi lặp chỉ ở lô anh_chuyen_khoan, trong khi tep_ket_qua rỗng hoặc dưới ngưỡng cảnh báo.",
impact="Ảnh chứng từ thanh toán còn duy nhất trên VPS có thể bị kẹt mà bộ theo dõi vẫn báo ok; vận hành thiếu tuổi/lỗi backlog để xử lý.",
evidence=[ev("src/clinicai/services/day_tep.py",516,522,"Worker xử lý lô anh_chuyen_khoan riêng."),ev("src/clinicai/services/day_tep.py",551,585,"so_lieu chỉ truy vấn FROM tep_ket_qua."),ev("src/clinicai/api/v1/health.py",123,137,"Health gọi so_lieu và trả 503 theo số liệu đó."),ev("src/clinicai/api/v1/routers/ops.py",170,186,"Ops trả day_tep.so_lieu."),ev("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql",223,246,"Ảnh chuyển khoản có vị trí VPS và trạng thái retry riêng.")],
validation=dict(method="static_worker_metric_health_ops_schema_trace",command=None,result="Đối chiếu worker hai bảng với query metric và consumer health/Ops.",limitations="Chưa dựng backlog tổng hợp trên DB, gọi HTTP health/Ops hoặc CFS; không có bằng chứng backlog production."),
recommendation="Tổng hợp metric cho mọi bảng thuộc BANG_TEP hoặc trả theo từng loại; đưa oldest pending, retry failures và bytes vào health/Ops, chỉ hiện số liệu không định danh.",
acceptance="Synthetic DB chỉ có ảnh chuyển khoản pending quá ngưỡng/lỗi nặng: health degraded, Ops nhận diện đúng loại và tuổi backlog; tep_ket_qua rỗng không che ảnh lỗi.",
alignment=["Reality ngày càng dễ nhìn thấy hơn","Khoảng thời gian Unknown ngày càng ngắn hơn","Vấn đề được phát hiện sớm hơn"], related_tests=["src/tests/services/test_day_tep_db.py"]),
dict(id="INF-014", title="CI trên máy có thể đăng trạng thái xanh cho commit dù đã kiểm mã untracked", severity="MEDIUM", evidence_level="confirmed_static", category="ci_provenance",
summary="ci-may.sh phát hiện working tree bằng git status --porcelain --untracked-files=no. Job chạy trên cây hiện tại; --bao-github gắn status vào HEAD. File nguồn/test untracked có thể ảnh hưởng kết quả mà không đặt BAN_BAN, khiến CI báo cây khác với commit. Tracked changes vẫn được phát hiện.",
trigger="File nguồn/test mới chưa git add làm thay đổi job, tracked tree sạch, chạy CI với --bao-github.",
impact="Người review có thể dựa vào status xanh trên SHA chưa chứa nội dung đã kiểm; không suy ra đã từng đăng status sai.",
evidence=[ev("scripts/ci-may.sh",74,80,"BAN_BAN bỏ qua untracked files."),ev("scripts/ci-may.sh",82,90,"Job chạy trên working tree hiện tại."),ev("scripts/ci-may.sh",241,250,"GitHub status đăng lên SHA BAN=HEAD khi BAN_BAN bằng 0."),ev("scripts/deploy-backend.sh",49,57,"Deploy dùng cách kiểm untracked khác, cho thấy tiêu chí không nhất quán.")],
validation=dict(method="static_worktree_dirty_detection_and_status_publish_trace",command=None,result="Truy vết cờ BAN_BAN, cách job chạy và SHA nhận status.",limitations="Chưa chạy CI trong repo giả có untracked code; không đăng GitHub status."),
recommendation="Coi non-ignored untracked là dirty trước khi chạy; chỉ publish status từ checkout sạch đúng SHA.",
acceptance="Repo tạm có HEAD sạch và untracked source/test ảnh hưởng job: --bao-github không đăng xanh cho HEAD; tracked-dirty, ignored và clean cases có test riêng.",
alignment=["Quyết định dựa trên bằng chứng tốt hơn","Lỗi lặp lại dần biến thành cải tiến hệ thống"], related_tests=["scripts/tests/test-ci-may.sh"]),
dict(id="INF-015", title="Deploy kiểm Caddyfile mới trong file tạm nhưng restart với bind-mount cũ", severity="HIGH", evidence_level="confirmed_static", category="release_configuration",
summary="Compose bind-mount một file Caddyfile riêng. Khi source đổi, deploy copy bản mới vào /tmp/Caddyfile.moi và validate file tạm, nhưng chỉ restart cùng container. Restart giữ inode bind-mount tại /etc/caddy/Caddyfile, nên Caddy vẫn đọc cấu hình cũ; không kiểm lại sau restart.",
trigger="Deploy thay Caddyfile hoặc CADDY_FILE và nhánh so sánh phát hiện khác nội dung.",
impact="Routing, TLS, allowlist hoặc lớp bảo vệ mới có thể chưa hiệu lực dù deploy tiếp tục; cấu hình đang chạy khác source đã kiểm.",
evidence=[ev("docker-compose.yml",63,70,"Caddyfile bind-mount như một file; ghi chú inode cũ."),ev("scripts/deploy-backend.sh",321,340,"Copy/validate /tmp/Caddyfile.moi rồi chỉ restart caddy."),ev("scripts/deploy-backend.sh",332,339,"So sánh trước restart nhưng không xác minh nội dung sau restart.")],
validation=dict(method="static_compose_bind_mount_and_deploy_reload_trace",command=None,result="Đối chiếu bind mount với docker cp, validate và lệnh restart.",limitations="Không chạy Docker/deploy; cần kiểm chứng trong staging disposable."),
recommendation="Sau validate, recreate container với mount mới hoặc mount cả thư mục; đọc lại checksum trong container và smoke-test route/TLS/auth.",
acceptance="Staging đổi directive an toàn: container mới đọc đúng checksum, endpoint smoke test đúng; cấu hình lỗi giữ bản đang chạy.",
alignment=["Reality ngày càng dễ nhìn thấy hơn","Khoảng thời gian Unknown ngày càng ngắn hơn","Vấn đề được phát hiện sớm hơn"], related_tests=["scripts/tests/test-deploy-backend.sh"]),
dict(id="SEC-016", title="TKYK có quyền ghi hồ sơ thai kỳ ngoài phạm vi bệnh nhân được phân", severity="HIGH", evidence_level="confirmed_static", category="patient_assignment_write_authorization",
summary="POST/PATCH thai kỳ yêu cầu clinical.record.write; service kiểm clinic và trạng thái nhưng không gọi kiem_khach. Đường đọc cùng service có gate này, và helper giới hạn TKYK theo bác sĩ được phân. Preset TKYK gồm quyền ghi hồ sơ, nên ID cùng clinic có thể mở đường ghi ngoài phân công.",
trigger="TKYK có quyền ghi, được phân cho bác sĩ A nhưng gửi patient_id hoặc pregnancy_id cùng clinic thuộc bệnh nhân bác sĩ B.",
impact="Có thể sửa ngày kinh cuối, ngày dự sinh, nguy cơ cao/lý do hoặc kết cục ngoài phạm vi; sai lệch tính toàn vẹn dữ liệu lâm sàng, không phải cross-clinic theo trace này.",
evidence=[ev("src/clinicai/api/v1/routers/thai_ky.py",59,85,"POST/PATCH dùng _GHI_GUARD rồi gọi create/update."),ev("src/clinicai/services/thai_ky_service.py",370,390,"Đường đọc gọi kiem_khach."),ev("src/clinicai/services/thai_ky_service.py",392,430,"Tạo kiểm quyền/clinic/visit nhưng thiếu assignment gate."),ev("src/clinicai/services/thai_ky_service.py",469,488,"Sửa khóa theo clinic và pregnancy ID nhưng thiếu gate bệnh nhân."),ev("src/clinicai/services/thu_ky_bac_si.py",120,147,"Helper định nghĩa phạm vi bệnh nhân của TKYK."),ev("src/clinicai/permissions/catalogue.py",723,735,"Preset TKYK có khối ghi bệnh án.")],
validation=dict(method="static_router_service_assignment_policy_and_role_preset_trace",command=None,result="Đối chiếu guard, SQL create/update, read-side gate, policy helper và preset TKYK.",limitations="Chưa HTTP/DB với TKYK tổng hợp A/B; cần xác nhận ma trận vai runtime."),
recommendation="Áp assignment policy tại mọi read/write patient boundary; PATCH lấy clinic_patient_id từ row đã khóa rồi gọi kiem_khach trước UPDATE.",
acceptance="TKYK A đọc/ghi bệnh nhân A nhưng bị từ chối trước INSERT/UPDATE với B; quyền bác sĩ và cross-clinic negative control giữ đúng.",
alignment=["Ownership ngày càng rõ hơn","Quyết định dựa trên bằng chứng tốt hơn","Lỗi lặp lại dần biến thành cải tiến hệ thống"], related_tests=["src/tests/services/test_thai_ky_db.py"]),
dict(id="SEC-017", title="Hai view quyền cấp authenticated có nguy cơ bỏ qua RLS và lộ metadata liên clinic", severity="MEDIUM", evidence_level="confirmed_static", category="tenant_boundary_view_security",
summary="Migration tạo v_quyen_hieu_luc và v_quyen_thuc_te rồi GRANT SELECT authenticated. View đầu đọc capability_grant không tenant predicate/security_invoker dù bảng có policy clinic. View sau đọc view đầu và roster không lọc clinic. Nếu owner bypass RLS, PostgREST có thể trả capability/nhân viên/phạm vi clinic khác. Không thấy PHI hay write path.",
trigger="JWT authenticated gọi trực tiếp PostgREST view khi owner view có quyền bypass RLS.",
impact="Rò metadata phân quyền và lịch/phạm vi nhân viên xuyên tenant. Cần xác nhận view owner/ACL runtime trước khi khẳng định có thể khai thác.",
evidence=[ev("supabase/migrations/20260923000003_capability.sql",104,110,"capability_grant có policy SELECT theo current_clinic_ids()."),ev("supabase/migrations/20260923000003_capability.sql",172,188,"v_quyen_hieu_luc không tenant predicate/security_invoker nhưng cấp SELECT authenticated."),ev("supabase/migrations/20260929000001_doi_nguoi_trong_ca.sql",168,224,"v_quyen_thuc_te đọc view và roster không lọc clinic."),ev("supabase/migrations/20260929000001_doi_nguoi_trong_ca.sql",226,229,"Comment và GRANT SELECT authenticated."),ev("supabase/migrations/20260730000015_patient_summary_security_invoker.sql",1,16,"Migration giải thích security_invoker để RLS theo người gọi.")],
validation=dict(method="static_view_owner_rls_grant_and_tenant_filter_inventory",command=None,result="Quét 373 migrations; đọc view grants/definitions, policy nguồn và một migration security_invoker.",limitations="Chưa kiểm owner/ACL DB triển khai hoặc gọi PostgREST authenticated; rủi ro phụ thuộc owner và RLS thực tế; không có bằng chứng lộ PHI."),
recommendation="Xác nhận owner/ACL trước; chuyển view backend-only hoặc lọc tenant rõ. Nếu security_invoker, thiết kế base-table grants để tránh mở rộng quyền.",
acceptance="Disposable DB hai clinic: JWT clinic A đọc REST hai view không nhận dòng clinic B; backend/service_role vẫn đúng; test ACL sau migration.",
alignment=["Ownership ngày càng rõ hơn","Quyết định dựa trên bằng chứng tốt hơn"], related_tests=[]),
dict(id="FIN-009", title="API giữ lại tiền thừa vẫn có thể ghi lại quyết định sau check-out", severity="MEDIUM", evidence_level="confirmed_static", category="financial_lifecycle_immutability",
summary="giu_lai khóa lượt và tính số dư nhưng không kiểm closed_at; khi số dư tăng, service hủy khoản giữ hiện tại rồi tạo bản ghi mới. huy_giu_lai lại chặn khi đã check-out. Endpoint giữ lại vẫn gọi service qua authorize_payment.",
trigger="Lượt đã đóng, còn số dư dương hoặc số dư tăng, client/retry gọi POST giữ lại tiền thừa.",
impact="Quyết định/lý do giữ hiện hành có thể đổi sau khi lượt đóng; chưa thấy correction/refund flow riêng giải thích điều chỉnh.",
evidence=[ev("src/clinicai/services/tien_thua_service.py",343,373,"giu_lai không kiểm closed_at, thay bản ghi giữ hiện hành."),ev("src/clinicai/services/tien_thua_service.py",375,384,"huy_giu_lai cấm sau checkout."),ev("src/clinicai/api/v1/routers/dispatch.py",513,528,"Endpoint vẫn expose service qua authorize_payment.")],
validation=dict(method="static_checkout_state_and_financial_write_path_trace",command=None,result="Đối chiếu row lock, closed_at gate, lịch sử giữ và API.",limitations="Chưa dựng DB lượt closed có số dư mới/gọi HTTP; cần xác nhận balance-increase path."),
recommendation="Từ chối giu_lai khi closed_at khác NULL. Điều chỉnh hậu checkout qua refund/correction có actor, reason, idempotency và audit ledger.",
acceptance="DB fixture closed có số dư dương: POST trả conflict và không đổi dòng/báo cáo; correction/refund ghi old/new, actor, reason.",
alignment=["Reality ngày càng dễ nhìn thấy hơn","Ownership ngày càng rõ hơn","Lỗi lặp lại dần biến thành cải tiến hệ thống"], related_tests=["src/tests/services/test_tien_thua_phan_e_db.py"]),
dict(id="CLIN-028", title="Sửa lịch riêng bác sĩ không bật nút lưu", severity="MEDIUM", evidence_level="confirmed_static", category="appointment_edit_contract",
summary="Trong edit mode, changed so ngày/giờ/dịch vụ/kênh/người giới thiệu/ghi chú nhưng bỏ doctorId. Submit phụ thuộc changed nên đổi riêng bác sĩ không thể gửi, trong khi PATCH payload có doctor_id.",
trigger="Nhân viên sửa lịch và chỉ đổi/bỏ phân bác sĩ.",
impact="Thao tác đổi bác sĩ không thể hoàn tất; lịch giữ bác sĩ cũ và UI không giải thích vì sao nút chưa bật.",
evidence=[ev("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx",234,241,"changed không so doctorId."),ev("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx",290,310,"PATCH reschedule gửi doctor_id."),ev("src/dashboard/app/(dashboard)/customers/AppointmentEditModal.tsx",90,105,"Modal kết thúc luồng sau response thành công.")],
validation=dict(method="static_edit_form_dirty_state_and_patch_payload_trace",command=None,result="Đối chiếu dirty flag và payload PATCH.",limitations="Chưa browser automation/React test; trace tĩnh."),
recommendation="Đưa doctorId vào changed, định nghĩa rõ null/rỗng khi bỏ phân và xác minh reload trước khi đóng modal.",
acceptance="Đổi riêng bác sĩ bật nút, gửi đúng ID; bỏ phân gửi null; reload hiển thị đúng bác sĩ.",
alignment=["Reality ngày càng dễ nhìn thấy hơn","Con người bị gián đoạn ít hơn nhưng đúng lúc hơn"], related_tests=["src/dashboard/tests"]),
dict(id="CLIN-029", title="Dropdown cơ sở trong form sửa lịch trông như lưu được nhưng PATCH bỏ qua", severity="MEDIUM", evidence_level="confirmed_static", category="appointment_edit_contract",
summary="Form sửa vẫn render location dropdown. locationId không thuộc changed; nếu đổi trường khác để nút bật, PATCH và proxy whitelist không có location_id. Modal đóng khi response ok, nên lựa chọn có thể bị hiểu nhầm là đã lưu.",
trigger="Người dùng đổi cơ sở và một trường khác được PATCH hỗ trợ.",
impact="Nhân viên tin lịch đã chuyển cơ sở trong khi backend giữ cơ sở cũ; điều phối có thể dựa trên địa điểm sai.",
evidence=[ev("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx",234,241,"changed bỏ locationId."),ev("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx",527,539,"Dropdown cơ sở tương tác được."),ev("src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx",293,310,"Payload không gửi location_id."),ev("src/dashboard/app/api/appointments/route.ts",223,238,"PatchBody không khai location_id."),ev("src/dashboard/app/api/appointments/route.ts",295,309,"Proxy không forward location_id."),ev("src/dashboard/app/(dashboard)/customers/AppointmentEditModal.tsx",90,105,"UI đóng modal sau response ok.")],
validation=dict(method="static_edit_control_proxy_whitelist_and_success_ui_trace",command=None,result="Đối chiếu control, dirty state, payload, proxy và success UI.",limitations="Chưa browser/API; chưa xác nhận caller đổi location trong edit mode."),
recommendation="Nếu không hỗ trợ, khóa/ẩn dropdown với thông báo. Nếu hỗ trợ, triển khai qua backend validation/authorization, history và response.",
acceptance="Đổi cơ sở hoặc bị ngăn rõ trước submit, hoặc reload chứng minh giá trị mới; test quyền và capacity.",
alignment=["Reality ngày càng dễ nhìn thấy hơn","Ownership ngày càng rõ hơn","Con người bị gián đoạn ít hơn nhưng đúng lúc hơn"], related_tests=["src/dashboard/tests"]),
dict(id="AI-002", title="Agent trả lời đã ghi nhận công việc dù không tạo hay truy vấn công việc", severity="MEDIUM", evidence_level="confirmed_static", category="ai_workflow_durability",
summary="Task wrapper ghi rõ chỉ chạy read-only filter rỗng; nó tạo TaskManagerState chỉ có clinic_id rồi trả acknowledgement đã ghi nhận. Không truyền task_input, task ID hoặc owner. Chỉ xảy ra nếu opt-in ENABLE_AI_ORCHESTRATOR=true.",
trigger="Bật ENABLE_AI_ORCHESTRATOR=true và staff gửi yêu cầu được route sang task.",
impact="Nhân viên có thể dừng theo dõi thủ công vì tin task có owner trong khi không có bản ghi; tái tạo lệ thuộc chat/nhớ việc.",
evidence=[ev("src/clinicai/orchestrator/graph.py",141,165,"Wrapper state chỉ clinic_id rồi trả acknowledgement."),ev("src/clinicai/api/v1/routers/orchestrator.py",23,29,"Endpoint disabled nếu chưa bật flag."),ev("src/clinicai/api/v1/routers/orchestrator.py",58,80,"Chat yêu cầu ops.view và đi qua flag.")],
validation=dict(method="static_agent_wrapper_state_and_api_flag_trace",command=None,result="Đối chiếu wrapper state, task branch và feature gate.",limitations="Chưa gọi endpoint/subgraph; không biết flag runtime hoặc task backend production."),
recommendation="Chỉ ack sau khi task bền vững có owner, SLA, ID và audit event; nếu chưa hỗ trợ, nói rõ chưa ghi nhận.",
acceptance="Task synthetic được tạo đúng một lần trước success; lỗi persist/thiếu owner trả chưa ghi nhận; retry idempotent.",
alignment=["Khoảng thời gian Unknown ngày càng ngắn hơn","Ownership ngày càng rõ hơn","Vấn đề được phát hiện sớm hơn"], related_tests=[]),
dict(id="AI-003", title="Agent xác nhận đã đặt lịch nhưng graph chỉ tìm bác sĩ, không ghi lịch", severity="MEDIUM", evidence_level="confirmed_static", category="ai_workflow_durability",
summary="confirm_node trả đã đặt; scheduling graph không có node create/hold appointment và các node kết thúc trực tiếp. Endpoint chat đang opt-in; scheduling thật chỉ nối khi có pool/location.",
trigger="Bật ENABLE_AI_ORCHESTRATOR=true, nối scheduling graph và staff xác nhận có.",
impact="Nhân viên có thể báo bệnh nhân lịch chưa giữ/chưa có appointment record; slot vẫn có thể bị người khác lấy.",
evidence=[ev("src/clinicai/graphs/scheduling/nodes.py",224,241,"confirm_node chỉ cập nhật state/response."),ev("src/clinicai/graphs/scheduling/graph.py",52,89,"Graph chỉ ask/find/confirm rồi END."),ev("src/clinicai/orchestrator/graph.py",212,218,"Scheduling subgraph chỉ được nối khi có pool/location."),ev("src/clinicai/api/v1/routers/orchestrator.py",23,29,"Chat disabled trừ khi opt-in flag bật.")],
validation=dict(method="static_scheduling_graph_side_effect_and_flag_trace",command=None,result="Đối chiếu lookup, confirm, graph edges và feature gate.",limitations="Chưa gọi graph/API/DB; không có bằng chứng flag bật hoặc nhân viên đã dùng."),
recommendation="Chỉ nói đã đặt sau write-service giữ slot/idempotent trả appointment ID; nếu chưa tích hợp, nói yêu cầu chưa được đặt.",
acceptance="Concurrent synthetic requests chỉ một bên giữ slot; success có appointment ID; retry không tạo bản ghi thứ hai; lỗi persist không trả success.",
alignment=["Khoảng thời gian Unknown ngày càng ngắn hơn","Bệnh nhân ít phải chờ trong bất định hơn","Quyết định dựa trên bằng chứng tốt hơn"], related_tests=[])
]

EXT = dict(id="INF-001", summary="verify-backup.sh không kiểm một số companion auth/media dù backup ghi manifest. Ngoài tep_ket_qua pending, query backup bỏ qua anh_chuyen_khoan dù worker đẩy bảng này và ảnh có thể còn duy nhất trên VPS; archive DB thiếu ảnh chứng từ chuyển khoản chưa lên CFS.",
evidence=[ev("scripts/backup-db.sh",424,424,"Danh sách pending chỉ truy vấn public.tep_ket_qua."),ev("scripts/backup-db.sh",438,490,"Tar được tạo từ đúng các khóa trong danh sách query."),ev("src/clinicai/services/day_tep.py",111,116,"Worker định nghĩa cả tep_ket_qua và anh_chuyen_khoan."),ev("src/clinicai/services/day_tep.py",516,520,"Worker gọi lô đẩy riêng ảnh chuyển khoản."),ev("supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql",223,246,"Ảnh mặc định nằm VPS và dùng trạng thái đẩy chung.")],
recommendation="Archive pending files của mọi bảng chứa tệp, tối thiểu cả hai bảng; manifest đối chiếu count/bytes/hash và restore đọc được từng loại.",
acceptance="Synthetic result và transfer-proof cùng nằm VPS khi CFS lỗi: archive có cả hai; verify fail nếu thiếu; restore drill khớp bytes/SHA.")

def render(items):
    out=[]; hashes={}
    for x in items:
        path=SNAPSHOT/x["path"]; raw=path.read_bytes(); lines=raw.decode("utf-8").splitlines()
        if x["line"]<1 or x["end_line"]>len(lines): raise ValueError(f"bad evidence {x}")
        out.append(dict(path=x["path"],line=x["line"],end_line=x["end_line"],sha256=hashlib.sha256(raw).hexdigest(),excerpt="\n".join(f"{n}: {lines[n-1]}" for n in range(x["line"],x["end_line"]+1))))
        hashes[x["path"]]=hashlib.sha256(raw).hexdigest()
    return out,hashes

def add_note(path, heading, body):
    f=ROOT/path; old=f.read_text() if f.exists() else ""
    if heading not in old: f.write_text(old.rstrip()+("\n\n" if old else "")+heading+"\n\n"+body.strip()+"\n")

def main():
    if not SNAPSHOT.is_dir(): raise SystemExit(f"Missing snapshot {SNAPSHOT}")
    now=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    findings=rj("PHAT-HIEN.json"); by_id={x["id"]:x for x in findings}
    dups=[x["id"] for x in F if x["id"] in by_id]
    if dups: raise SystemExit(f"Refusing duplicate IDs {dups}")
    for x in F:
        x["main_validation"]={"sha":SHA,"status":"still_present_on_main","note":"Đối chiếu static trực tiếp snapshot exact-main; chỉ khẳng định trigger/ảnh hưởng mô tả, không suy ra production.","evidence":render(x["evidence"])[0]}
        x["source_hashes"]=render(x["evidence"])[1]; x["status"]="open"; x["reference_version"]="pinned_main"; findings.append(x)
    old=by_id[EXT["id"]]
    rendered,hashes=render(EXT["evidence"])
    keys={(x["path"],x["line"],x["end_line"]) for x in old["main_validation"]["evidence"]}
    old["main_validation"]["evidence"].extend(x for x in rendered if (x["path"],x["line"],x["end_line"]) not in keys)
    old["source_hashes"].update(hashes)
    keys={(x["path"],x["line"],x["end_line"]) for x in old["evidence"]}
    old["evidence"].extend(x for x in EXT["evidence"] if (x["path"],x["line"],x["end_line"]) not in keys)
    for field in ("summary","recommendation","acceptance"): old[field]=EXT[field]
    wj("PHAT-HIEN.json",findings)

    manifest=rj("MAIN-PHAM-VI.json"); ledger={x["path"]:x for x in manifest["files"]}; touched={}
    for x in F+[old]:
        for path in x["source_hashes"]: touched.setdefault(path,set()).add(x["id"])
    for path,ids in touched.items():
        row=ledger[path]
        if row["status"]=="scanned": row["status"]="traced"
        note="v0.23 partial trace: "+",".join(sorted(ids))+"; not a whole-file review."
        if note not in row.get("method",""): row["method"]=(row.get("method","")+" | "+note).strip(" |")
    wj("MAIN-PHAM-VI.json",manifest)
    checks=rj("KIEM-CHUNG.json"); known={(x.get("id"),x.get("path")) for x in checks["checks"]}
    for x in F+[old]:
        for path in x["source_hashes"]:
            if (x["id"],path) not in known: checks["checks"].append({"id":x["id"],"path":path,"valid":True})
    wj("KIEM-CHUNG.json",checks)

    sev=Counter(x["severity"] for x in findings); levels=Counter(x["evidence_level"] for x in findings); ms=Counter(x["main_validation"]["status"] for x in findings)
    cov=Counter(x["status"] for x in manifest["files"]); suffixes={".py",".pyi",".ts",".tsx",".js",".jsx",".mjs",".cjs",".sql",".sh",".bash",".go",".rs",".java",".kt",".css",".html"}
    cc=Counter(x["status"] for x in manifest["files"] if Path(x["path"]).suffix.lower() in suffixes)
    state=rj("STATE.json"); prev=state["summary"]
    state["updated_at"]=now; state["phase"]="release_security_finance_ai_workflow_checkpoint"; state["next_action"]="Continue exact-main audit on remaining untraced source clusters; resolve view owner/runtime ACL first, then cross-role tenant/object matrix, payment/refund lifecycle, clinical provenance, and remaining API/UI routes. All traces remain partial."
    state["report_status"]="v0.23_88_findings_pending_report_and_bundle_QA; full source audit incomplete"
    state["limits"][0]=f"Full source audit incomplete: {cov['inventoried']} inventoried, {cov['traced']} partial traces, {cov['scanned']} scanned, {cov['excluded']} excluded; traced is not full-file semantic review."
    state["limits"].append("v0.23 candidates are exact-main static traces across CI/deploy, tenant views, TKYK pregnancy writes, checkout hold, appointment edit, file observability and opt-in AI; no runtime/prod configuration was established.")
    state["summary"]=dict(findings=len(findings),severity=dict(sev),evidence_levels=dict(levels),main_status=dict(ms),main_files=len(manifest["files"]),main_partial_traces=cov["traced"],main_coverage=dict(cov),code_like_source_files=dict(definition=prev["code_like_source_files"]["definition"],total=sum(cc.values()),coverage=dict(cc),traced_is_partial=True),new_static_findings_v018=prev.get("new_static_findings_v018",[]),new_findings_v019=prev.get("new_findings_v019",[]),new_findings_v020=prev.get("new_findings_v020",[]),new_findings_v021=prev.get("new_findings_v021",[]),new_findings_v022=prev.get("new_findings_v022",[]),new_findings_v023=[x["id"] for x in F])
    state["blocks"]["infra_events"].update(status="checkpointed_static_slice_not_complete",findings="PHAT-HIEN.json (INF-001..INF-015)",next="INF-013..015 static: include payment-proof metrics/backups, detect untracked CI files, recreate/reverify Caddy. Verify with disposable tests; continue restore/deploy/CI.")
    state["blocks"]["security"].update(status="checkpointed_static_slice_not_complete",findings="PHAT-HIEN.json (SEC-001..SEC-017)",next="SEC-016 pregnancy write assignment and SEC-017 view tenant risk are static. Confirm view owner/ACL and authenticated REST; run two-clinic TKYK role matrix.")
    state["blocks"]["finance"]["next"]="FIN-009 permits hold rewrite after close by static trace; verify balance-increase preconditions on synthetic DB. Refund-by-created-date is explicitly documented and not promoted as a defect. Continue refund/reconciliation."
    state["blocks"]["frontend"].update(status="round6_scheduling_edit_static_only_not_complete",next="CLIN-028/029: doctor-only change not dirty; location is not carried to PATCH. Verify browser/API, then continue remaining dashboard/API flows.")
    state["blocks"]["clinical"]["next"]+=" v0.23 adds CLIN-028/029 appointment edit traces; still static and partial."
    state["blocks"]["integration"]["next"]+=" v0.23 adds opt-in AI task/scheduling acknowledgements before durable write."
    state["blocks"]["integration"]["findings"]="PHAT-HIEN.json (AI-001..AI-003)"
    state["blocks"]["clinical"]["findings"]="PHAT-HIEN.json (CLIN-001..CLIN-029)"
    state["blocks"]["finance"]["findings"]="PHAT-HIEN.json (FIN-001..FIN-009; PHAR-001)"
    state["artifacts"]["integration_script"]="integrate_v023.py"
    for k in ("html_sha256","html_checked_at","bundle_verified_at"): state["artifacts"].pop(k,None)
    state["runtime_summary"]["audit_report_qc"]="v0.22 QA is stale after v0.23 evidence; rebuild HTML and rerun structural/browser/portable ZIP checks."
    wj("STATE.json",state)
    counts=f"Checkpoint v0.23: {len(findings)} hồ sơ, {sev['HIGH']} HIGH, {sev['MEDIUM']} MEDIUM; {levels['reproduced_local']} reproduced_local, {levels['confirmed_static']} confirmed_static, {levels['design_gap']} design_gap. Main: {ms['still_present_on_main']} còn hiện diện; {cov['traced']} traced một phần, {cov['scanned']} scanned. Full audit còn dang dở."
    add_note("NHAN-DINH.md","## v0.23 — release, phân quyền ghi và workflow",counts+"\n\nTích hợp INF-013..015, SEC-016..017, FIN-009, CLIN-028..029, AI-002..003; mở rộng INF-001 để gồm ảnh chứng từ chuyển khoản. SEC-017 cần xác minh owner/ACL runtime; AI chỉ nằm sau cờ opt-in. Hoàn tiền theo created_at là semantics được module công bố, nên chưa xếp lỗi; nếu cần cash-date reporting thì làm rõ yêu cầu sản phẩm.")
    add_note("blocks/infra_events.md","## v0.23 — backup, Caddy và CI", "INF-001 mở rộng ảnh chuyển khoản pending. INF-013 health/Ops bỏ sót backlog ảnh; INF-014 CI bỏ qua untracked; INF-015 restart Caddy giữ file bind-mount cũ. Static exact-main, chưa deploy/Docker/GitHub/backup thật.")
    add_note("blocks/security.md","## v0.23 — write scope và view quyền", "SEC-016: thai-ky POST/PATCH thiếu kiem_khach dù doc() có; preset TKYK có quyền ghi. SEC-017: hai view quyền cấp SELECT authenticated, thiếu tenant filter/security_invoker; rủi ro phụ thuộc owner/ACL runtime. Chưa HTTP/DB/PostgREST. Không mở rộng SEC-011 sang bảng hành trình chung vì policy còn cần chốt.")
    add_note("blocks/finance.md","## v0.23 — giữ tiền thừa", "FIN-009: giu_lai không kiểm closed_at dù huy_giu_lai có; static, cần xác nhận luồng tăng dư sau checkout. Hoàn theo created_at được ghi rõ trong module, nên không nâng thành defect.")
    add_note("blocks/frontend.md","## v0.23 — sửa lịch", "CLIN-028: doctorId không thuộc dirty check. CLIN-029: location dropdown có thể đổi nhưng không qua dirty check/PATCH/proxy; success đóng modal. Static, cần browser/API regression.")
    add_note("blocks/integration.md","## v0.23 — agent acknowledgements", "AI-002: task wrapper chỉ có clinic_id rồi xác nhận đã ghi nhận. AI-003: scheduling graph trả đã đặt nhưng chỉ tìm bác sĩ, không ghi appointment. Cả hai cần bật ENABLE_AI_ORCHESTRATOR; không có bằng chứng runtime/production.")
    add_note("NHAN-DINH.md","## v0.23 giới hạn", "Các finding mới là exact-main static, ngoại trừ probe trước đã mô tả riêng. Không suy ra cấu hình production, tần suất hay sự cố thật.")
    add_note("TIEP-TUC.md","## v0.23 mới tích hợp",counts+"\n\nRà thêm release/CI, ThaiKy write scope, permission views, giữ tiền thừa và sửa lịch UI; các nhánh AI chỉ opt-in. Build/QA HTML và ZIP rồi tiếp tục các block chưa phủ. Exact-main SHA: "+SHA+". Repo WIP giữ nguyên.")
    add_note("BAT-DAU-TU-DAY.md","## Checkpoint v0.23 — tiếp quản audit","Mục tiêu vẫn là full-source audit và trang HTML portable, hoàn chỉnh, trung thực. Canonical findings: PHAT-HIEN.json; exact-main snapshot SHA "+SHA+"; trạng thái/next actions: STATE.json, TIEP-TUC.md. Coverage chỉ là kiểm kê, quét và một phần trace sâu; chưa xong full code. Không sửa application source/migration trong task audit.")
    tp=ROOT/"report.template.html"; t=tp.read_text().replace("v0.22","v0.23").replace("BẢN 0.22","BẢN 0.23")
    t=t.replace("Checkpoint v0.22 bổ sung 7 findings và probe worker synthetic;","Checkpoint v0.23 bổ sung 10 exact-main findings về security, release, finance, UI và AI workflow;")
    tp.write_text(t)
    print(f"Integrated {len(F)} findings; INF-001 extended; {len(touched)} paths now partial traces; full source audit remains incomplete.")

if __name__=="__main__": main()
