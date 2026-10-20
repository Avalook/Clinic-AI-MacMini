# Round 8 — panel đối chiếu Nam khoa (exact-main)

Tham chiếu snapshot `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Chỉ đọc. Không sửa app/migration, không chạy DB/prod, không dùng secrets/PHI. Lát cắt chính gồm đúng 8 file: UI `AndrologyReview`/`ServiceFormEngine`, route BFF, helper proxy, router, permission contract, service và unit test. Danh sách span, hash SHA-256, các file cross-check một phần và giới hạn nằm trong `round8_frontend.coverage.json`.

## Finding mới

- **CLIN-034 · MEDIUM — review cũ vẫn hiện trong lúc form thay đổi.** Sau khi đã có kết quả, sửa một ô khiến component debounce 600 ms rồi gọi lại API nhưng giữ nguyên `review` trước đó. Thẻ vẫn hiển thị con số/cờ của snapshot cũ bên cạnh form mới mà không có trạng thái “đang tính”. Cleanup đã chặn response cũ ghi đè nên finding này chỉ về trạng thái cũ đang nhìn thấy, không cáo buộc race ghi đè.
- **FE-011 · MEDIUM — quyền đọc form không khớp quyền gọi review.** `ServiceFormEngine` vẫn mount panel khi `readOnly`; GET phiếu chấp nhận `cua_y_khoa`, nhưng POST review yêu cầu `cua_ghi_y_khoa`. Tài khoản chỉ có quyền đọc y khoa có thể đọc phiếu nhưng nhận 403 ở panel; UI đổi mọi non-2xx thành “Chưa đọc được ngưỡng tham chiếu”, che nguyên nhân quyền.

## Negative findings và giới hạn

- BFF xác thực user, chuyển tiếp request theo caller; backend review phụ thuộc StaffIdentity và đọc theo `clinic_id`.
- Service review chỉ đọc reference ranges/sinh hiệu; không ghi form, không tạo chỉ định. Unit tests hiện có tập trung logic service; round này không chạy tests và không kiểm tra quyền bằng HTTP/browser.
- Đã spot-check thêm đường GET form/history và migration để loại các hướng khác; các file này không được dùng làm evidence cho hai finding trên.
- Đây là trace tĩnh cho một panel chuyên khoa, không phải xác nhận lỗi đã xảy ra trên production hay audit toàn bộ form khám.

Chi tiết trigger, ảnh hưởng, path/line/hash, đề xuất và điều kiện chấp nhận nằm trong `round8_frontend.findings.json`.
