## Bổ sung từ Round 44 — identity đơn thuốc, quyền duyệt và recovery self-hosted

- Đơn thuốc cần so sánh danh tính catalog cùng row ID và hướng dẫn; nếu người dùng đổi drug_catalog_id mà nhãn/định lượng không đổi, lưu vẫn phải đổi ID hoặc từ chối rõ. Giữ no-op an toàn cho payload thực sự không đổi.
- Quyền duyệt kết quả là lệnh có thể mở release gate. Cùng capability phải đi với kiểm tra bệnh nhân thuộc bác sĩ được giao; kiểm tra phạm vi trong cùng transaction ghi và ghi rõ reviewer/ủy nhiệm. Danh sách có lọc không thay kiểm tra trên lệnh ghi.
- Quan hệ cha–con cấu hình cần invariant phía service/DB: phòng active chỉ nằm dưới cơ sở active; việc tạo/bật phòng kiểm tra cả trạng thái cha. Mọi truy vấn điều phối nên áp cùng luật, không chỉ lọc cờ phòng.
- Recovery contract phải theo Supabase self-hosted: artifacts xác định rõ public DB, auth identities/passwords, session/MFA policy, platform config cần dựng lại, files/CFS, migration ledger, ACL và phiên bản image. Không phụ thuộc cloud PITR trong manifest/runbook khi cloud không phải nguồn vận hành. Drill phải kiểm đăng nhập thật bằng fixture, quyền, media, DB/ACL/ledger và workflow mẫu; restore public/schema-only không đồng nghĩa stack sẵn sàng.

## Bổ sung thiết kế từ Round 34 — scope theo đối tượng, completeness và phục hồi

- Quyền cơ sở phải kiểm trên đối tượng: X-Location-ID chỉ cung cấp context; backend so location của visit/order/file với identity. Ngoại lệ đa cơ sở của partner là policy riêng.
- Đọc tệp đúng ngữ cảnh: lọc appointment/order/bên trước giới hạn; mọi list cap phải trả cursor/has_more/total và không để UI biến phần chưa đọc thành “không có”. Áp cùng contract cho danh sách phục hồi.
- Availability và lệnh ghi dùng cùng location: selected location phải truyền đến roster/capacity và write; đổi cơ sở thì tải lại dữ liệu.
- Ý định phụ sau thao tác chính phải bền: đổi lịch và nhắc gọi khách là một command hoặc có outbox/retry, owner và trạng thái. UI không báo hoàn tất khi reminder chưa lưu hoặc chưa có recovery path.
- Idempotency phải chịu đồng thời: check-then-insert không bảo đảm replay an toàn; invariant/lock bao trùm entity và mốc nghiệp vụ, có quy tắc hoàn tác rồi làm lại.

## Bổ sung thiết kế từ Round 31 — lịch sử CSKH và queue có tài nguyên inactive

- **Lịch sử có completeness contract:** cap ở request bundle phải trả total/cursor/has_more theo cohort hoặc chuyển sang đọc riêng từng bệnh nhân. Empty state chỉ dùng khi hệ thống biết đã đọc hết phạm vi; UI phân biệt “không có” với “chưa đọc hết”.
- **Undo kiểm tra dependency hiện hành:** khi khôi phục queue, xác minh phòng còn active và đúng cơ sở/node. Nếu không còn hợp lệ, chuyển sang hàng “cần định tuyến lại” có owner và timestamp; không để trạng thái chờ nằm ngoài bảng phòng.
- **Ownership khiếu nại cần hợp đồng riêng:** tách người ghi nhận, người tiếp nhận ban đầu, current owner, người xử lý/đóng; định nghĩa nhận bàn giao, SLA, escalation, reopen. Đây là yêu cầu product/ops cần chốt, không phải kết luận code đã vi phạm policy.

## Bổ sung thiết kế từ Round 30 — chứng từ, danh mục chuẩn và audit trail

- **Artifact có thể tự đứng:** mọi XLSX/PDF xuất khỏi ứng dụng phải giữ lại cảnh báo, phạm vi, thời điểm, phiên bản policy và ngoại lệ cần đối chiếu; hoặc từ chối tạo file khi contract chưa đạt. Preview không được là nơi duy nhất nói một file cần kiểm tra.
- **Danh tính thuốc có chủ sở hữu:** mapping mẫu chỉ là gợi ý khởi đầu; nguồn kê đơn và tồn kho phải tham chiếu định danh catalog được quản lý, lưu hoạt chất/hàm lượng/dạng dùng và brand theo policy phòng khám. Resolver cần trả trạng thái “không map/đa nghĩa” có thể nhìn thấy thay vì tự hợp nhất tên.
- **Event trail:** tách event chuyển trạng thái khỏi audit command của người dùng; lưu actor, request key, revision và kết quả để retry, timeline và KPI cùng hiểu một ngữ nghĩa.

## Bổ sung thiết kế từ Round 29 — phạm vi, freshness và đối soát

Thiết kế đích cần phân biệt một chỉ số tổng đầy đủ với một trang xem trước bị giới hạn. KPI vận hành nên lấy aggregate độc lập khỏi danh sách preview hoặc công khai total, cursor và trạng thái truncated; timestamp phải gắn với từng nguồn dữ liệu thay vì dùng lần đọc thành công của một panel làm dấu trực tiếp cho cả màn.

Số dư hồ sơ khách phải có định nghĩa phạm vi rõ ràng. Nếu nhãn là tổng công nợ hiện tại, nguồn nên là ledger/aggregate canonical không bị giới hạn theo số lượt lịch sử; nếu chỉ là năm lượt gần nhất, UI phải gọi đúng tên, thể hiện thời gian/phạm vi và dẫn đến sổ công nợ đầy đủ. Giá trị chưa đọc được phải có trạng thái riêng, không suy thành 0 hoặc cấu hình tắt.

Thu tiền liệu trình cần dùng chung bất biến hoàn tiền và receipt với các nguồn payment khác: số tiền cộng dồn không vượt số đã thu kể cả khi hoàn nhiều lần/lẻ buổi; command và receipt phải nguyên tử hoặc có reconciliation/idempotency bền sau commit. Mỗi chốt cần synthetic tests trước khi bán rộng; audit hiện tại mới chỉ xác nhận static path, chưa chứng minh lỗi production.

# Thiết kế đích — đề xuất cần kiểm chứng bằng triển khai

Đây là thiết kế đề xuất, chưa phải kiến trúc đã hiện thực. Các quyết định còn phụ thuộc
mô hình bán, mức cam kết vận hành và kết quả audit sâu tiếp theo. Không có số tải đo mới
trên production trong đợt này.

## 1. Điều sản phẩm cần bảo đảm

ClinicAI cần bảo đảm ba điều cùng lúc: thao tác nghiệp vụ đúng; người dùng hiểu đúng
trạng thái; và đội vận hành có thể giải thích, phục hồi khi có lỗi. Một trang đẹp hoặc
API trả 200 chưa đủ chứng minh cả ba.

Ví dụ: lưu được phiếu khám là một kết quả; tạo được việc CSKH gọi tái khám là kết quả
khác. Sản phẩm phải cho biết kết quả nào đã chắc chắn, kết quả nào đang chờ đồng bộ,
ai sẽ xử lý nếu nó thất bại. Đây là nền của alignment, trước khi bổ sung AI.

## 2. Giữ lõi hiện tại, siết ranh giới module

Khuyến nghị tiếp tục một ứng dụng backend chia module rõ, dùng Postgres để giữ bất biến
và giao dịch. Tái sử dụng worker và sự kiện đã có. Tách process khi cần cô lập lỗi;
tách microservice chỉ khi có bằng chứng về tải, quyền sở hữu đội hoặc yêu cầu cách ly.

| Module | Sở hữu quyết định và dữ liệu | Hợp đồng với module khác |
|---|---|---|
| Danh tính & quyền | Tài khoản, membership, cơ sở, capability, người làm thay | Một identity tin cậy; quyền kiểm trên đối tượng thực |
| Lịch & nguồn lực | Lịch hẹn, ca trực, phòng, sức chứa, giữ chỗ | Đặt/xếp/hủy có lý do, version và receipt |
| Lượt khám & phối hợp | Lượt, hàng chờ, phiên, trách nhiệm/bàn giao | Trạng thái và bước tiếp theo có chủ; không tự suy trạng thái y khoa |
| Hồ sơ & kết quả | Phiếu phiên bản, chỉ định, thực hiện, kết quả và xác nhận đọc | Kết quả gắn phiên bản; thay kết quả làm mất hiệu lực xác nhận cũ khi phù hợp |
| Tiền & đối soát | Báo giá, ảnh chụp lần thu, giảm/hoàn, công nợ | Số tiền chính thức do server tính; ghi sổ bất biến; sửa bằng bút toán/đính chính |
| Thuốc & vật tư | Đơn, mua, phân lô, giao, trả, tồn và điều chỉnh | Phân biệt kê, bán, xuất kho, giao thực tế, trả và kết cục tiền |
| CSKH & hẹn sau khám | Lời hẹn có cấu trúc, việc gọi, kết quả liên hệ | Nhận dữ liệu tối thiểu cần thiết; không cần quyền đọc toàn bệnh án |
| Nền vận hành | Command receipt, outbox, timer, giao thông báo, audit, file | Giao nhận có trạng thái, retry, đo độ trễ; không chứa luật điều trị |

