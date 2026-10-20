# Round 13 — triage và khử trùng

Ngày chốt: 20/10/2026. Nguồn bằng chứng: snapshot exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Bốn lát API/logging, vòng đời lịch, patient lookup/CSKH và công nợ được đọc tĩnh có chọn lọc. Không chạy test/runtime/DB, không truy cập VPS, secrets hoặc PHI.

## Đưa vào risk register

- **CLIN-035 — MEDIUM, confirmed_static:** action `no_show` không kiểm thời điểm hẹn; giao diện bật nút cho lịch chưa tới giờ trong ngày. Trạng thái này giải phóng chỗ và bị ẩn khỏi lưới tuần.
- **SEC-021 — LOW, confirmed_static:** khi lookup hồ sơ không thấy patient, exception message chứa UUID; handler ghi `reason` và bộ scrubber không xóa UUID trong free text. Chưa xác minh sink/retention production.
- **SEC-022 — MEDIUM, confirmed_static:** patient-list và CSKH list serialize CCCD/email nguyên văn vào response/client props dù màn patient-list không dùng hai field này. Các truy vấn đã đọc vẫn lọc theo clinic; chưa xác lập yêu cầu cô lập theo cơ sở.
- **SEC-023 — MEDIUM, confirmed_static:** preset CASHIER* được migration cấp `crm.manage`; cùng capability mở một số endpoint ghi tương tác/follow-up/phản hồi dù ghi chú role/UI nói thu ngân chỉ đọc. Static evidence không chứng minh tài khoản production còn nguyên preset.
- **FIN-013 — MEDIUM, confirmed_static:** khoản dịch vụ chưa có giá có thể được ghi nợ với tổng 0; projection dư nợ chỉ lấy `so_du > 0`, nên trạng thái nghĩa vụ chưa định giá không xuất hiện như một khoản mở trong tally/list tiền.
- **FIN-014 — MEDIUM, design_gap:** phủ nợ chỉ so `source_id`; nếu số tiền cùng nguồn thay đổi sau lần ghi nợ, check-out không yêu cầu xác nhận lại. Giá trị hiện hành được tính lại từ bảng giá active. Cần chốt chính sách giá/nợ và xác nhận lại của khách; chưa có bằng chứng production hay hợp đồng giá đã xác định.

Các finding mới có evidence exact-main và acceptance criteria trong `PHAT-HIEN.json`. FIN-014 được giữ mức `design_gap` vì semantics đổi giá của khoản đã ghi nợ chưa được quy định đầy đủ.

## Candidate không đưa vào risk register

- `CAND-BOOK-SLOT-001`: giữ trong `STATE.json`; badge có thể mô tả override tương lai là đang hiệu lực, nhưng resolver vẫn lọc thời gian và chưa có bằng chứng quyết định booking sai.
- Luồng điều hướng/gate cashier không có finding riêng trong phần đã đọc.
- Phạm vi `location_id` của patient/CSKH list được giữ là câu hỏi chính sách; chưa có hợp đồng chi nhánh đủ rõ để gọi là lỗi.

## Kiểm tra trùng

- SEC-021 khác SEC-013: UUID trong structured application log khi lookup miss, thay vì CCCD/liên hệ trong event log khi tạo hồ sơ.
- SEC-022 khác SEC-013/018/020: PII nguyên văn trong response của list endpoint; không phải event log, PostgREST read hay chart lâm sàng.
- SEC-023 khác SEC-020: cùng capability `crm.manage` nhưng finding này là quyền ghi tương tác CSKH do preset CASHIER cấp; SEC-020 là đọc tổng hợp hồ sơ khám.
- FIN-013/014 khác DB-007 và các finding FIN cũ: lần lượt là biểu diễn số dư không định giá và xác nhận snapshot tiền của cùng nguồn; không phải sai tenant FK, chốt ca hay giảm giá.
- CLIN-035 khác các finding reschedule/check-in hiện có: thiếu rào thời gian cho `no_show` trước giờ hẹn.

## Giới hạn và việc tiếp theo

Các artifact từng lát ghi path, SHA, dòng và mức đọc; những file chỉ trace không được tính là full read. Hệ thống và production chưa được chạy/xác minh. Vòng tiếp theo đang kiểm toán work-item ownership/SLA, Postgres RLS/grants và payment settlement; tiếp tục mở rộng source review sau đó. Full source audit vẫn chưa xong.
