# Round 12 — quyết định triage

**Nguồn:** snapshot exact-main `/tmp/clinicai-audit-main-956ba4f2`, pin `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Round này chỉ đọc tĩnh; không chạy test, runtime, DB, CI hay VPS. Không đọc secrets/PHI và không sửa source/migration.

## Đưa vào sổ phát hiện

- **PHAR-002 — LOW, confirmed_static.** Thao tác điều chỉnh tồn thủ công nhận `float`, service kiểm finite/zero nhưng chưa kiểm range/scale trước khi ghi `numeric(12,3)`. Việc thiếu validation là trực tiếp thấy trong source; lỗi DB hoặc làm tròn là tác động suy ra từ schema, chưa tái hiện. Không có bằng chứng tồn kho đã sai. Đề xuất nhận Decimal và validate miền nghiệp vụ/3 chữ số trước transaction, rồi kiểm bằng unit + ASGI tests trên fixture dùng một lần.

## Giữ ngoài sổ phát hiện

- **CAND-BOOK-SLOT-001 — quan sát LOW, chưa promote.** Danh sách policy có thể đặt `shadowed=true` cho ngoại lệ bắt đầu trong tương lai, trong khi nhãn UI nói “đang bị luật có ngày đè”. Resolver vẫn lọc theo ngày nên chưa thấy quyết định đặt lịch sai. Chưa có bằng chứng người dùng dựa vào badge hay chịu ảnh hưởng; cần xác nhận semantics với vận hành trước khi xếp là finding.
- **POS outbox — không có candidate mới.** Trong lát đã đọc, transaction enqueue/void và relay cùng dùng causal lock, relay đọc lại trạng thái trước giao; tests hiện có mô phỏng các nhánh retry. Adapter vendor thật chưa hoạt động nên idempotency ngoài vendor và race trên PostgreSQL chưa được xác minh. Dedupe các vấn đề vận hành đã có với INF-005/011/017/018.

## Độ phủ và giới hạn

Coverage từng file/hash/range nằm trong ba artifact `round12_*`. Booking và pharmacy có các file lớn chỉ được đọc có chọn lọc; POS `payment_service.py`, worker và test integrity cũng chỉ trace vùng liên quan. Không suy rộng kết quả của các lát này thành kết luận cho toàn module hay toàn repository. Sau tích hợp, đọc `STATE.json`, `MAIN-PHAM-VI.json`, `PHAT-HIEN.json` và block coverage để chọn lát tiếp theo. **Full source audit vẫn đang dang dở.**