Không cần tạo tám framework mới. Bắt đầu bằng API nội bộ rõ, sơ đồ phụ thuộc,
test bất biến và tách các hàm đang trộn trách nhiệm khi sửa đúng khu vực đó.

Một tín hiệu cần đưa vào kế hoạch đóng gọn: trên main ghim, `payment_service.py` có 2.400 dòng; `PaymentService` trải từ dòng 324–1686, gom ghi thu, xác minh, void/hoàn tác, tác động thuốc, snapshot và event. Độ dài không tự nó chứng minh lỗi nghiệp vụ, nhưng làm khó việc review thay đổi và xác định ownership. Khi sửa miền tiền, tách dần use case/orchestrator/adapter bên trong cùng module; giữ transaction và thứ tự khóa nguyên vẹn, chưa tách service chỉ vì file lớn.

## 3. Hợp đồng để hệ thống nhìn thấy chính mình

### Sự thật, ghi nhận và suy luận

Mỗi thông tin quan trọng cần nguồn, phiên bản và thời điểm. Không thêm mọi trường vào
mọi bảng; áp trước cho kết quả, bàn giao, chờ, cảnh báo và các chỉ số dùng ra quyết định.

- `occurred_at`: thời điểm nghiệp vụ xảy ra nếu biết; lưu người/nguồn khai và khả năng chỉnh.
- `recorded_at`: thời điểm server ghi nhận, không được đổi thành thời điểm thực tế.
- `observed_at` hoặc `as_of`: thông tin được quan sát/cập nhật đến đâu.
- `evidence_ref` + `revision`: bản ghi/sự kiện/phiên bản nào chứng minh.
- `knowledge_status`: đã xác nhận / do người khai / suy luận / chưa biết / mâu thuẫn.

Ví dụ, “đã đọc kết quả” phải gắn với kết quả nào, phiên bản nào và người xác nhận.
Hoàn tất phiên khám sau lúc bắt đầu lấy mẫu không đủ chứng minh hành động đọc.
“Khách đã về” vẫn là sự thật riêng; thuốc có thể đã giao, mua ngoài, từ chối hoặc chưa rõ.

### Trạng thái công việc khác kết quả chăm sóc

Một việc có thể đóng vì đã làm xong, bị hủy, không còn phù hợp hoặc bàn giao sang
nơi khác. Giao diện và báo cáo phải giữ lý do đó. Nếu tất cả cùng thành “xong”,
chỉ số hiệu suất sẽ thưởng cho việc đóng hồ sơ thay vì hoàn tất công việc.

### Ownership đến tận bàn giao

Ưu tiên mở rộng worklist/assignment hiện có nếu đáp ứng được các trạng thái sau:

`mới → đã giao → đã nhận → đang xử lý → chờ bên khác → hoàn tất/huỷ`

Bàn giao cần người/nhóm nhận, thời điểm chấp nhận, lý do và đường leo thang khi chưa
có người nhận. Việc đang chờ đối tác vẫn có người nội bộ theo dõi. Đổi ca/vắng mặt
chuyển trách nhiệm bằng lệnh có lịch sử; không suy ownership chỉ từ vai hoặc chuông đã gửi.

Source hiện tại đã có `assigned_to`, actor event và đường nhận ca riêng cho siêu âm;
lệnh worklist chung chủ yếu quản lý trạng thái/quyền/version. CLIN-004 đề xuất thống
nhất hợp đồng nhận/bàn giao, không tạo một hệ việc song song và không khóa người hỗ trợ.

### Dữ liệu cũ là trạng thái cần thấy

Read model trả `data`, `as_of`, `source_revision`, `is_complete`, `next_cursor` khi có
phân trang. Client giữ dữ liệu cũ để người dùng còn tham khảo nhưng phải gắn nhãn cũ,
mốc tải thành công cuối và lỗi đang có. Mất kết nối SSE, API tải thất bại và không có
dữ liệu là ba trạng thái khác nhau.

Riêng sổ thu/hoàn và đối soát: phân trang không được làm KPI tổng trở thành tổng của trang đầu. API phải trả `total_count`, `has_more`/cursor và aggregate theo toàn bộ scope đã lọc; response chưa đủ dữ liệu phải có trạng thái rõ. Cursor cần sắp xếp ổn định theo thời điểm + khóa giao dịch. CSV/XLSX phải đọc đủ cùng một scope, hoặc ghi trạng thái/counter rõ nếu xuất bị dừng. FIN-005 hiện chứng minh code còn `LIMIT 3000` và chỉ log cảnh báo; đây là hợp đồng cần chốt trước khi dùng màn làm nguồn đối soát.

Với báo cáo/hoá đơn theo ngày, API phải phân biệt khoảng người dùng yêu cầu và khoảng dữ liệu thực sự xử lý. Không clamp im lặng. FIN-006 cho thấy export hoá đơn và báo cáo cuối ngày có thể nhận khoảng dài nhưng chỉ truy vấn 93 ngày cuối; hệ thống cần trả đủ theo job/phân lô hoặc từ chối rõ, đồng thời hiển thị effective period, completeness và số bản ghi trên preview lẫn file.

## 4. Lệnh ghi và bất biến

Mỗi ý định ghi có tác động cần ID ổn định trước lần gửi đầu, scope theo clinic,
người gọi và loại thao tác. Server lưu receipt/result trong cùng giao dịch với thay đổi.
Gửi lại cùng ID và cùng payload trả cùng kết quả; cùng ID khác payload phải từ chối.
Không tạo ID mới ở mỗi lần retry.

Đối với form: dùng revision/field patch theo hợp đồng; đối với thêm dòng: dùng
draft_line_id/command_id ổn định. Khoá nút chỉ giảm bấm lặp, không thay bất biến server.

| Bất biến | Nơi ép | Cách chứng minh |
|---|---|---|
| Không lẫn phòng khám/cơ sở | Identity, query scope, FK/constraint và RLS/ACL đúng vai | Hai clinic, đoán UUID, gọi trực tiếp object/file/job/RPC |
| RPC không tin clinic_id do browser tự gửi | Grant tối thiểu; server suy tenant từ identity hoặc xác minh membership trong SECURITY DEFINER | JWT clinic A gọi giờ/capacity clinic B qua PostgREST phải bị từ chối; role backend vẫn chạy |
| Không thu/hoàn vượt ý định | Ảnh chụp giá, transaction, khóa đúng thứ tự, receipt | Hai request đồng thời; timeout sau commit; tổng tiền và ledger cân |
| Phân bổ giảm bảo toàn tổng | Hàm thuần + đối chiếu tổng cycle/dòng | Property tests, hoán vị dòng, giảm toàn phần và dòng không được giảm |
| Tồn và giao không âm/trùng | Conditional SQL/lock, ledger nhập/xuất/điều chỉnh | Bán lô cuối đồng thời; retry giao; trả/hoàn không nhập nhằng |
| Chuyển trạng thái có căn cứ | State transition + version + người thực hiện | Reopen/undo/đổi ca; event đến trễ/đảo thứ tự |
| Lịch sử không mất khi sửa | Audit cùng transaction, version hoặc đính chính | Thất bại giữa giao dịch không có nửa dữ liệu/nửa vết |

Hoàn tác không phải quay ngược mọi thứ một cách mù quáng. Ví dụ, dịch vụ đã thực hiện
hoặc thuốc đã giao cần đường đính chính/đối soát giữ lịch sử; hoàn tác giao diện phải
nói rõ tác động nghiệp vụ thực tế.

## 5. Sự kiện, timer và thông báo

Giữ event/outbox trong Postgres, ghi cùng transaction nghiệp vụ; audit trail cần
giao dịch nguyên khối với thay đổi gốc. Phân biệt ba vòng đời: incident/công việc,
delivery thông báo, và acknowledgement của người nhận.

