# Tổng hợp / chất lượng bằng chứng — checkpoint

## Đã làm

- Đọc quy tắc, bản đồ và trạng thái gần nhất; truy vết conftest, cơ chế gắn marker và fixture siết quyền.
- Quét AST 527 file Python trong src/tests; đếm 3.970 hàm test_ (không phải số test thu thập thực tế do parameterization).
- Không biến 51 tín hiệu thiếu assert cục bộ thành lỗi: helper có thể đã assert.
- Tạo baseline hash và phạm vi 2.515 file; các binary/chỗ nhạy cảm chỉ có metadata.
- Khởi chạy 3 file test chọn lọc qua test-nhanh.sh; kết quả đang chờ.

## Điểm tốt đã đọc

- conftest.py:143–157 ép MO_QUYEN_TAM_THOI=0 khi kiểm quyền, tránh test xanh giả do bật cửa tạm.
- Có source contract tests cho HTTP tools dev-only và identity; tenant-scope scanner có test OR escaping.
- Test DB dùng cơ chế DB tạm theo quy tắc repo; không cần ghi DB chung hoặc prod.

## Hạn chế

- AST scan không chứng minh test phản ánh nghiệp vụ đúng, không cho coverage thực thi và không thay E2E.
- Tài liệu lịch sử được inventoried, chưa đọc toàn bộ. Báo cáo 02/10 chỉ dùng làm đầu mối cần kiểm lại.
- Chưa xác minh SHA/config/metrics thực tế prod; không chứng nhận tuân thủ hay khả năng chịu tải.

## Tiếp tục

1. Lưu kết quả selected tests vào TEST-RUNS.json.
2. Tích hợp và đối chiếu các khối; khử trùng lặp, kiểm hash, review độc lập finding nghiêm trọng.
3. Viết thiết kế đích, tiêu chí thương mại hóa và HTML; kiểm cấu trúc, desktop/mobile, filter/link.
4. Cập nhật STATE và gói bàn giao; công khai mọi phần mới dừng ở scan/inventory.

## Root checkpoint 2026-10-19T17:46:43.192198+07:00

Khối chưa hoàn tất. Nội dung agent ban đầu là baseline543b9787+WIP; ưu tiên PHAT-HIEN.json/main_validation cho kết luận mới.
Tiếp theo: TIEP-TUC.md và MAIN-PHAM-VI.json. Không tự nâng scan thành đọc sâu.

## v0.23 — agent acknowledgements

AI-002: task wrapper chỉ có clinic_id rồi xác nhận đã ghi nhận. AI-003: scheduling graph trả đã đặt nhưng chỉ tìm bác sĩ, không ghi appointment. Cả hai cần bật ENABLE_AI_ORCHESTRATOR; không có bằng chứng runtime/production.

## v0.24 — queue, owner và MPI

OPS-001/002: generator gọi tái khám chạy theo GET và chưa có assignee/claim trước thao tác; cần xác nhận policy. PAT-001: MPI PENDING có getter nhưng chưa thấy app route/UI/review status path. PAT-002: PatientDTO masking được dùng trong scoring CCCD; candidate false-positive chỉ vào PENDING, không có bằng chứng auto-merge.
