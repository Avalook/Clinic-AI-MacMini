# Round 39 — hóa đơn công ty, phân ca, chỉ định dịch vụ và đổi mật khẩu

Nguồn chứng cứ chỉ từ main ghim `956ba4f236b1c92f1280d2097018c199e90ce8c7`; các test được đọc, không chạy. Không truy cập app, API, DB, provider, production, secrets hay hồ sơ bệnh nhân. Exact ranges/hash: `blocks/round39.coverage.json`.

## Finding extensions / addition

- **FE-004 mở rộng:** lịch sử công ty trên hóa đơn biến non-2xx hoặc JSON lỗi thành `[]`, rồi UI nói “Chưa có thay đổi nào.” Đây là cùng nhóm mất phân biệt lỗi đọc với dữ liệu rỗng; chưa probe 403/503/network hoặc xác minh production.
- **FE-022 mở rộng:** lịch sử công ty theo hóa đơn có `LIMIT 100`; UI render danh sách nhận được nhưng không báo còn dữ liệu. Chưa seed hơn 100 dòng.
- **SEC-025 mở rộng:** sau đổi mật khẩu, client không kiểm `res.ok` của POST ghi audit. Backend có endpoint ghi `staff.account_doi_mat_khau_ca_nhan` trong transaction; test đọc chỉ kiểm đường thành công. Đây là gap có điều kiện về khả năng truy vết; cần chốt event này là audit bắt buộc hay best-effort; không chạy fault injection.
- **FIN-018 LOW, confirmed_static:** hai hóa đơn khác nhau của một khách có thể cùng tìm chưa thấy hồ sơ công ty rồi insert trùng: lock chỉ trên payment_cycle, SELECT→INSERT không có khóa/profile uniqueness chung, migration chỉ tạo index thường. Không tái hiện concurrency hoặc khẳng định duplicate production. Chốt khóa nhận diện MST/tên và upsert nguyên tử trước khi triển khai.

## Chính sách giữ lại, chưa tính finding

- **Chỉ định dịch vụ:** POST hiện tại có capability `clinical.order.place` nhưng service không kiểm assigned doctor/team; các đường lưu note/authorize khác có `kiem_dung_ca`. Chưa rõ capability được định nghĩa clinic-wide hay assignment-bound. Cần product/clinical owner chốt phạm vi trước khi gọi là lỗi phân quyền; không có bằng chứng cross-clinic.
- **Ngoại lệ ca trực:** config path có thể thay người bằng nhân sự active cùng clinic; test chủ ý thay lễ tân bằng CSKH và kiểm quyền theo vị trí. Cần chốt competency/approval cho phòng lâm sàng; chưa kết luận auth bypass.
- **Hồ sơ công ty bị ẩn:** chọn ID tường minh kiểm clinic+patient nhưng không `an_luc IS NULL`, còn auto-suggest loại dòng ẩn. Có thể là hỗ trợ sửa hóa đơn cũ hoặc semantics không nhất quán; giữ policy question.

Không phát hiện lỗi mới đủ căn cứ trong roster; không nâng đường chỉ định thành finding khi contract phân công chưa được chốt. Round 39 static-only, không phải chứng nhận runtime/production. Full source audit vẫn chưa hoàn tất.