- Delivery bền có `pending/sent/retry/dead`, số lần, hẹn thử tiếp và mã lỗi.
- Dedupe theo incident/người/kênh; có quiet hours theo độ khẩn, gom thông báo thường.
- Retry timeout/429/5xx có backoff và budget; không bỏ việc vì lần gửi đầu thất bại.
- Worker chạy round-robin có batch/time budget; timer/cảnh báo không phải đợi consumer rỗng.
- Khi có nhiều worker, claim có attempt token/fencing hoặc consumer chứng minh idempotency;
  worker cũ không được ghi đè trạng thái của lần claim mới.
- SSE giúp nhận biết cần tải lại. Khi reconnect, client phải catch-up/read lại có version;
  không xem LISTEN/NOTIFY là lịch sử giao tin bền.

AI có thể tổng hợp và giúp điều tra, nhưng không thay thế các hợp đồng giao nhận này.

## 6. Bảo mật theo đường dữ liệu

Threat model tối thiểu gồm: người ngoài chưa đăng nhập; nhân viên khác phòng khám;
nhân viên cùng clinic nhưng thiếu capability; tài khoản bị thu hồi; người có quyền
máy quầy dùng chung; service/worker bị cấp quá quyền; nhà cung cấp bên ngoài.

Kiểm cả API, PostgREST/RPC, file, in/xuất, SSE, job nền, log và backup. RLS lọc hàng
không thay quyền cột; SECURITY DEFINER có thể vượt RLS; namespace localStorage không
phải mã hóa. Ngược lại, đừng coi server owner query là tự động sai nếu quyền đối tượng
đã được ép và kiểm thử ở API. Đánh giá cả chuỗi tin cậy.

Đề xuất một authority thông tin xác thực và chính sách thu hồi rõ. Mọi cửa đăng nhập
còn được hỗ trợ phải phản ánh reset/ban/revoke nhất quán. Dữ liệu hỗ trợ kỹ thuật cần
được che theo quyền; truy cập hỗ trợ đặc biệt có giới hạn thời gian và lưu dấu.

Hồ sơ nhân sự cũng cần phân lớp dữ liệu: danh bạ phục vụ lịch chỉ trả tên, vai trò và cơ sở; ngày sinh, CCCD, liên hệ cá nhân và giấy phép chỉ qua quyền đọc nhạy cảm có scope clinic. SEC-005 cho thấy DTO/projection dùng chung hiện làm danh sách thường trả các trường ấy cho identity cùng clinic. Ghi audit cho lần đọc/xuất có dữ liệu nhạy cảm và kiểm bằng tài khoản ít quyền.

Thay đổi danh tính đi qua GoTrue và Postgres phải có hợp đồng partial-failure. SEC-006 cho thấy activate đã commit nhưng unban GoTrue lỗi vẫn trả thành công. Dùng trạng thái pending/retry/reconcile có owner và receipt; chỉ báo hoàn tất khi hai phía xác nhận, hoặc hiển thị rõ trạng thái chưa hoàn tất.

Upload tệp lớn cần một quota chung theo byte thực và reservation tính cả lượt đang bay. Áp cùng trần tổng body/metadata trên CSKH, payment proof và cổng đối tác; SEC-003 cho thấy nhận file theo luồng không tự bảo vệ disk reserve khi header thiếu hoặc route nằm ngoài middleware. Từ chối và dọn file trước khi chạm ngưỡng, rồi thử concurrency và storage outage.

## 7. Đóng gói để bán

### Chọn mô hình triển khai có thể vận hành

| Phương án | Đổi lại điều gì | Khuyến nghị ở giai đoạn này |
|---|---|---|
| Triển khai riêng từng khách, cùng một bản phần mềm | Cách ly tốt, nhưng mỗi bản cần cập nhật/sao lưu/theo dõi | Phương án pilot đáng cân nhắc sau khi tự động hóa cài và nâng cấp |
| SaaS dùng chung ứng dụng/DB | Nâng một lần, nhưng tenant isolation, noisy-neighbor và restore riêng khó hơn | Chỉ mở khi test tenant và vận hành chứng minh được, không dựa riêng clinic_id |
| Mỗi khách một nhánh code | Vá nhanh nhưng bản phần mềm phân kỳ và tăng chi phí bảo trì | Không chọn làm mô hình bán; dùng cấu hình/feature có phiên bản |

Chưa chốt SaaS hay triển khai riêng bằng cảm tính. Dùng tiêu chí số khách dự kiến,
giá bán, yêu cầu dữ liệu, năng lực trực vận hành, chi phí trên khách và thời gian nâng cấp.
Không suy rằng triển khai riêng bỏ được kiểm quyền theo tenant.

### Danh tính qua nhiều phòng khám

Code hiện tại yêu cầu dashboard login tìm đúng một `clinic_membership` đang hoạt động; FastAPI có selector `X-Clinic-ID` và kiểm nó với membership của người đã xác thực. Màn `/chon-co-so` hiện chọn cơ sở trong một clinic, không phải chuyển clinic. Nếu bán cho chuỗi có nhân viên làm ở nhiều clinic, cần thiết kế chooser rõ ràng và buộc mỗi request/session theo clinic đã chọn; không tự chọn tenant đầu tiên. Nếu pilot chỉ một clinic độc lập, ghi giới hạn đó vào hợp đồng onboarding và kiểm lại khi mở rộng. Đây là ranh giới sản phẩm cần quyết định, không phải finding bảo mật mới trong lượt đọc này.

### Gói phát hành

Một release có image digest, Git SHA, migration manifest/checksum, phiên bản config,
hợp đồng backup, compatibility range và rollback/runbook. Cùng artifact đã thử được
đưa đến môi trường đích. Rollback image không mặc định rollback được schema/data.

### Onboarding và rời hệ thống

Cài phòng khám mới từ môi trường trắng với cấu hình clinic/cơ sở/phòng/dịch vụ/giá/
vai trò/mẫu in riêng; không cần mật khẩu mẫu hay ID thật của Dr4Women. Tách schema
migration khỏi thay danh mục/giá riêng từng khách. Mỗi import có preview, báo lỗi,
mã lô và đối soát. Có export dữ liệu và file theo quyền, tài liệu định dạng, kiểm
tính đầy đủ và quy trình retention/xóa theo chính sách được chốt.

### Phục hồi là tính năng của sản phẩm

Một recovery set phải chỉ rõ public DB, auth, media đã đồng bộ, file chờ đẩy,
config/keys cần cung cấp lại, migration ledger và phiên bản ứng dụng. Không nhét
secrets vào cùng báo cáo; chỉ ghi loại bí mật cần có và chủ sở hữu.

Restore drill phải kiểm đăng nhập, quyền, mở một lượt, đọc/in một kết quả/file,
đối soát tiền/tồn và worker bắt kịp. Ghi thời gian phục hồi và mốc dữ liệu cuối theo
từng loại; checksum DB hoặc health endpoint xanh chưa thay được hành trình này.

## 8. Alignment thành phép đo có thể dùng

Các chỉ số dưới đây là đề xuất, chưa có baseline đo trong đợt này. Thu thập trước,
cùng phòng khám chốt ngưỡng sau; không dùng ngay để xếp hạng nhân viên.

| Mục tiêu | Định nghĩa đo được | Chống hiểu sai |
|---|---|---|
| Reality rõ | Tỷ lệ trạng thái quan trọng có nguồn/phiên bản; tuổi dữ liệu trên từng bảng | Phân biệt suy luận với xác nhận; không tính chỉ có event là đã làm thật |
| Unknown ngắn | p50/p95 thời gian từ phát hiện thiếu/mâu thuẫn đến xác minh hoặc có người nhận | Unknown mới phát hiện không đồng nghĩa phần mềm vừa gây lỗi |
| Ownership rõ | Tỷ lệ việc chưa có người nhận; thời gian nhận bàn giao và đổi ca | Chuông đã gửi không tính là nhận việc |
| Phát hiện sớm | Lead time từ cảnh báo có ích đến hậu quả được ngăn/giảm | Đo cảnh báo sai/trùng và sự cố bị bỏ lọt |
| Ít gián đoạn đúng lúc | Lần báo chủ động/người/ca, tỷ lệ có hành động, escalation chưa nhận | Không tối ưu bằng im lặng mọi cảnh báo |
| Bệnh nhân ít chờ bất định | Thời gian không có bước tiếp theo/owner/hẹn cập nhật; số lần phải hỏi | Không suy chờ thực từ mốc nhân viên bấm muộn |
| Nhân viên bền vững | Việc quá hạn tồn qua ca, số bước nhập lặp và kiểm ngoài hệ thống | Ghi nhận cả tải công việc và mức thiếu nguồn lực |
| Quyết định có bằng chứng | Tỷ lệ báo cáo có nguồn/as_of/độ đầy đủ; số quyết định phải sửa vì dữ liệu sai | Lỗi API không được biến thành số 0 |
| Học từ lỗi | Tái diễn theo loại lỗi; tỷ lệ sự cố có invariant/test/quy trình ngăn lại | Số ticket đóng không thay được giảm tái diễn |

