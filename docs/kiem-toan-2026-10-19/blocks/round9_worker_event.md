# Round 9 — worker và event

Nguồn: exact-main snapshot `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Đánh giá tĩnh; không chạy test, không kết nối DB/production và không sửa ứng dụng hoặc migration.

Kết quả: **1 candidate mới**, mã tạm `CAND-WRK-001`; chưa thêm vào canonical ledger. Đã đọc đủ các consumer module, luồng worker/timer, vòng chạy và shutdown, retry/DLQ, health/canh_gac. Danh sách file đầy đủ, SHA-256 và dải dòng thực đọc nằm trong [coverage JSON](round9_worker_event.coverage.json). `events/catalogue.py` chỉ được đọc theo các dải ghi trong coverage, đồng thời tìm kiếm registry trên toàn file.

## CAND-WRK-001 — Thu hồi lease không áp giới hạn retry khi worker chết liên tiếp sau khi nhận việc

**Trigger.** Worker dừng đột ngột sau khi transaction claim đã commit nhưng trước khi callback hoàn tất. Claim đã tăng `attempts`/`so_lan_thu`; khi lease hết hạn, reclaimer đưa việc về hàng mà không kiểm tra ngưỡng 5 lần. Nếu crash lặp lại, việc tiếp tục được claim nhưng không đi qua exception handler.

**Bằng chứng.** [events/worker.py](../../../src/clinicai/events/worker.py) đặt ngưỡng 5 ở dòng 43, tăng `attempts` khi claim ở 117–129, chỉ chuyển sang `DEAD` trong exception handler ở 182–194, còn reclaimer luôn đặt lại `RETRY` ở 283–293. [events/hen_gio.py](../../../src/clinicai/events/hen_gio.py) có đường tương tự: tăng số lần ở 111–125; chỉ exception mới xét ngưỡng, chuyển `CHET` và gọi alert ở 168–190; reclaimer luôn đưa về `CHO` ở 227–238. Findings JSON ghi hash và line evidence chính xác.

Test hiện có chỉ mô phỏng một lease bị thu hồi rồi xử lý thành công ([test_event_worker_db.py](../../../src/tests/services/test_event_worker_db.py:204), [test_hen_gio_db.py](../../../src/tests/services/test_hen_gio_db.py:187)); không kiểm tra crash lặp qua ngưỡng. Health/canh_gac đếm số việc trễ/tồn lâu nói chung; metric đó không terminal hóa việc hoặc xác định nó đã vượt retry cap ([health.py](../../../src/clinicai/api/v1/health.py:72)).

**Ảnh hưởng.** Retry cap không giới hạn crash-loop. Event có thể nằm `RETRY` và chặn version mới hơn trong cùng aggregate; hẹn giờ có thể tiếp tục ở `CHO` thay vì `CHET`. Nhánh terminal không tạo dead-letter/alert riêng cho trường hợp này. Health vẫn có thể báo số lượng hàng trễ/tồn lâu, nên không kết luận tình trạng hoàn toàn vô hình.

**Khuyến nghị.** Dùng cùng quy tắc giới hạn cho callback exception và lease reclaim. Khi reclaim việc đã chạm ngưỡng, chuyển sang `DEAD`/`CHET`, lưu nguyên nhân và gọi đường báo người trực; hoặc định nghĩa attempt semantics khác nhưng bảo đảm crash cũng bị chặn hữu hạn. Giữ backoff cho lỗi callback chưa chạm ngưỡng.

**Tiêu chí chấp nhận.** Regression test cho event và timer tạo chuỗi claim → crash trước callback → lease expiry → reclaim lặp tới ngưỡng. Tại ngưỡng phải chuyển sang `DEAD`/`CHET`, tạo audit/alert terminal và không claim lại; callback error vẫn backoff trước ngưỡng và terminal hóa theo chính sách.

**Độ chắc chắn và giới hạn.** Cao về control-flow tĩnh; trung bình về tần suất/tác động vận hành vì chưa mô phỏng crash hoặc đọc runtime. Nếu worker cuối cùng hoàn tất callback, việc vẫn có thể thành công sau hơn năm lần claim; phát hiện này là retry cap không giới hạn được chuỗi claim/crash.

## Đối chiếu canonical

Đã so với `INF-001`–`INF-017` và `AI-004`. Các mục gần nhất là `INF-004` (drain không giới hạn làm đói timer/canh_gac), `INF-005` (thiếu fencing cho callback stale), `INF-017` (metric DEAD chỉ tính 24 giờ) và `INF-002` (gửi Telegram). Những mục đó không mô tả reclaimer bỏ qua retry cap khi process chết sau claim; candidate này không bị gộp trùng. Canonical chỉ được dùng để khử trùng, không làm bằng chứng.

## Giới hạn kiểm toán

Không chạy test hay mô phỏng crash; không truy cập DB, production, secret hoặc PHI. Không sửa app, migration, canonical ledger, HTML hay artifact của agent khác. Coverage JSON liệt kê toàn bộ file và dải dòng thực đọc.
