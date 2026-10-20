# Round 31 — phản hồi CSKH và vòng đời phòng/hàng chờ

Snapshot cố định: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Evidence lấy từ Git HEAD worktree ghim, không dùng dirty primary checkout. Chỉ đọc tĩnh; tests đọc, không chạy; không gọi app/API/DB/provider/VPS/production.

## Kết quả

- **CLIN-045 MEDIUM — feedback CSKH có thể bị cắt ở 300 dòng.** Service cap chung cho nhóm khách hiện xem; response không có pagination metadata; UI nhóm theo khách và có empty state tuyệt đối. Phản hồi cũ có thể nằm sau cap. Trigger phụ thuộc >300 dòng; production chưa đo. Tách CLIN-022 vì finding đó cắt danh sách khách liệu trình.
- **CLIN-046 MEDIUM — undo checkout có thể hồi sinh queue gắn phòng inactive.** Checkout đặt queue thành `left`; gate tắt phòng không xét `left`; undo trả `waiting` và giữ room_id; danh sách phòng chỉ lấy phòng active. Test hai nửa đã được đọc nhưng chưa compose trình tự. Production chưa xác minh.
- OPS-009, FE-002, FE-004 đã bao phủ cap dispatch 400, freshness panel và unknown-vs-zero; không tạo bản trùng. FE-010 là phòng active nhưng tạm ngừng nhận, khác vòng đời inactive room.
- Một câu hỏi held: current owner của khiếu nại sau intake/đổi ca, SLA/escalation/acknowledgement/reopen. Schema có người tiếp nhận và người xử lý khi đóng; không kết luận thiếu owner tuyệt đối.

Scope, SHA-256, line ranges, mức đọc và test gaps ở `round31.coverage.json`; held contract ở `round31_observations.json`. Một số file ngắn được đọc hết; file lớn chỉ trace theo luồng. Không tuyên bố đã đọc toàn bộ source.