## 9. Vai trò AI sau khi nền dữ liệu đủ tin

AI đọc trong quyền được cấp, chỉ rõ nguồn/phiên bản/độ mới, nêu giả thuyết và bằng
chứng còn thiếu. Thử ở chế độ quan sát với bộ tình huống có đáp án kiểm chứng:
phát hiện việc rơi, giải thích mâu thuẫn, gom lỗi lặp. So sánh với truy vấn/rule thuần
về độ đúng, độ nhiễu, thời gian tiết kiệm và công kiểm lại.

AI không tự xác nhận đã chăm sóc, tự đổi tiền/quyền/thuốc hoặc đưa bản sửa lên prod.
Nếu sau này cho ghi, dùng đúng command API, capability hẹp, approval theo tác động,
receipt/audit và kill switch. Không cho agent sửa DB để né bất biến.

Mọi lời gọi model cũng là một hành động có chi phí và cần receipt vận hành. Trước khi
bật AI cho một clinic, app phải dùng cùng meter đã khởi tạo với DB pool; ngân sách ngày
cần được reserve nguyên tử để request đồng thời không cùng tiêu một phần dư. Sau provider
response, finalize theo request ID; lỗi finalize tạo trạng thái “chưa đối soát” có cảnh
báo và người nhận xử lý. Ops hiển thị mức đã xác nhận, đang reserve, thời điểm cập nhật
và các lần ghi thất bại. Khi meter không sẵn sàng, app chặn LLM hoặc chuyển sang fallback
rule-based được công bố. AI-004 là bằng chứng static cho thấy wiring hiện tại chưa đáp ứng
hợp đồng này; chưa có chứng cứ chi phí production bị vượt.

## 10. Các quyết định kiến trúc dự kiến

| ADR dự kiến | Đề xuất | Vì sao / khi xem lại |
|---|---|---|
| D01 — Ranh giới triển khai | Backend chia module, Postgres + worker hiện hữu | Giảm số hệ phải trực; xem lại khi có tải/đội/isolated failure cần tách |
| D02 — Sự thật và suy luận | Thêm provenance/knowledge status có chọn lọc | Chặn nhãn chắc chắn giả; cần thống nhất nghĩa nghiệp vụ cùng phòng khám |
| D03 — Command/receipt | Idempotency bền, payload hash và version | Mất response không thành ghi trùng; dùng implementation chung có kiểm chứng |
| D04 — Giao cảnh báo | Delivery bền tách incident và acknowledgement | Retry không làm spam và không mất thông báo |
| D05 — Release/recovery | Một artifact và recovery set có phiên bản | Test và deploy cùng vật thể; phục hồi cả quyền và file |
| D06 — Mô hình bán | Pilot một bản phần mềm cấu hình được; chọn isolation sau thử clinic thứ hai | Không duy trì fork từng khách; đo tổng chi phí vận hành trước mở rộng |
| D07 — Chuyển clinic | Quyết định một account/clinic hay một account/nhiều clinic; dashboard hiện yêu cầu đúng một active membership | Nếu hỗ trợ nhiều clinic, chooser và mọi request phải gắn tenant được chọn; nếu không, công khai giới hạn ở onboarding |

Đây chưa phải ADR đã được chấp thuận; khi triển khai, ghi từng quyết định chính thức
vào cấu trúc ADR hiện có của dự án, cùng bằng chứng và phương án đã loại.

## 11. Bổ sung từ các phép thử vòng 2

Năm trường hợp mới làm rõ một yêu cầu chung: **thiếu bằng chứng không được biến
thành bằng chứng hoàn tất; gửi lại không được biến thành ý định mới; bản cũ không
được ghi đè sự thật mới hơn.** Đây là thay đổi hợp đồng dữ liệu và lệnh, không cần
thêm một model AI mạnh hơn để chữa.

### 11.1 Scan và kết luận phủ định

`agent_giam_sat.phat_hien_sql` đang trả dictionary danh sách rồi `ap_dung` đóng mọi
khóa vắng mặt. AI-001 chứng minh danh sách bị cắt vẫn được coi là toàn bộ hiện trạng.
Đổi kiểu kết quả nội bộ thành một hợp đồng rõ:

```text
ObservationBatch {
  detector, detector_version, clinic_id, started_at, finished_at,
  scope, complete, next_cursor, source_watermark,
  observations: [{subject_id, evidence_ref, observed_at, assertion}]
}
```

`complete=false` chỉ cho phép thêm/cập nhật quan sát đã thấy. Đóng một nhận định cần
query xác minh chủ thể đó đã hết điều kiện, hoặc scan đầy đủ cùng phạm vi. Phân trang
cần thứ tự ổn định và xử lý đối tượng đổi trong lúc scan; không chỉ thêm ORDER BY
rồi vẫn đóng phần chưa đọc. Log “bị cắt” là tín hiệu chẩn đoán, không sửa được nghĩa
của thao tác đóng. Đóng do tắt rule phải giữ lý do `TAT`, không gộp vào đã hết vấn đề.

### 11.2 Receipt phải cùng giao dịch nghiệp vụ

Đề xuất tái dùng bảng/chốt hiện có nếu sửa được hợp đồng, không bắt buộc tạo bảng
mới. Khóa logic tối thiểu là `(clinic_id, actor_id, command_type, command_id)`;
payload hash giúp phát hiện sử dụng lại ID sai ý định. Kết quả cần một trong ba nghĩa:
đã từ chối chắc chắn, đã commit chắc chắn, hoặc chưa rõ và đang đối soát.

```text
BEGIN
  reserve command identity (unique, compare payload_hash)
  authorize target + lock expected revision
  apply domain changes + append audit/outbox
  persist command result / affected object IDs
COMMIT
return result
```

Khi crash trước COMMIT, retry làm lại an toàn; sau COMMIT, retry trả receipt. Không
để receipt được ghi bằng một kết nối/giao dịch khác sau khi service đã commit.
Không dựa riêng PROCESSING lease 5 phút để quyết định thao tác cũ chưa xảy ra.
Với tác động bên ngoài như gửi tin, lưu delivery trong giao dịch rồi worker gửi;
nếu nhà cung cấp không hỗ trợ dedupe, trạng thái chưa rõ cần reconciliation.

API gợi ý cho ý định mới: `POST /commands/{type}` nhận `command_id`,
`expected_revision`, `payload`; trả `command_id`, `status`, `result`,
`committed_at`, `new_revision`, `followup_status`. Đây là hợp đồng đề xuất,
không yêu cầu đổi ngay mọi endpoint sang một router chung. Có thể giữ URL hiện tại
và dùng cùng application command boundary bên trong.

Frontend tạo ID trước gửi đầu; retry giữ ID và payload. Lưu phiếu thành công nhưng
bàn giao tái khám thất bại phải trả “phiếu đã lưu, việc tái khám đang chờ xử lý”,
giữ pending task bền để retry/đối soát. Không bắt bác sĩ thay ngày rồi lưu lại để
đánh thức đồng bộ. Có thể dùng outbox hiện có thay vì tạo queue riêng.

### 11.3 Chuyển trạng thái và sửa trường

CLIN-005 cho thấy lệnh đổi lịch chỉ muốn sửa giờ/ghi chú nhưng ghi lại status cũ.
Tách patch của trường người dùng chủ đích sửa khỏi transition của lifecycle.
Nếu dùng optimistic concurrency, revision của aggregate phải tăng cho mọi thay đổi
có ảnh hưởng quyết định. Nếu dùng row lock, khóa trước khi đọc và quyết định, theo
cùng thứ tự ở mọi lệnh. State machine trong Python chỉ đủ khi SQL ép đúng điều kiện
của snapshot hoặc hàng đã được khóa. Cần kiểm cả hủy/hoàn tác/đổi bác sĩ trong cùng
ma trận, không giới hạn test vào hai check-in cạnh tranh giống hệt nhau.

### 11.4 Tiền hoàn là một phần của số tiền ảnh chụp

FIN-004 chứng minh `sum(round(part_i × price))` có thể khác
`round(sum(part_i) × price)`. Đối với mỗi dòng, dùng lượng và tiền lũy kế:

