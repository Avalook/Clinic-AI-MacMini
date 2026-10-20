# Round 19 — biểu mẫu, thông báo, quyền riêng tư và lịch trực

Nguồn là checkout `main` ghim SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Vòng này chỉ đọc source và test lân cận; không chạy app/DB/API, không gọi Telegram/Zalo, không dùng production, secrets hoặc dữ liệu bệnh nhân. Bằng chứng và SHA từng file được trích trong `round19_findings.json`; path coverage nằm trong `round19_coverage.json`.

## Finding mới

- `FE-019`, `FE-020`: lỗi tải chuông bị hiểu là không có việc; danh sách chuông cắt ở 50 mà không có đường xem tiếp.
- `CLIN-037`–`CLIN-039`: bản in phiếu khám không phân biệt nháp; backend không ràng buộc form kết quả với dịch vụ của chỉ định; hai người sửa cùng field có thể last-write-wins trong khi tab báo đã lưu.
- `SEC-027`: API hồ sơ theo ID/số điện thoại trả PatientDTO cho identity thiếu `patient.list.view`, nhưng vẫn giới hạn cùng clinic và mask national ID.
- `INF-023`–`INF-025`: fanout Telegram có thể lặp ở kênh khỏe khi kênh khác lỗi; Zalo timeout chưa có attempt UNKNOWN để đối soát; dữ liệu động trong template HTML Telegram chưa escape. Relay Telegram hiện tắt mặc định; route Zalo chưa thấy dashboard caller trong source search.
- `FE-021`: giao diện vẫn mời tự đăng ký ca dù backend chủ ý đóng luồng; xếp LOW vì có thể giữ chính sách quản lý xếp lịch.
- `OPS-003`, `SEC-028`, `INF-026`, `OPS-004`: kiểm tra ca phủ lịch không đồng bộ với trạng thái/giờ; `PENDING` có thể tham gia cấp quyền thay bác sĩ nếu còn row; gỡ ca có thể nested acquire connection; API quyết định có thể từ chối row đã APPROVED mà không chạy reconciliation của remove.

## Mở rộng finding hiện có

- `SEC-016`: thêm đường ghi chú tự do của lượt. TKYK có thể gọi endpoint cùng clinic ngoài bác sĩ được phân vì service không gọi assignment helper; cùng root policy với ghi hồ sơ thai kỳ ngoài phân công.
- `SEC-018`: thêm bảng `patient_sdt_them`, được SELECT authenticated và RLS theo clinic, không theo role. Chưa có bằng chứng đọc chéo clinic hoặc runtime PostgREST.

## Kiểm chứng và giới hạn

Round 19 không chạy application tests; những test được nêu trong finding là test lân cận đã tồn tại, không phải test vừa chạy. Năm file voice/retired-route được đọc trọn, không phát hiện finding riêng trong lát này. Các candidate về trạng thái ca là conditional theo row/state; không truy vấn production. HTML v0.40 đã qua RUN-074 (6/6 structural/evidence checks) và RUN-075 (desktop/mobile report UI); ZIP audit-only 255 file đã qua member-set/CRC/byte-count/per-file SHA-256; checksum ở `MANIFEST-GOI.json`. Full source audit vẫn dang dở.

## Ưu tiên kiểm thử kế tiếp

1. Permission matrix synthetic cho `/patients/{id}`, `/patients?phone=`, ghi chú lượt TKYK và `patient_sdt_them` qua PostgREST.
2. Form-result/service binding và concurrent same-field save với hai request cùng revision.
3. Notification error/50+ list; Telegram partial recipient failure; Zalo accepted-then-timeout; escape ký tự HTML.
4. Roster interleaving cho pending/approved/rejected, appointment coverage theo giờ/cơ sở, reject sau approve và pool size 2 dưới concurrent remove.
