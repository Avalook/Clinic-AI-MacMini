# Round 26 — static exact-main dashboard and operations review

Snapshot `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Chỉ đọc nguồn ghim; không chạy test ClinicAI/API/DB/provider/VPS/prod, không đọc secrets/PHI.

## Findings tích hợp

- `FE-026` (LOW): panel lịch sử điều phối có thể giữ ‘Đang tải…’ khi backend lỗi; retry chỉ gián tiếp theo thay đổi queue/remount. Panel phụ; chưa có tác động lâm sàng được chứng minh.
- `OPS-008` (MEDIUM, điều kiện): danh sách nhóm lỗi lấy tối đa 100 dòng nhưng không có metadata phân trang; volume production chưa kiểm.
- Mở rộng `FE-004`: Báo cáo và Toàn cảnh biến null thành empty/0; Trang chủ cũng render KPI fallback 0 nhưng có banner lỗi riêng.
- Mở rộng `FE-023`: AppointmentBooking không dọn pending khi fetch/JSON reject và không gửi Idempotency-Key. Service và partial unique index có duplicate guard; không kết luận retry tạo lịch trùng.

## Held observations

Nút Làm mới của PortalBoard chỉ đọc lại trạng thái hạ tầng trong khi số liệu Toàn cảnh là props phía server; contract mong đợi chưa rõ. Tác động OPS-008 cần hơn 100 nhóm đang xem; production volume chưa đo.

Hashes, excerpt, path-level review status và dòng test được đọc ghi ở `round26.coverage.json`; findings mới nằm trong `round26_findings.json` và canonical `../PHAT-HIEN.json`. Không chạy test.