```text
remaining_quantity = original_quantity - reserved_or_completed_refund_quantity
remaining_money = collected_line_money - reserved_or_completed_refund_money
requested_money = cumulative_target_after_this_refund - money_already_reserved
```

Lần hoàn hết lượng nhận chính xác phần tiền còn lại. Mọi nhánh, kể cả không giảm,
cùng tuân cap tiền. Kho trả về vẫn là quy trình độc lập; hoàn tiền không tự chứng minh
thuốc còn dùng/bán lại được. Sửa bằng hợp đồng chung, tránh sao chép một nhánh xử lý
giảm giá sang một nhánh khác rồi bỏ sót nơi thứ ba.

### 11.5 Xung đột nội dung và thu hồi quyền

FE-005 cần trạng thái UI có cả `base`, `local`, `remote`, `remote_revision` khi 409.
Giữ local trong bộ nhớ; nếu cần lưu bền trên máy quầy phải áp retention/clear-on-logout
theo dữ liệu nhạy cảm, không tự chữa bằng localStorage không kiểm soát. Người dùng
chọn hợp nhất hoặc bỏ, server vẫn từ chối stale revision. Cần thử gõ tiếp khi request
đang bay và chuyển khách trước khi response cũ về.

SEC-002 cần ba trạng thái quyền tách biệt: chưa provision, provision hợp lệ có quyền,
provision hợp lệ không còn quyền. Chuyển từ có sang hết quyền là kết quả có chủ đích,
không được fallback legacy. Cơ chế cứu quyền quản trị cần tài khoản/quy trình khẩn
có phạm vi và lịch sử riêng. Giữ kiểm auth/membership trước và query clinic scope
ở mọi đường; không sửa fallback bằng cách khóa toàn bộ người chưa migrate.

## 12. Ma trận lỗi để nghiệm thu sản phẩm

| Tình huống | Người dùng phải thấy | Hệ thống phải giữ | Bằng chứng nghiệm thu |
|---|---|---|---|
| Response mất sau commit | Đang xác minh rồi đúng kết quả cũ | Một ý định, một receipt, một tác động | Kill process ở ranh giới commit/return rồi retry |
| Lưu phiếu được, tạo việc sau khám hỏng | Phiếu đã lưu; việc đang chờ, owner xử lý | Pending handoff không mất, retry có hạn | Inject lỗi trước/sau event, phục hồi không sửa ngày giả |
| Nhận kết quả ngoài đến muộn/đính chính | Bản mới, việc đọc lại và owner rõ | Acknowledgement gắn revision đúng | Kết quả v1→v2 không còn được coi v2 đã đọc |
| Read model bị cắt | Phần đang xem và khả năng còn thiếu | Không đóng việc từ tập không đầy đủ | 201 đối tượng, đổi thứ tự, nhiều trang |
| SSE/LISTEN rớt | Tuổi dữ liệu/đang nối lại; reload khả dụng | Poll/catch-up đọc lại truth từ API | Ngắt mỗi chặng riêng và quan sát bảng phục hồi |
| Hai người sửa ghi chú | Giữ chữ của mình + bản đồng nghiệp | Revision, lịch sử, không mất local | Browser conflict có nội dung hai bên |
| Thu hồi khối quyền cuối | Quyền mất đúng cửa | Không fallback cấp lại; cache hết hạn hữu hạn | Nhiều process và raw file/export/API |
| Restore từ backup | Tài khoản vào đúng quyền, file đọc được | ACL cột/hàm, DB/auth/media cùng recovery point | Nurse không đọc draft/settings, bác sĩ đọc hợp lệ |
| Gửi cảnh báo thất bại | Incident còn mở; delivery đang retry | Không coi gửi lỗi là đã thông báo/đã nhận | Timeout rồi phục hồi kênh, dedupe và escalation |
| Nâng cấp clinic thứ hai | Giá/quy trình riêng không đổi ngoài ý định | Schema và dữ liệu cấu hình tách | Snapshot cấu hình trước/sau migration |

## 13. Quy mô và cam kết: phải đo trước khi bán

Trong repo có nhận định quy mô khoảng 1 request/giây; đợt audit này chưa đo tải
production nên chỉ dùng làm bối cảnh, không dùng làm capacity benchmark. “Như
Facebook/YouTube” nên được chuyển thành kỷ luật về bằng chứng, release, phục hồi,
bảo mật và trải nghiệm. Kiến trúc phục vụ hàng tỷ người không phải yêu cầu mặc định
của phần mềm phòng khám.

Thử tải pilot nên mô phỏng toàn luồng: nhiều quầy check-in, bác sĩ autosave, thu tiền,
giao thuốc, SSE và worker đồng thời. Ghi p50/p95/p99, lỗi, pool wait, DB lock wait,
CPU/RAM/disk, backlog age và latency read-after-write. Tăng 1×→5×→10× tải đo được;
quyết định tối ưu từ điểm gãy, không lấy số request GET rỗng để hứa sức tải nghiệp vụ.

| Cam kết cần chốt với khách | SLI đề xuất | Chưa được hứa lúc này |
|---|---|---|
| Mở cửa và làm việc trong giờ khám | Tỷ lệ hành trình check-in/đọc phiếu/thu tiền thành công trong thời gian chấp nhận | Chưa có uptime/SLO đã đo |
| Dữ liệu không mất quá mức chấp nhận | Mốc recovery point cuối theo DB/auth/file và độ trễ đẩy file | Backup mỗi đêm không mặc nhiên bằng RPO 0 |
| Phục hồi trong thời gian chấp nhận | Thời gian từ bắt đầu sự cố đến người dùng làm được hành trình chuẩn | Một VPS chưa chứng minh high availability |
| Không bỏ sót việc | Tuổi pending handoff/delivery và thời gian không owner | API 200 không bảo đảm phối hợp xong |
| Bàn giao vận hành | Người khác dựng/nâng/restore bằng runbook, có đối soát | Không dựa vào trí nhớ người triển khai |

Ngưỡng thời gian, RPO/RTO, giờ hỗ trợ và trách nhiệm vận hành là quyết định kinh doanh
có chi phí. Báo cáo này không tự đặt thành SLA. Trước pilot, ghi ngưỡng dự kiến rõ,
chạy diễn tập, rồi mới đưa con số đã chứng minh vào hợp đồng.

## 14. Hợp đồng tài nguyên và vòng đời thông báo

CLIN-006 bổ sung yêu cầu: một incident có thể gom nhiều lần thay đổi, nhưng delivery
và acknowledgement phải biết phiên bản nào người nhận đã thấy. Khóa chống trùng là
`(subject, revision, recipient, purpose)` hoặc có cơ chế tương đương giữ revision mới.
Ẩn chuông v2 không được ẩn cả đính chính v3. Replay lại đúng event v3 vẫn chỉ tạo một
lần báo; gửi bản mới là một sự kiện mới cần được người chịu trách nhiệm nhận biết.
Thông báo khác với xác nhận đã đọc chuyên môn; chưa được coi “đã mở” là đã xử trí.

Đường upload đã có streaming, sniff loại tệp, đường dẫn UUID, no-store/nosniff và
mạch ngắt kho riêng. Giữ các cơ chế này. SEC-003 cho thấy cần thêm budget theo byte
thực trong receiver, kể cả request không khai Content-Length. Giữ dự phòng ổ VPS
trong mọi thời điểm, không đợi nhận xong mới từ chối. Hạn mức tenant/tệp là cấu hình
kinh doanh; bảo vệ tài nguyên host là bất biến kỹ thuật, hai quyết định tách nhau.
Kiểm cả nhiều upload hợp lệ cùng lúc, pending file chưa đẩy sang CFS và dọn tệp dở.

## 15. Đúng định danh thuốc là bất biến, độc lập với cách thu và quản lý kho

CLIN-007 chỉ ra chốt đúng thuốc phải đi cùng mọi đường giao: có phân lô, không phân
lô, lần thu cũ và gán lô sau. Kiểm tối thiểu `clinic + cơ sở + drug_catalog_id + đơn vị
+ hạn + số lượng`, theo dữ liệu đã khóa. Cùng đơn vị hoặc cùng giá không thay được
cùng thuốc. Quy đổi đơn vị chỉ dùng bản quy đổi đã xác nhận; thay thuốc là một quyết
định riêng cần người có quyền, lý do và vết đính chính.

