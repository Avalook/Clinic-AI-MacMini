# Round 10 — triage các lát source

Ngày 19/10/2026. Baseline là snapshot nội dung exact-main tại `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Snapshot không có `.git`; SHA commit lấy từ pin đã lưu trong STATE/manifest, còn SHA-256 từng file được tính trực tiếp trên snapshot. Không kết nối production/VPS/DB, không đọc secrets/PHI và không sửa source ứng dụng hoặc migration.

## Quyết định

| Candidate | Kết quả | Lý do |
|---|---|---|
| API identity/authorization | Không thêm finding | Rà 619 route decorator cùng dependency identity, membership, capability và location. Không xác nhận được đường truy cập mới ngoài các vấn đề đã có trong ledger. Đây là kết quả của lát đã rà, không phải kết luận toàn API an toàn. |
| Dashboard session/context | Không thêm finding | Các điểm về draft localStorage sau logout và dashboard nhiều clinic đã được ghi ở FE-001/FE-009; xác thực route liên quan SEC-009. Không lập bản trùng. |
| CAND-OPS-001 | Thêm **INF-019**, HIGH, `confirmed_static` | Heartbeat và trạng thái backup local thành công được phát trước uploader Viettel CFS; systemd bỏ qua mã lỗi upload; Ops không suy giảm trạng thái theo kết quả CFS. Đây là sai lệch tín hiệu offsite có thể che việc thiếu bản sao ngoài VPS. Có liên quan INF-001/INF-006 nhưng khác phạm vi: candidate này nói về heartbeat/status/UI khi lệnh CFS lỗi. Không khẳng định CFS hiện đang hỏng hoặc backup đã mất. |
| CAND-CI-001 | Thêm **CI-001**, MEDIUM, `confirmed_static` | Nhánh PID cũ đã chết chỉ thông báo rồi tiếp tục dùng thư mục khóa cũ; nhiều lượt CI có thể cùng ghi PID và chạy đồng thời. Chúng dùng chung `.ci-may` logs/result files và tài nguyên test. Đây là race path tĩnh; chưa chạy concurrency test, không khẳng định đã tạo false-green. |
| CAND-CI-002 | Giữ ngoài risk register, LOW | Test Excel không nằm trong danh sách test frontend tường minh. Chưa chứng minh hợp đồng release yêu cầu test này hoặc code path không được kiểm tra ở nơi khác; không tái hiện release false-green. Bằng chứng và câu hỏi tiếp theo được lưu trong `STATE.json` → `held_observations`. |
| INF-014 | Dedup | Agent CI xác nhận duplicate với quan sát untracked-file false-green đã có; không thêm lại. |

## Xác minh evidence

Các coverage JSON của bốn lát round10 có tổng 67 file path. Mỗi file xuất hiện trong các coverage được so SHA-256 trực tiếp với snapshot; không có thiếu file hoặc sai hash, và các path đã có trong `MAIN-PHAM-VI.json` cũng khớp manifest. Evidence line/hash của INF-019 và CI-001 được kiểm lại trên cùng snapshot trước khi gộp; integration script lưu trích đoạn chính xác vào `main_validation.evidence`.

Tập CI dùng metadata `snapshot.sha` (commit SHA được cấp trong task) thay vì `source.repository_sha`; integration script đã hỗ trợ hai schema này và nhiều dạng status coverage. Các mức coverage chỉ được nâng khi evidence ghi full/read hoặc trace cụ thể; scan/inventory không được tính thành đọc trọn.

## Việc còn mở

- Chạy test cô lập cho khóa CI cũ: tạo trạng thái PID chết có kiểm soát, khởi chạy đồng thời và kiểm tra loại trừ lẫn nhau, log và mã kết quả.
- Trên môi trường disposable, cho backup local thành công nhưng CFS unmounted/upload/checksum lỗi; xác nhận heartbeat/offsite warning bền và chỉ trở xanh sau receipt checksum khớp.
- Tiếp tục các source path chưa được đọc trọn; bốn lát round10 hoàn thành không đồng nghĩa full source audit hoàn tất.
- Rebuild/validate HTML rồi tái tạo và kiểm gói ZIP sau cập nhật trạng thái.

