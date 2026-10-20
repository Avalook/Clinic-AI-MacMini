# Round 13 — API errors, rate limiting và an toàn log

**Nguồn:** snapshot exact-main `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Chỉ đọc tĩnh; không chạy test/runtime/DB/VPS, không đọc secrets/PHI và không sửa source/migration.

## Kết quả

Có một candidate **LOW** về định danh bệnh nhân trong API log. Khi không tìm thấy hồ sơ, service tạo `ResourceNotFoundError` với `clinic_patient_id` nằm trong message. Exception handler ghi nguyên message vào field `reason`. Bộ scrubber hiện xử lý key như `clinic_patient_id`, email, điện thoại và bearer token; với free text nó chỉ có regex cho email/điện thoại/token, nên UUID nằm trong `reason` không được che. Đây là đường log có thể truy vết tĩnh; chưa xem log hay cấu hình retention ở production. Tác động giới hạn ở mã hồ sơ nội bộ có thể được lưu trong log, không có bằng chứng về nội dung bệnh án bị ghi qua đường này.

**Đề xuất:** không ghi raw exception message vào log mặc định; ghi error code/type/request ID và route template. Nếu cần điều tra, truyền identifiers riêng dưới key đã scrub hoặc dùng mã tương quan không ánh xạ ngược trực tiếp; thêm regression test cho UUID trong `reason` và exception text.

**Dedupe:** SEC-013 nói về payload tạo bệnh nhân trong event/audit log, gồm CCCD và thông tin liên hệ. Candidate này là đường log ứng dụng khi lookup không thấy hồ sơ, ở một sink và trigger khác; không khẳng định hai finding cùng độ nhạy.

## Các kiểm soát đã đọc, không mở finding

- `InMemoryRateLimiter` có key theo clinic+staff, giới hạn bộ nhớ, fail-closed khi đầy, `Retry-After` và test các nhánh chính. Tính process-local được nêu rõ trong docstring cùng yêu cầu thay sang limiter dùng chung trước khi tăng worker; không xem đây là lỗi tại cấu hình một process trong snapshot.
- Xử lý validation 422 giữ `detail` cho máy và thêm câu tiếng Việt; các lỗi custom giữ envelope/mã ổn định; unhandled exception không trả stack trace/raw message cho client. Test tương ứng tồn tại nhưng lượt audit này không chạy test.
- Logging pipeline gắn scrubber vào cả structlog lẫn stdlib/Uvicorn; access log cắt query string để không ghi tên/điện thoại tìm kiếm.

## Phạm vi

Các file nhỏ về rate limit, validation, exception hierarchy và test trực tiếp đã được đọc trọn. `main.py` và `patient_service.py` chỉ đọc những vùng liên quan; coverage JSON ghi hash, line ranges và mức đọc. Kết quả không phải audit toàn bộ middleware, router, cấu hình logging hay repository. **Full source audit còn dang dở.**
