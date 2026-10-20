# Round 27 — clinic configuration, ownership, account recovery and migration contracts

Snapshot `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Static exact-main only; no ClinicAI tests, API, database, provider, VPS or production access; no secrets/PHI.

## Finding update

- Mở rộng `INF-021` (MEDIUM), không tạo finding trùng: nhiều writer trong ClinicConfigService ghi cấu hình trước rồi dùng pooled connection riêng để ghi audit. Nếu INSERT event lỗi, mutation có thể đã commit dù API trả lỗi và lịch sử thiếu event. `update_service_type` và `room_node_chuyen` là counterexample đúng transaction; không khái quát cho mọi writer.
- Lát phân công bác sĩ/ownership không tạo finding mới; các điểm đã thấy thuộc SEC-028, SEC-011/016, SEC-027, CLIN-004/OPS-002 và observations work-item đang giữ.
- Rà soát migration/RLS tĩnh không tạo finding mới. Cả 373 migration đã ở trạng thái read trong ledger từ các lượt trước; không kiểm tra DB catalog.

## Held observations

- Khôi phục mật khẩu nhận email đầy đủ trong khi login chấp nhận username: chính sách username `.local` và kênh recovery chưa rõ.
- Migration dry-run có thể tạo schema/bảng ledger rỗng nếu chưa tồn tại; không áp migration hay dữ liệu nghiệp vụ.
- Nút Lưu tên+tầng phòng gửi hai PUT tuần tự; tính nguyên tử mong muốn là câu hỏi sản phẩm.

Coverage hash, dòng và mức đọc ở `round27.coverage.json`; finding mới không có, `round27_findings.json` là danh sách rỗng. Full source audit còn mở.