Giữ phân biệt kê, xác định thuốc kho, mua, bán và giao. Những bước chưa biết chính
xác lô vẫn biểu diễn chưa gán lô, không tự biến thành đã đối soát kho. Khi cho phép
giao chưa gán lô, hệ thống phải có danh sách chờ đối soát có owner và tuổi chờ; nới
quy trình kho không được nới bất biến thuốc nào đã giao cho dòng đơn nào.

## 16. Bản phát hành và bản in đều cần danh tính có thể kiểm lại

Mỗi release cần Git SHA, digest image, migration IDs/checksums, lockfile, SBOM và
cấu hình nghiệp vụ đã chấp thuận. Scan dependency theo đúng image phát hành, tách
runtime/dev và lưu kết luận reachability, mitigation, owner cùng hạn xử lý. Quét
một lockfile không thay scan Python/OS image; phiên bản package không tự chứng minh
toàn bundle biên dịch khớp source. Quy trình nâng phải chạy lại các hành trình ảnh,
file, đăng nhập và in, có phương án phục hồi theo tương thích schema.

Đường in hiện đã có nhãn bản nháp, lấy bản chính thức và không tính in là bác sĩ đã
đọc. Giữ các điểm đó. Để tài liệu đã phát ra kiểm lại được, bổ sung contract in chứa
ID phiếu/kết quả, revision chính thức, phiên bản mẫu, thời điểm snapshot và thời điểm
xuất. Bản đính chính có liên hệ với bản bị thay; tên người nhập khác người đứng tên
chuyên môn, không gọi chỗ ký tay là chữ ký số đã xác thực.

Nếu cho in lại bản cũ, phải ghi rõ bản cũ/as-of. Nếu yêu cầu in bản hiện hành, kiểm
revision ngay trước khi xuất; không dựa trang đã mở từ đầu ca. Cần chọn chính sách
snapshot cho file kèm và thông tin đứng tên khi lịch/nhân sự thay đổi. Đây là đề xuất
provenance sản phẩm; chưa có phép thử chứng minh toàn bộ bản in hiện tại sai.

## 17. Gói sản phẩm đầu tiên và giới hạn cam kết

Đề xuất pilot có quản lý cho một clinic độc lập, phạm vi tối thiểu là lịch–lượt–kết
quả–thuốc/tiền–việc sau khám, cấu hình cơ sở/người/quyền/catalog riêng. Chỉ chọn sau
khi đóng các cổng lỗi và phục hồi; không dùng clinic thứ hai làm môi trường kiểm lỗi
nguy hiểm. Demo dùng dữ liệu giả và một ca thường cùng các ngoại lệ quan trọng.

| Mô hình | Điều phải có trước khi chọn | Đánh đổi vận hành |
|---|---|---|
| Managed deployment riêng từng clinic | Dựng/nâng/backup tự lặp lại, secrets riêng, chi phí và owner rõ | Cách ly tốt hơn theo deployment; tốn vận hành mỗi khách |
| SaaS chung | Tenant isolation đủ mọi bề mặt, quota/noisy-neighbor, migration cấu hình khách, hỗ trợ có scope | Chia sẻ tài nguyên; blast radius và kiểm chứng phức tạp hơn |
| Khách tự vận hành | Runbook đủ, người khác restore/nâng được, hỗ trợ/phiên bản tương thích rõ | Ít kiểm soát môi trường; yêu cầu đóng gói và chẩn đoán cao hơn |

Không chốt SaaS chung từ việc schema đã có clinic_id. Tách schema evolution khỏi
catalog mẫu của Dr4Women, tạo bộ cấu hình demo và bootstrap có target clinic rõ.
Phép thử DB-004 là căn cứ ưu tiên việc này. Bảng giá, mô hình bán và SLA cần quyết
định kinh doanh sau khi có số chi phí pilot; không suy ra từ repo.

AI chỉ đọc/tóm tắt/đề xuất ở vòng đầu, phải có scope, nguồn chứng cứ, phiên bản input,
model/prompt và cơ chế đánh giá. Khi tắt AI, lõi lịch/khám/thu/giao vẫn khởi động và
phục vụ được. Cần kiểm thêm boot coupling của checkpointer tùy chọn; chưa có kết
luận cấu hình AI hiện tại làm production không khởi động.


## 18. Hợp đồng bổ sung từ vòng đọc v0.17

### Quyền đọc hồ sơ phải gắn với nhân viên và lượt khám

Endpoint hồ sơ chia sẻ không được coi hai UUID do caller gửi là bằng chứng cùng một bệnh nhân hoặc quyền đọc. Kiểm capability lâm sàng ở backend trước khi mở dữ liệu; nối `viewing_patient_id` với visit hiện hành được phân quyền từ server; đánh giá consent riêng giữa người bệnh nguồn và người bệnh đích. Quyền xem hồ sơ, consent bệnh nhân và mục đích điều trị là ba quyết định có thể liên quan nhưng không thay thế nhau. Ma trận quyền phải kiểm cả đường đọc tắt, export, in và tải xuống.

### Mọi giới hạn truy vấn phải mang trạng thái đầy đủ đến người dùng

`LIMIT` bảo vệ tài nguyên không thể biến thành “dữ liệu đầy đủ” ở màn hình hoặc file xuất. List API cần cursor ổn định, tổng số hoặc `has_more`; báo cáo đối soát cần một lựa chọn rõ: truy vấn đủ bằng aggregate/stream, hoặc trả trạng thái `incomplete` kèm số dòng/giới hạn và không cho chốt đối soát. Cảnh báo log-only là không đủ vì người quyết định không nhìn thấy log. Áp hợp đồng này cho hàng đợi nhà thuốc, lịch sử, tư vấn, payment/refund, thuốc theo khách và mọi export.

### MPI là một quy trình có người chịu trách nhiệm

Phát hiện candidate chỉ tạo tín hiệu. Sản phẩm phải có hàng chờ reviewer, lý do khớp, người nhận việc và hạn xử lý; quyết định reject/merge cần ghi actor, thời điểm, bằng chứng và tác động đến visit/thuốc/tiền/form. Merge phải giao dịch nguyên tử và có đường phục hồi. Không auto-merge chỉ dựa vào score.

### Tenant mới phải dựng được từ template có phiên bản

Onboarding cần một lệnh/flow idempotent nhận rõ `clinic_id`, gắn catalogue/workflow template được version hóa, tạo location, role và membership, áp ACL, rồi chạy smoke test. Dữ liệu template mặc định phải tách khỏi dữ liệu riêng khách hàng hiện hữu. Cấp tài khoản không được chọn tenant bằng `LIMIT 1`; thao tác phải có clinic đích tường minh và kiểm tra quyền operator. Gói bán chỉ đạt khi clinic hai cài mới, nâng cấp, chạy một lượt khám và tách biệt dữ liệu mà không sửa code.

### Restore chỉ thành công khi schema, ledger và quyền cùng nhất quán

Dump public-only, GoTrue/auth, pending files, kho file ngoài máy, cấu hình được bảo vệ và migration ledger là các phần của một recovery set hoặc các dependency được kiểm chứng. `restore complete` phải khác `ready for traffic`: sau nạp dữ liệu cần xác minh schema/ledger, reconcile ACL từ khai báo versioned, kiểm tenant, login, file và workflow mẫu. Sau đó chạy một migration kế tiếp như bằng chứng nâng cấp tiếp tục được. Mọi bước thực hành trên disposable target; không sửa ledger thủ công chỉ để làm xanh kiểm tra.


## 19. Hợp đồng bổ sung từ vòng đọc v0.18

### Quyền đọc phải gắn với đúng đối tượng được phân

Capability `clinical.*` chỉ chứng minh người dùng được làm loại công việc lâm sàng; nó không chứng minh họ được xem mọi bệnh nhân. Với TKYK, áp patient-assignment guard ở mọi API đọc form, lịch sử, print, hồ sơ ghép và export. Visit, appointment, patient phải được nối với nhau trên server; nếu caller gửi cặp không khớp thì từ chối trước khi lấy form_data. Kiểm negative tests bằng hai bệnh nhân cùng clinic.

### Ngữ cảnh bệnh nhân là một phần của state

Mọi history/form/feedback component cần ghi patient ID nguồn của state. Khi selection đổi, dữ liệu chỉ được render nếu source ID khớp selection hiện tại. Loading, empty, stale và error là các trạng thái riêng. Mọi nút mở lại lượt cũ phải xác thực lại visit→patient thay vì dùng patient ID từ closure hiện tại. FE-007 là lỗi gắn sai ngữ cảnh; chưa có bằng chứng thao tác ghi vào nhầm hồ sơ.

### Worklist lâm sàng phải fail visibly

