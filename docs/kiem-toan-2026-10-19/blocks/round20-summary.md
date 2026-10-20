# Round 20 — queue, follow-up, reminders, clinical results and cleanup

Nguồn là exact-main ghim `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Round 20 đọc/trace 36 path, trong đó 16 file được đọc trọn; danh sách file, line range, SHA-256 và mức coverage nằm ở `round20_coverage.json`. Chỉ source/test liền kề được đọc; không chạy ClinicAI app, DB, API, provider hoặc production, không đọc secrets/PHI.

## Finding mới

- `CLIN-040` (MEDIUM): `save_measurements` merge `findings` từ snapshot chưa khóa rồi ghi đè toàn JSON. Hai lần ghi cùng lượt có thể mất update nếu không có một work item chưa nhận tình cờ tuần tự hóa chúng. Route API tồn tại nhưng chưa tìm thấy dashboard caller đang bật `showSono`; không kết luận luồng hiện được nhân viên dùng.
- `OPS-005` (LOW): kết quả gọi tái khám có thể nhận phản hồi 2xx `da_ghi_tu_truoc` dù row vừa thành `KHONG_CAN` do trigger lịch hẹn và nhánh đó chưa tạo `cskh_log`. Chỉ áp dụng race/tab cũ; chưa tái hiện.
- `FE-022` (LOW): khối tự nhắc cá nhân cắt ở 100 mục mà không `has_more`/phân trang. Reminder/timer vẫn còn trong hệ thống; chưa có bằng chứng ngưỡng đã gặp.

## Mở rộng finding

- `SEC-028`: ngoài quyền thay bác sĩ, `hang_cho.cap_nhat_vi_tri` cũng dùng `work_roster.status <> 'REJECTED'` để suy phòng/node khi vị trí lượt chưa có. Một row `PENDING` có thể trở thành nguồn vị trí vận hành nếu station mapping còn active. Điều kiện phụ thuộc row/state; không có DB/production confirmation.

## Quan sát giữ ngoài risk register

- `SONO-UI-CONTRACT-001`: `SonoBiometry` đọc/ghi `/api/ultrasound`, nhưng component bị chặn bởi `showSono` mặc định false và không tìm thấy callsite truyền true. BFF generic hiện GET queue/POST draft, còn API measurements tương thích là route riêng. Chưa có user-facing caller, nên giữ làm contract phải giải quyết trước khi bật lại UI.
- `CLEANUP-SCHEMA-001`: full-wipe script cũ có thể dừng ở FK graph guard sau khi writer đã dừng nếu schema có thêm hai bảng payment mới. Transaction/guard dự kiến fail-closed, current selective cleanup có đường khác và DANG-LAM còn ghi trạng thái cũ. Chưa gọi đây là data-loss defect; cần xác nhận script còn được dùng.

## Đọc và kiểm chứng

Các service được đọc trọn gồm intake/queue, recall, reminder, file watch/result return, Andrology và ultrasound; ba script cleanup cũng đọc trọn. Targeted traces đi đến route/UI/test và migrations liên quan. Test liền kề chỉ được đọc để hiểu khoảng trống, không chạy trong vòng này. Không có kết luận về occurrence production, mức sử dụng UI siêu âm, ngưỡng reminder hoặc trạng thái dữ liệu thật.

HTML v0.41 qua 6/6 structural/evidence checks (RUN-076) và browser QA desktop/mobile (RUN-077). ZIP audit-only 259 file qua member-set/CRC/byte-count/per-file SHA (RUN-078; archive sau đó được dựng/verify lại). Các bước này chỉ kiểm artifact. Full source audit vẫn `in_progress`.

## Thiết kế/kiểm thử kế tiếp

1. Clinical writes phải có revision/CAS hoặc khóa aggregate đúng chỗ; probe hai writer cho ca assigned, unassigned và không có work item.
2. Recall outcome cần phân biệt `recorded`, `already_recorded` có bằng chứng, và `superseded_by_appointment`; UI không được coi mọi 2xx là đã ghi cuộc gọi.
3. Các danh sách có giới hạn cần cursor/`has_more` hoặc nhãn rõ; fixture 101 personal reminder và kiểm timer vẫn giữ.
4. Roster `APPROVED` phải là nguồn duy nhất cho authority và room/node hiệu lực; PENDING/REJECTED được kiểm cả permission gate lẫn queue projection.
5. Trước khi bật `SonoBiometry`, nối UI/BFF đúng route và thêm contract test; xác nhận chính sách vận hành của full-wipe script hoặc đánh dấu retired.
