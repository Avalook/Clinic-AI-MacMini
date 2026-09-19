# Câu hỏi cho reviewer — hãy trả lời BẰNG MÃ, không bằng tài liệu

Mỗi câu: chỉ ra file/hàm/SQL chứng minh, phân loại *đã chứng minh / lệch nguồn / bug / debt / cần Dr4Women*.

1. Một Visit có đi xuyên journey (check-in → checkout) mà không dùng rail cũ (`work_item`, `service_log`, `lab_result`) làm **nguồn sự thật** không? Chỗ nào còn đọc rail cũ để ra quyết định?
2. Có chỗ nào **quyền** bị suy ra từ queue/work_item/vị trí khách (thay vì vai + phân công) không?
3. Multi-role / acting context: backend có kiểm quyền theo vai **đang dùng** ở mọi đường ghi không, hay chỉ thanh bên (`lib/roles.ts`) che nút? Audit có ghi đúng cả vai dùng lẫn vai tài khoản không?
4. Tệp kết quả bản mới có thể **thừa hưởng** quyền gửi của bản cũ ở bất kỳ đường nào không (upload, duyệt lại, CSKH)?
5. CSKH có đường nào **vượt** bước bác sĩ cho phép gửi không (đánh dấu đã gửi, tải nội dung, Zalo)?
6. Checkout có đóng được lượt khi còn yêu cầu chặn (requirement open, kết quả chờ, chưa thu) mà không ghi lý do không?
7. Một dịch vụ `not_performed` có luôn quay lại bác sĩ để quyết (miễn / theo dõi) và không tự "satisfied" không?
8. Bệnh án / phiếu chuyên khoa **sau khi ký** có bị ghi đè được không (API, autosave, dashboard route chạm DB trực tiếp)? Ngược lại: sau khi ký, luồng khám còn đi tiếp được không (xem mục A của HANDOFF + diff PR #169)?
9. Vai nào đọc được nội dung lâm sàng quá phạm vi (thu ngân, lễ tân, đối tác, CSKH, TKYK với `MO_QUYEN_TAM_THOI`)?
10. Có rò rỉ **chéo phòng khám** (thiếu `clinic_id`, RLS hở, view `SECURITY DEFINER`, route dashboard dùng service-role) không?
11. Thu tiền / cấp thuốc / trừ kho có thể **ghi hai lần** (double submit, retry, idempotency key) không?
12. Có trạng thái nào ở UI **khác** sự thật backend (ví dụ bảng thu ngân hiện khách "chờ thu" nhưng `payment_service` từ chối; màn check-out; nhóm Bàn khám)?
13. Mốc "có kết quả" (`service_order.ket_qua_luc`) có thể được đặt khi chưa có kết quả thật không (ghi chú lúc lấy mẫu)?
14. Hàm nhận ngày/giờ từ người dùng có trả rỗng thay vì ném, và có test rác không (luật dự án)?
15. Bất biến có tranh chấp (một lịch hẹn/khung, một thai kỳ ONGOING, một phiếu thu/lượt) có được ép ở Postgres (unique/check/lock) chứ không chỉ ở Python không?