Nếu một endpoint riêng cung cấp queue việc bác sĩ quyết bị lỗi, panel phải hiện error + last successful read + retry. Endpoint khác trả 200 không chứng minh queue này đã cập nhật. FE-008 giữ công việc phía backend nhưng có thể làm người dùng không biết việc đang chờ. Theo dõi tuổi việc chưa được người chịu trách nhiệm nhận.

### Lịch, dịch vụ và lượt khám cần cùng phiên bản

Mọi đổi dịch vụ sau check-in phải đi qua một use case có state guard, cập nhật appointment và visit nguyên tử, lưu delta trước/sau và chốt phiếu sẽ mở. Không để reschedule thông thường đổi catalog của lịch nhưng giữ catalog của visit. Các lần đổi giờ, bác sĩ, dịch vụ, kênh và nguồn giới thiệu cần audit delta riêng thay vì chỉ lưu sự kiện đổi thời gian.

### Timer thay thế cần generation fencing

Lịch tái khám đổi trong lúc timer cũ đã được claim phải vẫn tạo được timer mới. Dedupe key nên gồm generation hoặc có thao tác nguyên tử hủy/thay; handler cũ chỉ được hoàn tất đúng generation. Health check phải phát hiện việc CHO_GOI quá hạn nhưng thiếu timer/chuông. INF-009 là interleaving tĩnh, cần DB fault test trước khi kết luận tần suất.


## 12. Bổ sung từ checkpoint v0.19

- **Receipt phải bao trọn route có side-effect, không chỉ command đã biết:** INF-007 nay có cả CSKH và refund partial. Giao dịch refund commit ở service rồi receipt mới save; crash boundary làm lại cùng nửa refund. Dùng một command ID ổn định, receipt/domain cùng transaction hoặc một durable reconciliation contract; kiểm mọi router riêng.
- **Quyền phải hội tụ về desired state:** SEC-012 cho thấy assignment kỹ năng và các lego không có một đơn vị nguyên tử; `already` không đủ bảo đảm effective grants đúng. Mọi đường retry/revoke cần đọc nguồn cấp quyền còn hiệu lực và reconcile có dấu vết.
- **Vòng đời thuốc trả phải phân biệt đã thu, đã void, đã hoàn và hàng vật lý đã nhận:** PHAR-001 không cho suy `VOIDED` nghĩa là chưa từng thu. Tài chính và kho cần một quy trình trả/đổi có thể theo dõi cả khi receipt gốc bị void; không để workaround GIU_LAI thành khoản treo không owner.
- **Bàn giao đối tác cần hạn + người theo dõi theo loại dịch vụ:** CLIN-012 chưa được coi là lỗi nếu clinic không yêu cầu SLA cho mẫu nội bộ gửi đối tác. Nếu có, timer phải bắt đầu từ mốc bàn giao mẫu, không từ nhãn node nội bộ/bên ngoài đơn lẻ.


## 13. Bổ sung từ checkpoint v0.20

- **Tối thiểu hóa dữ liệu ngay ở sự kiện nguồn:** event log lưu mã hồ sơ, actor, thời điểm và field names đã đổi; tránh nhân bản CCCD/SĐT nguyên vẹn vào kho audit rộng quyền. Có đường migration/retention để xử lý lịch sử theo chính sách được duyệt.
- **Phân biệt “chưa cấu hình” với “đã cấu hình rỗng”:** lưu trạng thái cấu hình roster tường minh; khi đã cấu hình mà không còn quyền/vị trí nào thì từ chối. Mọi đổi phạm vi phải có actor, lý do, diff trước/sau và thời gian.
- **Điều phối và cấu hình dùng một phiên bản nhất quán:** transaction assignment ghi nhận version cấu hình và chỉ commit khi eligibility còn đúng tại version đó; cấu hình đổi làm phát hiện các assignment đang hoạt động bị ảnh hưởng, gắn owner và tạo việc xử lý.
- **Lệnh thao tác có danh tính mục tiêu và điều kiện phiên bản:** undo gắn attempt_id và expected execution revision; replay/stale request trả conflict thay vì tác động bản ghi mới nhất. Snapshot attempt phải lấy revision sau update.
- **PATCH là patch thật:** các trường cài đặt hiển thị riêng biệt, không có default ghi đè trường bị bỏ khỏi body; privacy-sensitive config có test regression và kiểm soát quyền.
- **Validation nhất quán xuyên luồng:** create/update/lookup/duplicate cùng dùng một hợp đồng chuẩn hóa số điện thoại và kiểm tra location cùng clinic/trạng thái active.


## 14. Bổ sung hợp đồng từ checkpoint v0.21

### Trạng thái “đã có kết quả” phải nói đúng kết quả còn hiệu lực

Tách ít nhất hai mốc: đối tác đã gửi/trả một lần và hiện còn bản kết quả hiệu lực được bác sĩ xem. Thu hồi bản cuối phải tạo một trạng thái cần xử lý, owner và hạn; không để marker cũ làm H7 kết thúc im lặng. Nếu quy trình yêu cầu thao tác Hoàn tác riêng, UI phải mở việc đó ngay và ghi ai chịu trách nhiệm.

### Mọi loại hồ sơ dùng cùng hợp đồng FINALIZED

Clinical shell là nguồn quyết định status/lock/amendment. Module form không được tự mặc định editable khi thiếu mode. Ghi sau FINALIZED cần một policy duy nhất: từ chối hoặc tạo amendment có reason/actor/approval, revision có thể truy lại và bản in giữ đúng release.

### Bản được duyệt và bản mới nhất là hai khái niệm khác nhau

Lưu revision không tự release. API in/gửi phải đọc release của đúng version hiện hành; khi có correction, cổng phát hành chọn rõ version đang hiệu lực và thông báo thu hồi bản trước. Nếu chưa có flow release, UI phải ghi nháp và không trình bày như bản chính thức.

### Worklist không được biến trần kỹ thuật thành số tổng

Mọi danh sách có cap phải có cursor/page, total hoặc `has_more`, timestamp và tuổi dữ liệu. Dashboard phân biệt đủ dữ liệu, đang tải tiếp, lỗi và rỗng; count chỉ báo số đang hiển thị khi chưa biết tổng. Áp điều kiện này cho CSKH liệu trình, tiền, thuốc, bệnh nhân và export.

### Tenant context phải được chọn tường minh và xác minh server-side

Clinic switcher (nếu target market nhiều clinic) đứng riêng với location picker. Token xác định người; membership xác định clinic+role; selector chỉ chọn ngữ cảnh và backend kiểm membership active mỗi request. Khi switch phải reset patient cache, query cache, realtime subscription và các request đang bay để không trộn dữ liệu hai clinic.

### Dead-letter là một việc có owner, không phải một trạng thái trong DB

POS/worker failure cần queue có người nhận, hạn, cảnh báo, lý do, retry/reconcile an toàn và audit. Không cho replay thủ công nếu idempotency/effect ngoài hệ thống chưa rõ. Readiness/health phải nhìn được DEAD và khoảng backlog; integration để opt-in cho tới khi có runbook, test adapter và recovery drill.


## 21. Bổ sung từ vòng đọc v0.38 — audit phải tìm được và đi cùng mutation

- **Một read model có phạm vi rõ:** trang nhật ký vận hành có thể hợp nhất các nguồn, nhưng chỉ chiếu loại sự kiện đã được duyệt cho vai đó. Security event như cấp/thu capability cần actor, người nhận, quyền, scope và thời điểm; không trả nguyên payload của `domain_event` lâm sàng. Bộ lọc clinic luôn lấy từ identity đã xác thực.
- **Mutation và audit là một kết quả nguyên tử:** cấu hình tầng, quyền và các thay đổi có ý nghĩa vận hành ghi hiện trạng cùng audit event trên một transaction; nếu phải ghi qua outbox thì phải có owner, trạng thái chờ, retry và alert. API không được trả lỗi mơ hồ sau khi thay đổi đã commit mà không để lại dấu vết.
- **Lỗi đọc phải giữ trạng thái lỗi:** BFF không biến `null`/non-2xx thành success-shaped HTTP 200. Consumer validate discriminant và dữ liệu trước render; màn hình cho biết dữ liệu chưa tải thay vì ném lỗi hoặc đoán trạng thái.

Round17 xác nhận các gap này bằng source trace; fault-injection, API/UI tests và production behavior vẫn cần kiểm tra trước khi chốt nghiệm thu.

## 22. Bổ sung từ vòng đọc v0.39 — trạng thái lỗi phải dẫn tới hành động đúng

