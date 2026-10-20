"""Integrate verified workflow and patient-identity candidates into v0.24."""
from __future__ import annotations
import hashlib, json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SNAPSHOT = Path('/tmp/clinicai-audit-main-956ba4f2')
SHA = '956ba4f236b1c92f1280d2097018c199e90ce8c7'

def rj(name): return json.loads((ROOT / name).read_text())
def wj(name, obj): (ROOT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
def ev(path, start, end, detail): return {'path':path,'line':start,'end_line':end,'detail':detail}

F = [
dict(id='CLIN-030', title='Mất phản hồi khi mở lượt mua thuốc có thể tạo hồ sơ khách trùng', severity='MEDIUM', evidence_level='confirmed_static', category='patient_identity_idempotency',
summary='Form cho phép tạo khách chỉ với tên; request không gửi Idempotency-Key và endpoint không dùng guard. Backend tạo hồ sơ trong transaction của PatientService rồi mở lượt ở transaction kế tiếp. Dedupe hồ sơ chỉ khóa theo phone nếu có. Retry sau khi response mất với khách không số điện thoại có thể tạo patient_id mới và một lượt bán lẻ mới.',
trigger='Nhân viên tạo khách mới không nhập số điện thoại; server commit hồ sơ/lượt nhưng phản hồi bị mất; UI báo “Mất kết nối — CHƯA mở lượt” và người dùng gửi lại.',
impact='Có thể sinh hai hồ sơ cho cùng một ý định mua thuốc và hai lượt thuộc hai patient_id; lịch sử mua thuốc và nhận diện khách bị tách. Chưa mô phỏng lỗi mạng.',
evidence=[ev('src/dashboard/app/(dashboard)/pharmacy/KhachMuaThuoc.tsx',46,60,'POST không gửi Idempotency-Key; catch mạng khẳng định chưa mở dù kết quả server có thể chưa biết.'),ev('src/dashboard/app/(dashboard)/pharmacy/KhachMuaThuoc.tsx',272,278,'Số điện thoại là ô nhập tùy chọn.'),ev('src/dashboard/app/(dashboard)/pharmacy/KhachMuaThuoc.tsx',322,329,'Chỉ họ tên bắt buộc để bấm tạo khách và mở lượt.'),ev('src/dashboard/app/api/pharmacy/[action]/route.ts',177,181,'Proxy chỉ chuyển tiếp khóa nếu request đã có khóa.'),ev('src/clinicai/api/v1/routers/pharmacy.py',195,209,'Endpoint không nhận IdempotencyGuard và gọi BanLeService.'),ev('src/clinicai/services/ban_le_service.py',131,142,'Tạo khách qua PatientService trước, sau đó mở/lấy lượt trong transaction thứ hai.'),ev('src/clinicai/services/patient_service.py',181,205,'Chống trùng chỉ chạy khi phone_primary có giá trị.'),ev('src/clinicai/services/ban_le_service.py',281,300,'Chỉ mục nghiệp vụ chỉ duy nhất một lượt đang mở theo từng clinic_patient_id, không gộp hai patient mới.')],
validation=dict(method='static_UI_proxy_API_service_and_patient_dedupe_trace',command=None,result='Đối chiếu payload UI, BFF, chữ ký endpoint, thứ tự transaction, điều kiện phone-dedupe và unique scope lượt bán lẻ.',limitations='Chưa mô phỏng response loss/HTTP retry; test hiện có kiểm trường hợp trùng số điện thoại, không kiểm tạo khách không số điện thoại sau commit nhưng mất response. Không kết luận đã xảy ra trên production.'),
recommendation='Tạo command key ổn định ở đầu ý định tạo khách và xử lý idempotent xuyên suốt create patient + open visit; lý tưởng ghi patient, visit, receipt và event trong một operation/transaction có thể đối soát. Khi timeout phải báo “chưa xác định kết quả” và cho khôi phục theo key.',
acceptance='Sau commit giả lập rồi làm rơi response, retry cùng key trả đúng patient_id/visit_id ban đầu; không tăng số bệnh nhân/lượt. Hai ý định khác nhau vẫn tạo được hai khách khi được xác nhận. BFF/UI không báo chắc “chưa mở” khi trạng thái chưa biết.',alignment=['Reality ngày càng dễ nhìn thấy hơn','Khoảng thời gian Unknown ngày càng ngắn hơn','Lỗi lặp lại dần biến thành cải tiến hệ thống'],related_tests=['src/tests/services/test_ban_le_thuoc_db.py']),
dict(id='CLIN-031', title='Retry chỉ định sau lỗi mạng có thể tạo thêm service_order', severity='MEDIUM', evidence_level='confirmed_static', category='clinical_command_idempotency',
summary='guiThaoTac tạo khóa Idempotency-Key ngẫu nhiên bên trong mỗi lần gọi. Khi fetch lỗi, UI báo thao tác chưa ghi và cho bấm lại; lần gửi sau có khóa khác. Service chỉ phát lại biên nhận theo đúng khóa, còn khóa mới có thể sinh service_order mới cho cùng mã dịch vụ.',
trigger='Chỉ định đã commit nhưng phản hồi bị mất; bác sĩ/thư ký thấy thông báo mất kết nối rồi gửi lại cùng dịch vụ.',
impact='Một ý định có thể thành hai chỉ định/công việc. Có nguy cơ làm sai tải hàng đợi và hóa đơn về sau; chưa chứng minh hệ tự thu tiền trùng hay có sự cố thực tế.',
evidence=[ev('src/dashboard/app/(dashboard)/_lam-viec/api.ts',212,250,'Mỗi lời gọi tạo khóa mới; lỗi mạng được diễn đạt là thao tác chưa được ghi.'),ev('src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx',1598,1619,'Form gửi chỉ định; khi lỗi hiển thị lại trạng thái lỗi mà không hoàn tất thao tác.'),ev('src/dashboard/app/api/luot-kham/route.ts',264,265,'Proxy chuyển nguyên khóa xuống backend.'),ev('src/clinicai/services/chi_dinh_service.py',185,221,'Biên nhận được tìm theo idempotency key; nhánh không replay insert service_order.'),ev('src/tests/services/test_chi_dinh_db.py',188,211,'Test chứng minh cùng khóa chỉ tạo một order/event.'),ev('src/tests/services/test_lan_chi_dinh_db.py',78,90,'Khóa mới cho cùng mã dịch vụ được thiết kế để tạo dòng chỉ định mới.')],
validation=dict(method='static_UI_retry_and_idempotency_receipt_trace_with_existing_test_contracts',command=None,result='Đối chiếu generator khóa, thông báo lỗi, proxy, receipt lookup/insert và hai test mô tả cùng khóa so với khóa mới.',limitations='Chưa giả lập response loss trên trình duyệt/HTTP; các test được đọc làm bằng chứng contract, không chạy trong lượt này.'),
recommendation='Tạo idempotency key cho từng ý định chỉ định ở component/domain action và giữ nguyên đến khi nhận kết quả chắc chắn; lần retry dùng lại khóa. Chỉ tạo khóa khác khi người dùng bắt đầu ý định mới. Đổi thông báo timeout thành trạng thái “chưa xác định”, kèm nút đối soát.',
acceptance='Sau commit rồi làm rơi response, retry cùng intent không tăng order/event; người dùng có thể chủ động tạo lần chỉ định mới bằng intent mới; test browser/API/service bao phủ timeout và đối soát.',alignment=['Khoảng thời gian Unknown ngày càng ngắn hơn','Ownership ngày càng rõ hơn','Quyết định dựa trên bằng chứng tốt hơn'],related_tests=['src/tests/services/test_chi_dinh_db.py','src/tests/services/test_lan_chi_dinh_db.py']),
dict(id='CLIN-032', title='Hàng gọi tái khám chạm trần 500 nhưng màn hình vẫn nói không còn việc', severity='MEDIUM', evidence_level='confirmed_static', category='bounded_queue_visibility',
summary='RecallJobService giới hạn truy vấn ở 500 và trả bi_cat/tran; giao diện DuLieu không khai báo hai trường, không hiển thị cảnh báo. Khi dữ liệu vượt 500, hàng sau không xuất hiện; nhóm không có item vẫn hiện “Không còn ai phải gọi”. Service chỉ ghi log cảnh báo.',
trigger='Có hơn 500 việc recall đến hạn trong phòng khám; API trả 500 dòng đầu theo thứ tự ưu tiên.',
impact='Nhân viên có thể tin hàng đợi đã hết trong khi còn bệnh nhân chưa được gọi; độ trễ theo dõi bị che khuất.',
evidence=[ev('src/clinicai/services/recall_job_service.py',98,131,'Truy vấn chỉ lấy tối đa 500 việc.'),ev('src/clinicai/services/recall_job_service.py',133,155,'Service phát hiện chạm trần và trả bi_cat/tran.'),ev('src/clinicai/core/tran.py',35,41,'canh_bao_neu_day chỉ ghi log; tài liệu mã nói màn hình không thấy cảnh báo.'),ev('src/dashboard/app/(dashboard)/nhac-tai-kham/ViecGoiNhac.tsx',33,38,'Kiểu dữ liệu frontend bỏ bi_cat và tran.'),ev('src/dashboard/app/(dashboard)/nhac-tai-kham/ViecGoiNhac.tsx',123,136,'Danh sách rỗng hiển thị thông điệp không còn ai phải gọi.'),ev('src/dashboard/app/(dashboard)/nhac-tai-kham/page.tsx',41,45,'Trang đưa nguyên response vào component nhưng không bổ sung tín hiệu cắt.')],
validation=dict(method='static_limit_API_response_and_render_trace',command=None,result='Theo từ LIMIT 500 qua bi_cat/tran đến kiểu dữ liệu và nhánh giao diện rỗng.',limitations='Chưa dựng >500 hàng synthetic để kiểm UI; chưa xác minh lượng recall thực tế trên production.'),
recommendation='Dùng dem_va_bi_cat để trả tổng và trạng thái cắt; UI phải hiển thị “đang xem 500/N” hoặc “ít nhất 500, cần thu hẹp/lọc”, không hiển thị câu hết việc khi đã cắt.',
acceptance='Fixture có 501+ việc cho thấy số tổng/cảnh báo, không tuyên bố hết việc; danh sách dưới ngưỡng vẫn giữ hiệu năng và thông điệp hiện tại.',alignment=['Reality ngày càng dễ nhìn thấy hơn','Khoảng thời gian Unknown ngày càng ngắn hơn','Vấn đề được phát hiện sớm hơn'],related_tests=[]),
dict(id='CLIN-033', title='Đóng lời hẹn gọi lại không bắt buộc lưu kết quả cuộc gọi', severity='MEDIUM', evidence_level='confirmed_static', category='followup_outcome_provenance',
summary='Nút “Đã gọi xong — đóng việc” gọi PATCH chỉ mang id. API không nhận outcome; service chỉ ghi dong_luc và dong_boi_staff_id, không ghi interaction hay kết quả cuộc gọi. Projection loại việc đã đóng khỏi hàng chờ.',
trigger='Nhân viên bấm đóng lời hẹn sau giờ hẹn nhưng cuộc gọi hụt, chưa gọi, hoặc cần bác sĩ xử lý.',
impact='Việc biến mất khỏi hàng chờ và trông như đã xử lý nhưng không có bằng chứng bệnh nhân được liên hệ; người trực sau không biết cần gọi lại hay chuyển việc.',
evidence=[ev('src/dashboard/app/(dashboard)/customers/VungLamViecKhach.tsx',284,347,'UI chỉ có nút đóng với nhãn đã gọi xong; không có chọn kết quả.'),ev('src/dashboard/app/api/cskh/hen-goi-lai/route.ts',23,36,'BFF chỉ lấy id và gửi body rỗng.'),ev('src/clinicai/api/v1/routers/cskh.py',601,608,'Handler đóng việc không nhận outcome.'),ev('src/clinicai/services/tuong_tac_cskh_service.py',793,831,'Service kiểm hạn rồi chỉ ghi thời gian đóng/người đóng.'),ev('supabase/migrations/20260809000005_trang_thai_cskh_suy_ra.sql',247,254,'Projection chỉ đưa hẹn gọi lại còn dong_luc NULL vào hàng công việc.')],
validation=dict(method='static_UI_BFF_API_service_projection_trace',command=None,result='Đối chiếu payload và SQL UPDATE với projection queue; không thấy event/outcome trong đường đóng này.',limitations='Không có nhà cung cấp điện thoại hay external call automation; chỉ kết luận thao tác đóng UI không chứng minh cuộc gọi đã thành công. Chưa chạy HTTP/DB test.'),
recommendation='Đóng việc phải yêu cầu một outcome rõ (đã liên hệ, không nghe máy, cần bác sĩ, từ chối) và ghi interaction cùng transaction. Kết quả chưa liên hệ phải giữ/tạo lại follow-up có hạn và owner.',
acceptance='Không thể đóng thiếu outcome; mỗi đóng có actor, thời điểm và kết quả; CHUA_NGHE_MAY/cần bác sĩ tạo trạng thái follow-up tương ứng và vẫn nhìn thấy trên dashboard.',alignment=['Reality ngày càng dễ nhìn thấy hơn','Ownership ngày càng rõ hơn','Lỗi lặp lại dần biến thành cải tiến hệ thống'],related_tests=[]),
dict(id='OPS-001', title='Tác vụ gọi tái khám chỉ được sinh khi có người mở màn CSKH', severity='MEDIUM', evidence_level='design_gap', category='proactive_work_generation',
summary='Service ghi rõ dự án chưa có scheduler và sinh việc ngay trong danh_sach trước khi đọc. GET recall-jobs gọi danh_sach; trang tái khám gọi GET lúc render. Không thấy worker/cron/pg_cron gọi hàm sinh ngoài service/API. Việc tạo queue vì thế phụ thuộc có người mở trang hoặc gọi endpoint generate.',
trigger='Không ai mở màn tái khám và không có caller nền POST /cskh/recall-jobs/generate trong ngày.',
impact='Lời dặn tái khám đủ điều kiện có thể chưa thành công việc hiển thị cho nhân viên; phát hiện muộn phụ thuộc kiểm tra thủ công.',
evidence=[ev('src/clinicai/services/recall_job_service.py',23,29,'Comment nói chưa có hẹn giờ; danh_sach gọi sinh khi mở màn.'),ev('src/clinicai/services/recall_job_service.py',84,95,'sinh_truoc mặc định bật và chạy trước khi đọc queue.'),ev('src/clinicai/api/v1/routers/cskh.py',317,336,'GET sinh trước khi trả; endpoint POST riêng được để dành cắm cron sau.'),ev('src/dashboard/app/(dashboard)/nhac-tai-kham/page.tsx',41,45,'Trang server gọi recall-jobs khi mở.'),ev('src/dashboard/tests/goi-man-khach-boundary.test.mts',17,20,'Test ranh giới ghi rõ việc sinh queue hiện nằm ở lời gọi backend từ trang khách.')],
validation=dict(method='static_caller_search_and_service_route_page_trace',command='rg -n "sinh_viec_nhac_tai_kham|RecallJobService.*sinh" exact-main source excluding tests and Markdown',result='Ngoài SQL/tests, call sites tìm được là RecallJobService.sinh, GET/POST router và dashboard page; không tìm thấy cron, worker hay pg_cron caller.',limitations='Không kiểm cấu hình production/host cron ngoài repo; không khẳng định task chưa được chạy thủ công. Hàm sinh đã idempotent, thuận lợi để gắn scheduler.'),
recommendation='Chạy generator qua job nền idempotent theo lịch, theo tenant/timezone; có heartbeat, tuổi lần chạy cuối, dead-letter/retry và phép đối soát lời dặn đủ điều kiện so với queue. GET chỉ đọc.',
acceptance='Ngày không có user mở màn vẫn sinh đúng queue; job lỗi tạo tín hiệu cảnh báo/owner; gọi lặp an toàn; GET không mang side effect.',alignment=['Khoảng thời gian Unknown ngày càng ngắn hơn','Vấn đề được phát hiện sớm hơn','Con người bị gián đoạn ít hơn nhưng đúng lúc hơn'],related_tests=['src/tests/services/test_hen_tai_kham_db.py']),
dict(id='OPS-002', title='Việc gọi tái khám chưa có người nhận hoặc claim trước khi xử lý', severity='MEDIUM', evidence_level='design_gap', category='workflow_ownership',
summary='Bảng nhắc lưu nguoi_goi_staff_id sau khi đã ghi kết quả và người tạo cho một số luồng thủ công, nhưng không có assignee/claim/lease. Queue list theo clinic và trạng thái; UI không hiển thị người đang chịu trách nhiệm trước cuộc gọi. Đây là gap nếu mục tiêu là một người cụ thể nhận ownership, không phải bằng chứng policy hàng đợi nhóm sai.',
trigger='Clinic dùng queue chung nhiều nhân viên; nhiều người cùng nhìn việc hoặc ai cũng nghĩ người khác sẽ gọi.',
impact='Trước khi thao tác chỉ biết việc còn mở, chưa có bằng chứng ai đang nhận nó; có thể bị bỏ sót hoặc hai người cùng gọi. Nếu hàng đợi nhóm là chính sách có chủ ý, cần thay bằng owner trực ca/coverage rõ.',
evidence=[ev('supabase/migrations/20260807000005_nhac_tai_kham_hai_luot_goi.sql',29,56,'Schema có nguoi_goi_staff_id và goi_luc/dong_luc nhưng không có trường người được giao/claim.'),ev('src/clinicai/services/recall_job_service.py',98,131,'Danh sách lấy việc theo clinic/status/hạn, chỉ JOIN nguoi_goi để hiện người gọi đã ghi.'),ev('src/dashboard/app/(dashboard)/nhac-tai-kham/ViecGoiNhac.tsx',140,167,'Card hiển thị bệnh nhân, số, hạn nhưng không có owner.'),ev('src/clinicai/services/recall_job_service.py',59,60,'Service mô tả việc có người gọi, kết quả và đối soát nhưng không có assignment trước xử lý.')],
validation=dict(method='static_schema_API_UI_field_trace',command=None,result='Đối chiếu cột, SELECT, kiểu dữ liệu và card UI; không thấy assignee/claim transition.',limitations='Cần chủ phòng khám chốt queue nhóm, tự nhận việc hay phân công ca trực trước khi coi đây là lỗi nghiệp vụ; không suy ra double-call đã xảy ra.'),
recommendation='Chốt một chính sách cụ thể: assignment cá nhân, claim lease có timeout/reassign, hoặc queue theo ca có một owner trực và backup. Ghi assignment/reassignment/claim cùng actor và thời điểm; tách assignee khỏi người thực hiện.',
acceptance='Mỗi việc mở có policy owner hiển thị, không thể claim kép, hết lease có đường nhận lại; hoặc dashboard nói rõ owner là nhóm/ca nào và cách theo dõi coverage.',alignment=['Ownership ngày càng rõ hơn','Nhân viên làm việc trong điều kiện bền vững hơn','Con người bị gián đoạn ít hơn nhưng đúng lúc hơn'],related_tests=[]),
dict(id='PAT-001', title='Hàng chờ MPI PENDING không có màn/API để nhân viên xem xét', severity='MEDIUM', evidence_level='design_gap', category='identity_resolution_ownership',
summary='Tạo bệnh nhân gọi MPI autoqueue kiểu best-effort; MPIService chèn mục PENDING và có getter get_pending_queue, nhưng tìm trong API/dashboard/tests/migrations không thấy route/UI hoặc transition xử lý MERGED/REJECTED/REVIEW. Các nghi vấn trùng vì vậy chưa thành công việc có owner qua ứng dụng.',
trigger='Patient intake phát hiện candidate score đủ ngưỡng và ghi vào mpi_merge_queue.status=PENDING.',
impact='Hồ sơ có thể bị nghi trùng nhưng không có nơi nhìn thấy, phân công reviewer, quyết định merge/từ chối và kiểm tra lại. Không kết luận vận hành không có thao tác SQL ngoài repo.',
evidence=[ev('src/clinicai/services/patient_service.py',307,331,'Tạo hồ sơ gọi autoqueue best-effort; lỗi chỉ được log.'),ev('src/clinicai/services/mpi_service.py',172,240,'Score đủ ngưỡng thì insert hàng MPI trạng thái PENDING.'),ev('src/clinicai/services/mpi_service.py',246,262,'Có helper đọc queue nhưng không phải API route.'),ev('supabase/migrations/20260714000001_baseline_schema.sql',600,610,'Schema có trạng thái PENDING/MERGED/REJECTED/REVIEW và trường reviewer.')],
validation=dict(method='static_exact_symbol_search_across_API_dashboard_migrations_tests',command='rg -n "mpi_merge_queue|get_pending_queue|MPIService" exact-main source',result='Không tìm thấy router, UI, caller getter hoặc luồng cập nhật review status ngoài service/helper và test/schema.',limitations='Không thể loại trừ thao tác SQL thủ công hoặc công cụ ngoài repository; chưa kiểm production queue rows.'),
recommendation='Hoặc xây review workbench có quyền, owner, audit, quyết định idempotent và safeguards chống merge sai; hoặc không tạo queue PENDING cho đến khi quy trình review được triển khai. Đặt SLA/tuổi queue và alert.',
acceptance='Tạo synthetic candidate cho thấy queue item có người/nhóm nhận, có thể approve/reject với lý do và audit, search hồ sơ sau xử lý; backlog lâu ngày có cảnh báo.',alignment=['Reality ngày càng dễ nhìn thấy hơn','Ownership ngày càng rõ hơn','Khoảng thời gian Unknown ngày càng ngắn hơn'],related_tests=[]),
dict(id='PAT-002', title='MPI dùng CCCD đã che để tính điểm nên có thể chấm nhầm hồ sơ trùng', severity='MEDIUM', evidence_level='confirmed_static', category='identity_matching_integrity',
summary='MPIService nhận PatientDTO cho candidate và tạo PatientDTO cho hồ sơ mới. PatientDTO mask CCCD còn 3 số đầu/2 số cuối; score lại so sánh chuỗi CCCD bằng equality và cộng 40 điểm. Hai CCCD khác nhau nhưng cùng đầu/cuối trở thành chuỗi giống nhau. Nếu cùng phone_primary, tổng đã vượt ngưỡng 70 và có thể vào queue PENDING; code này không tự merge.',
trigger='Hai người dùng chung phone_primary và có CCCD khác nhau nhưng cùng ba số đầu và hai số cuối; MPI tìm candidate theo phone và chấm trên DTO đã mask.',
impact='Tạo false-positive trong hàng review, làm giảm độ tin cậy của MPI và có thể gây merge nhầm nếu reviewer thao tác sai. Hiện không thấy review UI/API hay auto-merge, nên không khẳng định hồ sơ đã bị gộp.',
evidence=[ev('src/clinicai/schemas/patient.py',299,301,'Hàm hiển thị CCCD chỉ giữ ba số đầu và hai số cuối.'),ev('src/clinicai/schemas/patient.py',331,357,'PatientDTO áp mask trong validator khi parse dữ liệu.'),ev('src/clinicai/services/mpi_service.py',37,68,'Score dùng equality trên national_id_number và cộng 40; phone cộng 50.'),ev('src/clinicai/services/mpi_service.py',163,166,'Candidate query kết quả raw được chuyển thành PatientDTO.'),ev('src/clinicai/services/mpi_service.py',199,229,'Hồ sơ mới cũng được parse thành PatientDTO trước khi score; điểm đủ ngưỡng ghi queue.'),ev('src/clinicai/services/mpi_service.py',20,27,'Ngưỡng MPI là 70.')],
validation=dict(method='static_schema_validator_to_scoring_and_queue_trace',command=None,result='Đối chiếu masking validator với hai nơi tạo DTO và nhánh score/queue; ví dụ hai CCCD khác cùng prefix/suffix cho cùng masked value.',limitations='Thử nghiệm import model không chạy được do snapshot runtime thiếu pydantic; kết luận về transform dựa vào validator code, chưa có property test/DB run. Queue chỉ là PENDING, không chứng minh merge tự động hay đã xảy ra.'),
recommendation='Tách model nội bộ chứa raw identity fields cho matching khỏi PatientDTO che dùng ở ranh giới API/UI; giữ log không chứa CCCD raw; thêm test cặp CCCD khác nhau cùng mask không được tính là exact match.',
acceptance='Hai CCCD raw khác nhau không cộng điểm exact-ID dù masked display trùng; CCCD raw giống vẫn được nhận diện trong matching nội bộ; serialization API/log không lộ số gốc; threshold/candidate behavior có integration test.',alignment=['Quyết định dựa trên bằng chứng tốt hơn','Lỗi lặp lại dần biến thành cải tiến hệ thống'],related_tests=['src/tests/services/test_mpi_service.py']),
dict(id='INF-016', title='Tải ảnh siêu âm không chặn kích thước thân request trước khi đọc toàn bộ', severity='MEDIUM', evidence_level='confirmed_static', category='upload_resource_exhaustion',
summary='Next route parse request.formData() rồi dựng multipart mới. FastAPI đọc toàn bộ UploadFile bằng file.read() trước khi MediaService kiểm MAX_BYTES=12MB; body-size middleware chỉ áp dụng đúng route upload CSKH. API container có memory limit 1 GB và không thấy giới hạn body toàn cục trong cấu hình Caddy snapshot.',
trigger='Tài khoản có quyền siêu âm gửi multipart lớn hoặc chunked vượt giới hạn qua /api/ultrasound/image.',
impact='Tệp bị spool/đọc hết trước khi trả lỗi; nội dung lớn có thể chiếm bộ nhớ API/Next hoặc làm container quá tải. Chưa thử tải lớn, chưa kết luận có khai thác/thực tế prod.',
evidence=[ev('src/dashboard/app/api/ultrasound/image/route.ts',53,80,'BFF gọi request.formData rồi dựng lại multipart trước khi forward.'),ev('src/clinicai/api/v1/routers/ultrasound.py',209,227,'Handler đọc file.read không giới hạn trước khi gọi service.'),ev('src/clinicai/services/media_service.py',328,344,'Trần 12MB được kiểm sau khi data bytes đã được tạo.'),ev('src/clinicai/api/middleware.py',93,100,'Middleware giới hạn body chỉ chạy trên đúng đường CSKH ket-qua/tep.'),ev('docker-compose.yml',172,183,'API container giới hạn RAM 1GB.')],
validation=dict(method='static_multipart_BFF_API_service_middleware_container_trace',command=None,result='Theo dữ liệu từ browser formData qua BFF, UploadFile.read, rồi mới đến kiểm MAX_BYTES; middleware path predicate chỉ khớp route khác.',limitations='Không gửi request lớn/chunked; chưa xác minh proxy/host ngoài cấu hình repo có limit bổ sung; mức cạn tài nguyên phụ thuộc concurrency/runtime.'),
recommendation='Đặt trần request ở ingress/server trước multipart parse cho mọi upload route; đọc stream theo chunk với tổng byte tối đa và dừng ngay khi vượt; kiểm thêm quota/concurrency, giữ service cap làm lớp thứ hai.',
acceptance='Content-Length lớn và chunked quá cỡ đều bị từ chối sớm bằng 413 trước khi handler đọc hết; dưới 12MB hoạt động; tải đồng thời không vượt budget memory/spool.',alignment=['Vấn đề được phát hiện sớm hơn','Nhân viên làm việc trong điều kiện bền vững hơn'],related_tests=['src/tests/test_upload_size_middleware.py']),
]

EXT = dict(id='SEC-017',
summary='v_quyen_hieu_luc có SELECT authenticated, owner postgres và không security_invoker. Trên DB CI, EXPLAIN dưới role authenticated quét capability_grant mà không có tenant predicate; EXPLAIN bảng gốc có predicate RLS current_clinic_ids(). Đây là bằng chứng mạnh về đường đọc có thể bỏ RLS, nhưng chưa SELECT hàng clinic B. v_quyen_thuc_te cũng grant authenticated nhưng hiện EXPLAIN bị từ chối vì hai helper thiếu EXECUTE sau ACL hardening; không có bằng chứng view này đang lộ row. Chỉ cấp EXECUTE có thể mở view owner-rights đọc roster/phòng không tenant-filter, trong đó vi_tri_lam_viec không RLS.',
trigger='JWT authenticated đọc v_quyen_hieu_luc qua PostgREST. v_quyen_thuc_te hiện bị permission denied; chỉ sửa EXECUTE mà không thiết kế lại owner/tenant/base privileges có thể mở rộng đường dữ liệu.',
impact='v_quyen_hieu_luc có thể lộ metadata capability, staff, scope giữa clinic. v_quyen_thuc_te hiện là rủi ro latent và functionality failure, không phải bằng chứng đã lộ dữ liệu. Chưa dựng hai clinic fixture hoặc đọc rows.',
recommendation='Nếu quyền view chỉ dành backend, revoke authenticated. Nếu cần client, thiết kế invoker/owner và quyền từng bảng nền, tenant predicates và helper ACL theo least privilege; không chỉ thêm EXECUTE. Kiểm bằng fixture hai clinic trên DB độc lập từ đúng migrations.',
acceptance='Trên database disposable hai clinic đã chạy đúng migrations: authenticated clinic A không nhận bất kỳ row/scope clinic B ở cả hai view; view backend-only bị từ chối có chủ ý; helper và base table grants được kiểm riêng.',
validation=dict(method='catalog_and_read_only_explain_on_local_CI_PostgreSQL_17',command='Trên ci_may_test (BEGIN READ ONLY; SET LOCAL ROLE authenticated): EXPLAIN SELECT clinic_id,staff_id,capability FROM v_quyen_hieu_luc; đối chứng EXPLAIN trực tiếp capability_grant; EXPLAIN v_quyen_thuc_te.',result='v_quyen_hieu_luc: owner postgres, reloptions NULL, authenticated SELECT=true; EXPLAIN không có tenant filter. Base-table positive control có current_clinic_ids() predicate. v_quyen_thuc_te: EXPLAIN lỗi permission denied for quyen_theo_lich_bang(); ACL catalog cho thấy cả quyen_theo_lich_bang() và quyen_theo_vi_tri_bang() không có EXECUTE authenticated. Không SELECT rows.',limitations='Local ci_may_test PostgreSQL 17.11, catalog/EXPLAIN read-only; không có migration ledger nên schema không được chứng minh dựng chính xác từ snapshot; DB có cảnh báo dùng chung. Không đọc hàng dữ liệu, không fixture hai clinic, không production. v_quyen_thuc_te còn cần thiết kế base privileges vì vi_tri_lam_viec không RLS và authenticated không có SELECT.' ))


def render(items):
    out=[]; hashes={}
    for x in items:
        path=SNAPSHOT/x['path']; raw=path.read_bytes(); lines=raw.decode('utf-8').splitlines()
        if x['line']<1 or x['end_line']>len(lines): raise ValueError(f"bad evidence {x}")
        digest=hashlib.sha256(raw).hexdigest()
        out.append({'path':x['path'],'line':x['line'],'end_line':x['end_line'],'sha256':digest,'excerpt':'\n'.join(f'{n}: {lines[n-1]}' for n in range(x['line'],x['end_line']+1))})
        hashes[x['path']]=digest
    return out,hashes

def add_note(path, heading, body):
    f=ROOT/path; old=f.read_text() if f.exists() else ''
    if heading not in old: f.write_text(old.rstrip()+('\n\n' if old else '')+heading+'\n\n'+body.strip()+'\n')

def main():
    findings=rj('PHAT-HIEN.json'); by_id={x['id']:x for x in findings}
    dups=[x['id'] for x in F if x['id'] in by_id]
    if dups: raise SystemExit(f'Refusing duplicate IDs {dups}')
    for x in F:
        x['main_validation']={'sha':SHA,'status':'still_present_on_main','note':'Đối chiếu code và call path trên snapshot main ghim; chỉ kết luận phạm vi mô tả, không suy ra đã khai thác hoặc hành vi production.','evidence':render(x['evidence'])[0]}
        x['source_hashes']=render(x['evidence'])[1]; x['status']='open'; x['reference_version']='pinned_main'; findings.append(x)
    old=by_id[EXT['id']]
    rendered,hashes=render(old['evidence'])
    # Refresh all existing evidence excerpts from the pinned source and add runtime-specific migration evidence.
    old['main_validation']['evidence']=render(old['evidence'])[0]
    old['source_hashes'].update(render(old['evidence'])[1])
    extra=[ev('supabase/migrations/20260928000097_quyen_theo_lich_phong.sql',60,102,'V_quyen_thuc_te được tạo và cấp SELECT cho authenticated.'),ev('supabase/migrations/20261019100000_harden_public_function_acl.sql',9,24,'ACL hardening revoke PUBLIC rồi whitelist helper; hai function theo lịch/vị trí bị bỏ sót.'),ev('supabase/migrations/20260929000001_doi_nguoi_trong_ca.sql',168,229,'View cuối thiếu security_invoker, không lọc clinic trên roster và được grant authenticated.')]
    # Avoid duplicate source-span evidence.
    keys={(e['path'],e['line'],e['end_line']) for e in old['evidence']}
    for e in extra:
        if (e['path'],e['line'],e['end_line']) not in keys: old['evidence'].append(e); keys.add((e['path'],e['line'],e['end_line']))
    old['main_validation']['evidence']=render(old['evidence'])[0]
    old['source_hashes'].update(render(old['evidence'])[1])
    for k in ('summary','trigger','impact','recommendation','acceptance','validation'): old[k]=EXT[k]
    old['main_validation']['note']='Static view/GRANT evidence exact-main plus read-only catalog/EXPLAIN on local ci_may_test; v_quyen_hieu_luc can bypass base RLS under authenticated, while v_quyen_thuc_te currently fails its helper ACL. No row disclosure was queried and no production behavior is claimed.'

    # Add exact service-side evidence to existing SEC-011; it is the same object-scope flaw, not a duplicate finding.
    sec11=by_id['SEC-011']
    extra11=[ev('src/clinicai/services/clinical_record_service.py',884,908,'Nhánh lấy visit theo appointment_id và clinic không đối chiếu visit.clinic_patient_id với patient_id đã gate assignment.')]
    keys={(e['path'],e['line'],e['end_line']) for e in sec11['evidence']}
    for e in extra11:
        if (e['path'],e['line'],e['end_line']) not in keys: sec11['evidence'].append(e)
    sec11['main_validation']['evidence']=render(sec11['evidence'])[0]
    sec11['source_hashes'].update(render(sec11['evidence'])[1])
    sec11['validation']['limitations']=(sec11['validation'].get('limitations','')+' Mismatch case: assigned patient B paired with appointment A remains untested at HTTP/DB; exact-main static trace confirms the IDs are not cross-checked in this branch.')
    wj('PHAT-HIEN.json',findings)

    manifest=rj('MAIN-PHAM-VI.json'); ledger={x['path']:x for x in manifest['files']}; touched={}
    for x in F+[old,sec11]:
        for path in x['source_hashes']: touched.setdefault(path,set()).add(x['id'])
    for path,ids in touched.items():
        row=ledger[path]
        if row['status'] in ('scanned','inventoried'): row['status']='traced'
        note='v0.24 partial trace: '+','.join(sorted(ids))+'; not a whole-file review.'
        if note not in row.get('method',''): row['method']=(row.get('method','')+' | '+note).strip(' |')
    wj('MAIN-PHAM-VI.json',manifest)
    checks=rj('KIEM-CHUNG.json'); known={(x.get('id'),x.get('path')) for x in checks['checks']}
    for x in F+[old,sec11]:
        for path in x['source_hashes']:
            if (x['id'],path) not in known: checks['checks'].append({'id':x['id'],'path':path,'valid':True})
    wj('KIEM-CHUNG.json',checks)

    now=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(timespec='seconds')
    sev=Counter(x['severity'] for x in findings); levels=Counter(x['evidence_level'] for x in findings); ms=Counter(x['main_validation']['status'] for x in findings)
    cov=Counter(x['status'] for x in manifest['files']); suffixes={'.py','.pyi','.ts','.tsx','.js','.jsx','.mjs','.cjs','.sql','.sh','.bash','.go','.rs','.java','.kt','.css','.html'}
    cc=Counter(x['status'] for x in manifest['files'] if Path(x['path']).suffix.lower() in suffixes)
    state=rj('STATE.json'); prev=state['summary']; state['updated_at']=now; state['phase']='identity_recall_idempotency_upload_security_checkpoint'
    state['next_action']='Continue exact-main source review; then verify findings that still lack isolated integration tests, complete one coherent API/UI subsystem at a time, and regenerate the report/package after each checkpoint. Full source audit remains incomplete.'
    state['report_status']='v0.24_97_findings_pending_html_and_bundle_QA; full source audit incomplete'
    state['limits'][0]=f"Full source audit incomplete: {cov['inventoried']} inventoried, {cov['traced']} partial traces, {cov['scanned']} scanned, {cov['excluded']} excluded; traced is not full-file semantic review."
    state['limits'].append('v0.24 adds exact-main partial traces for patient identity/MPI, recall workflow, retry semantics, upload limits, plus read-only CI-DB EXPLAIN for permission views; no application-wide E2E, production exploit, row-level cross-clinic SELECT, or giant upload test.')
    state['limits'].append('v0.24 design gaps around recall scheduling/assignment and MPI review queue require clinic operating-policy confirmation; they are not proof of a production incident.')
    state['summary']=dict(findings=len(findings),severity=dict(sev),evidence_levels=dict(levels),main_status=dict(ms),main_files=len(manifest['files']),main_partial_traces=cov['traced'],main_coverage=dict(cov),code_like_source_files=dict(definition=prev['code_like_source_files']['definition'],total=sum(cc.values()),coverage=dict(cc),traced_is_partial=True),new_static_findings_v018=prev.get('new_static_findings_v018',[]),new_findings_v019=prev.get('new_findings_v019',[]),new_findings_v020=prev.get('new_findings_v020',[]),new_findings_v021=prev.get('new_findings_v021',[]),new_findings_v022=prev.get('new_findings_v022',[]),new_findings_v023=prev.get('new_findings_v023',[]),new_findings_v024=[x['id'] for x in F])
    state['blocks']['security'].update(status='static_view_probe_and_scope_followup_not_complete',findings='PHAT-HIEN.json (SEC-001..SEC-017)',next='SEC-017: v_quyen_hieu_luc authenticated EXPLAIN lacks base RLS predicate on local CI DB; v_quyen_thuc_te currently denied helper EXECUTE. Still needs isolated DB from exact migrations + two-clinic synthetic read test; do not infer prod rows.')
    state['blocks']['clinical'].update(status='round7_patient_recall_and_retry_traces_not_complete',findings='PHAT-HIEN.json (CLIN-001..CLIN-033)',next='CLIN-030/031: create-patient and service-order retry/idempotency gaps static; CLIN-032/033: recall truncation and close-without-outcome. Validate in disposable API/browser tests; continue remaining clinical forms, lab lifecycle and checkout.')
    state['blocks']['infra_events'].update(status='checkpointed_upload_limit_added_not_complete',findings='PHAT-HIEN.json (INF-001..INF-016)',next='INF-016 multipart body cap missing on ultrasound upload; validate early rejection on isolated request harness. Continue recovery/observability source review.')
    state['blocks']['patient_identity']=dict(status='mpi_static_trace_not_complete',findings='PHAT-HIEN.json (PAT-001..PAT-002)',next='MPI autoqueue has no visible review workflow; masked CCCD feeds scoring. Confirm product policy and add synthetic tests without using PHI.')
    state['blocks']['operations']=dict(status='recall_workflow_design_gaps_not_complete',findings='PHAT-HIEN.json (OPS-001..OPS-002)',next='Recall work generation depends on page reads; task assignment policy is unresolved. Confirm queue-vs-person ownership policy and background scheduler SLA.')
    state['artifacts']['integration_script']='integrate_v024.py'
    for k in ('html_sha256','html_checked_at','bundle_verified_at','bundle_entries'): state['artifacts'].pop(k,None)
    state['runtime_summary']['audit_report_qc']='v0.23 HTML/ZIP is stale after v0.24 findings; rebuild and rerun structural/browser/portable bundle checks.'
    wj('STATE.json',state)

    counts=f"Checkpoint v0.24: {len(findings)} hồ sơ ({sev['HIGH']} HIGH, {sev['MEDIUM']} MEDIUM); {ms['still_present_on_main']} còn hiện diện, {ms['partially_addressed_on_main']} xử lý một phần, {ms['addressed_on_main']} đã có sửa trên main. Main: {cov['traced']} trace một phần, {cov['scanned']} scanned. Full source audit vẫn chưa xong."
    add_note('NHAN-DINH.md','## v0.24 — idempotency, MPI và queue tái khám',counts+'\n\nThêm CLIN-030..033, OPS-001..002, PAT-001..002 và INF-016. Bổ sung EXPLAIN read-only cho SEC-017; mở rộng SEC-011 bằng mismatch appointment/patient cụ thể. Các đường retry và upload vẫn cần probe trong môi trường disposable; hai gap assignment/scheduler là chính sách cần chốt.')
    add_note('blocks/clinical.md','## v0.24 — retry mua thuốc/chỉ định và CSKH', 'CLIN-030: tạo khách mua thuốc không có key, patient insert và lượt mở tách transaction; số điện thoại rỗng cho phép duplicate sau timeout. CLIN-031: key chỉ định ngẫu nhiên mỗi request nên retry không replay. CLIN-032: recall giới hạn 500 nhưng UI bỏ bi_cat/tran. CLIN-033: đóng hẹn gọi không yêu cầu outcome/interaction. Tất cả static, chưa chạy fault injection/browser.')
    add_note('blocks/integration.md','## v0.24 — queue, owner và MPI', 'OPS-001/002: generator gọi tái khám chạy theo GET và chưa có assignee/claim trước thao tác; cần xác nhận policy. PAT-001: MPI PENDING có getter nhưng chưa thấy app route/UI/review status path. PAT-002: PatientDTO masking được dùng trong scoring CCCD; candidate false-positive chỉ vào PENDING, không có bằng chứng auto-merge.')
    add_note('blocks/infra_events.md','## v0.24 — giới hạn upload siêu âm','INF-016: BFF request.formData + backend file.read toàn bộ trước khi kiểm 12MB; middleware hiện chỉ chặn CSKH upload. Static, chưa thử body quá cỡ/chunked hoặc proxy ngoài repo.')
    add_note('blocks/security.md','## v0.24 — xác minh view quyền trên CI DB','SEC-017: authenticated EXPLAIN v_quyen_hieu_luc bỏ predicate RLS trong plan nhưng base table có predicate. v_quyen_thuc_te hiện lỗi thiếu EXECUTE hai helper; chỉ cấp EXECUTE có thể mở dữ liệu unscoped. Local ci_may_test PG17.11, catalog/EXPLAIN read-only, không SELECT rows/production. SEC-011 được bổ sung exact mismatch appointment/patient evidence, chưa có regression test.')
    add_note('TIEP-TUC.md','## v0.24 mới tích hợp',counts+'\n\nĐọc tiếp các block còn thiếu; không coi trace là full-file review. Điểm tiếp tục: STATE.json + MAIN-PHAM-VI.json + PHAT-HIEN.json. Main exact SHA: '+SHA+'. WIP checkout ban đầu giữ nguyên.')
    add_note('BAT-DAU-TU-DAY.md','## Checkpoint v0.24 — tiếp quản audit', 'Mục tiêu full-source audit và standalone HTML vẫn đang làm. Snapshot main exact SHA '+SHA+'. Đọc STATE.json, PHAT-HIEN.json, MAIN-PHAM-VI.json và TIEP-TUC.md; traced chỉ là một phần đường code, chưa đọc hết toàn bộ file. Không sửa application source/migrations trong task audit. Đã có candidates mới về retry, recall, MPI và upload; report/ZIP cần rebuild sau checkpoint.')
    template=ROOT/'report.template.html'; t=template.read_text()
    t=t.replace('v0.23','v0.24').replace('BẢN 0.23','BẢN 0.24').replace('Checkpoint v0.23 tích hợp 10 finding mới, mở rộng INF-001 và giữ lại bằng chứng từ các lượt trước.','Checkpoint v0.24 bổ sung 9 finding về retry, MPI, queue tái khám và giới hạn upload; SEC-017 có thêm phép EXPLAIN read-only. Phạm vi full source vẫn chưa hoàn tất.')
    t=t.replace('Bản 0.21; audit toàn code chưa hoàn tất.','Bản 0.24; audit toàn code chưa hoàn tất.')
    template.write_text(t)
    print(f'Integrated {len(F)} findings and refreshed SEC-017/SEC-011; touched {len(touched)} files. Full source audit remains incomplete.')

if __name__ == '__main__': main()