- **Đính chính sau khi đã gửi kết quả:** thu hồi chỉ đổi trạng thái và cập nhật timeline. Nếu người dùng đã ghi nhận gửi, tạo công việc liên hệ lại có owner, hạn, kết quả xác nhận và liên kết bản thay thế; hoặc buộc chuyển qua một quy trình đính chính riêng. `gui_luc` là xác nhận thao tác thủ công, không được hiểu như receipt của kênh gửi.
- **Dead-letter phải xử lý được theo dòng:** role alert và health counter giúp phát hiện, nhưng Ops cần lọc từng event/timer, xem lỗi đã làm sạch, biết aggregate/tác vụ bị chặn, giao owner, acknowledge và retry an toàn. Retry phải giữ fencing/idempotency và audit; projection replay vẫn là thao tác khác.
- **Tender breakdown phải bảo toàn qua hoàn tiền:** mặc định lấy phần tiền theo từng hình thức hiệu lực của cycle và tạo các refund parts tương ứng; một lựa chọn override phải được người dùng xác nhận và lưu lý do. Số các phần hoàn cần bằng số hoàn tổng.

Đây là tiêu chí đích từ static review. Cần kiểm thử DB/API/UI cô lập và chốt policy đính chính trước khi triển khai. Không có bằng chứng về giao dịch lỗi hoặc sự cố bệnh nhân trong production.



## 23. Bổ sung từ vòng đọc v0.40 — trạng thái phải phân biệt được và mutation phải có điều kiện

- **Worklist:** lỗi tải là trạng thái `error` có retry, không được ánh xạ thành danh sách rỗng. Danh sách có cap phải trả cursor/`has_more` hoặc nói rõ số đang hiển thị; badge không giả làm tổng.
- **Clinical release:** API print phải trả trạng thái draft/final/released và revision. Bản nháp/đang autosave cần nhãn rõ và không được giống bản chính thức; bản in chỉ lấy revision được release theo policy.
- **Form binding:** dịch vụ chỉ gợi ý/cho mở form có mapping hợp lệ. “Không có gợi ý” không được hiểu thành “mọi form đều hợp dịch vụ”. Quy tắc mapping cần được lưu và kiểm tra ở backend, không chỉ ở UI.
- **Autosave xung đột:** gửi revision/base version; backend dùng compare-and-swap hoặc trả 409 cùng dữ liệu mới nhất để client cho người dùng hợp nhất. Không âm thầm ghi đè thay đổi cùng trường.
- **Quyền theo patient và clinic:** mỗi endpoint bắt đầu bằng capability, clinic membership, role, assignment/location khi policy yêu cầu. Bảng nhạy cảm dùng RLS có cùng contract; field projection tối thiểu vẫn giữ nhưng không thay thế authorization.
- **Notification:** mỗi recipient có delivery attempt/idempotency riêng; một recipient lỗi không replay các recipient đã thành công. Timeout bên Zalo phải lưu `UNKNOWN` cùng mã yêu cầu/thời điểm để reconcile trước retry. Dynamic text cần escape theo đúng Telegram HTML.
- **Roster:** chỉ `APPROVED` được cấp authority/capacity. Chuyển trạng thái cần guard trạng thái nguồn, reconciliation lịch hẹn sau reject/remove và audit. Đường service không nên giữ một pool connection rồi chờ lấy thêm connection để hoàn tất cùng mutation.

Đây là hướng thiết kế và acceptance cần xác minh bằng test tổng hợp; không tự động hàm ý thay đổi code đã thực hiện.

## 24. Bổ sung v0.41 — ghi có revision, kết quả stale có tên, list có ranh giới

- **Clinical aggregate writes:** mọi thao tác merge `findings`/JSONB phải khóa record trước khi đọc, dùng revision compare-and-swap, hoặc patch key nguyên tử. Một request không được ghi toàn bộ snapshot cũ rồi trả 2xx như thể dữ liệu mới nhất đã được giữ. Revision và actor cần đi cùng audit event.
- **Recall outcomes:** status của hàng đợi không thay cho outcome của cuộc gọi. API nên phân biệt ghi mới, retry đã ghi, và việc đã bị lịch hẹn thay thế; UI cần hiện đúng kết quả đó thay vì chỉ refresh khi HTTP 2xx. Nếu lưu cuộc gọi sau khi hàng đợi đóng, dùng attempt/event idempotent tách khỏi trạng thái cần gọi.
- **Personal reminders and worklists:** giới hạn SQL phải đi kèm cursor/`has_more` hoặc copy nêu rõ danh sách đang được cắt. Timer bền và danh sách nhìn thấy là hai trạng thái riêng; không để log cảnh báo thay thế tín hiệu cho nhân viên.
- **Roster projection:** cùng một trạng thái được dùng nhất quán ở permission, capacity, queue room/node. Chỉ `APPROVED` mới là nguồn hiệu lực; thiếu vị trí hợp lệ phải giữ Unknown/explicit visit state, không suy ra từ PENDING.
- **Dormant interface:** không bật `SonoBiometry` đến khi contract GET/POST của UI, BFF và FastAPI trỏ tới cùng một model/route, có kiểm tra component caller và concurrent-save test. Script thao tác dữ liệu cũ cần trạng thái retired/active rõ trên runbook.

Đây là nguyên tắc đích và tiêu chí nghiệm thu đề xuất; chưa thay đổi code.


## 25. Bổ sung v0.42 — một ranh quyền dữ liệu bệnh nhân, kể cả PostgREST

- **Mặc định API-owned cho hồ sơ bệnh nhân:** danh sách/chi tiết patient đi qua FastAPI với capability, clinic, location/object scope và DTO tối thiểu. Policy RLS tenant-only không được xem như authorization role-complete. Nếu direct PostgREST được chủ ý giữ, cần capability-aware policy/RPC hoặc projection riêng; cấp table SELECT cho authenticated không tự giới hạn cột.
- **Realtime không phải lý do mở cả bảng:** phát event/projection chỉ mang ID nghiệp vụ tối thiểu; client lấy chi tiết qua API đã guard. Kiểm tra lại yêu cầu SELECT của Realtime trước khi chọn mô hình, rồi test subscriptions cùng các HTTP reads.
- **Freshness là một phần của dữ liệu:** UI giữ last-known-good để không mất công việc nhưng phải gắn stale, thời điểm tải thành công cuối, lý do lỗi và thao tác thử lại. Trạng thái SSE connected không chứng minh từng panel đã refresh thành công.
- **List contract chuẩn:** mọi API có LIMIT trả `has_more`/cursor hoặc nêu rõ cửa sổ chọn được; màn phản hồi thuốc phải cho tìm/chọn lượt cũ mà không giả vờ 20 lượt là đầy đủ.
- **Finance event time:** refund lưu riêng requested_at và completed_at. Báo cáo theo chính sách kế toán đã chốt, phân biệt khoản pending với tiền thực chuyển; lịch sử giao dịch và sổ nợ phải giải thích cùng một mốc thời gian.

Đây là thiết kế đích. Chưa thay đổi app; mọi quyền cần kiểm bằng role fixture và request PostgREST thực trên stack dùng một lần.


## 26. Bổ sung v0.51 — command rõ danh tính, nháp có revision, write có thể đối soát

- **Hẹn gọi lại là một command có side effect:** client tạo `operation_id` một lần cho ý định của người trực; retries giữ cùng id. Server ghi receipt và hàng hẹn trong một transaction hoặc có domain dedupe bền. Notification dựa trên cùng resource ID/outbox, không tạo một lần nữa khi retry. Cùng id với body khác phải trả conflict.
- **Phiếu kiểm kê nháp có revision:** mỗi lần lưu yêu cầu `expected_revision`; transaction khóa phiếu, so revision rồi cập nhật toàn bộ patch và tăng version. Editor cũ nhận 409 cùng snapshot mới, không ghi đè lặng lẽ. Chốt ghi lại revision nguồn để người rà biết số liệu nào tạo ra mismatch.
- **Không biến mất trạng thái ghi chưa rõ:** timeout sau gửi là `UNKNOWN`, không phải `FAILED`/“chưa lưu”. Client đối soát command receipt/domain status bằng `operation_id`, giữ bản nháp và chỉ mở lệnh mới sau khi xác minh kết quả lệnh trước.
- **Freshness theo từng read model:** mỗi bảng giữ `as_of`/revision gần nhất, `stale_reason` và retry; kết nối SSE/poll còn mở không được coi là bằng chứng dữ liệu đã tải mới.

Các cổng này nối trực tiếp CLIN-044, PHAR-003, PHAR-004 và FE-002. Chưa sửa code; acceptance cần concurrency/fault-injection tests trên DB và UI dùng dữ liệu tổng hợp.
