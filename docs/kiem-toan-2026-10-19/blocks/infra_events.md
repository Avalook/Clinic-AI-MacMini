# Kiểm toán hạ tầng, sự kiện, độ tin cậy

Trạng thái: đang đọc. Chưa có test/runtime/prod.

## Bước kế tiếp
Đọc event worker/outbox, SSE reconnect, backup/restore/deploy/CI.

## Root checkpoint 2026-10-19T17:46:43.192198+07:00

Khối chưa hoàn tất. Nội dung agent ban đầu là baseline543b9787+WIP; ưu tiên PHAT-HIEN.json/main_validation cho kết luận mới.
- INF-001: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- INF-002: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- INF-003: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- INF-004: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- INF-005: still_present_on_main — Đường claim/finish trên main vẫn như baseline; đây vẫn là giả thuyết concurrency, chưa chứng minh consumer cụ thể tạo tác động trùng.
- INF-006: still_present_on_main — Khoảng trống kiểm chứng DR vẫn còn; không suy rằng backup thật đang mất hoặc không phục hồi được.
Tiếp theo: TIEP-TUC.md và MAIN-PHAM-VI.json. Không tự nâng scan thành đọc sâu.


## Root checkpoint 2026-10-19T20:48:50+07:00 — SSE và event delivery (static)

- Đã đọc đủ dashboard SSE route (80 dòng), FastAPI events router (76), ChangeBroker (153), EventService (146), publisher, adapter, tool wrapper và GoldenRecordEngine; RealtimeRefresher chỉ đọc phần cấu hình bảng, reconnect/ẩn tab/poll/catch-up. Coverage chi tiết trong `blocks/infra_events.coverage.json`.
- Không thêm finding mới cho SSE: server session + API key, clinic-scoped subscription, payload chỉ tên bảng/clinic, queue mỗi kết nối max 8, disconnect được truyền upstream; client tự reconnect, catch-up khi mở lại tab và poll 60 giây khi visible. Đây là trace source, chưa phải runtime/end-to-end guarantee.
- Generic `EventService.get_unpublished` không có caller ngoài định nghĩa/test theo source search; `RabbitMQPublisher` và GoldenRecordEngine vẫn là stub, không tìm thấy wiring production ở lát cắt. Không kết luận đường domain-event đang mất tin; các hệ thống event khác nhau vẫn cần inventory tiếp.
- INF-005 remains hypothesis: lease 120s, reclaim hết hạn, DONE/RETRY không fence theo locked_by/attempt. Existing DB test chỉ giả lập worker chết; chưa có test hai worker với handler cũ còn sống.
- Không đọc DB/production và không chạy HTTP. Main ledger hiện 206 traced một phần / 2.126 scanned / 550 inventoried / 8 excluded; code-like 190 / 2.122 / 22.


## v0.18 — bổ sung trace

INF-009 MEDIUM/confirmed-static: khi timer due đã DANG_LAM, đổi ngày tái khám chỉ huỷ CHO; timer mới xung đột unique key, handler cũ bỏ qua ngày stale và đánh BO_QUA. Khác INF-005; chưa DB interleaving test. Canonical evidence ở PHAT-HIEN.json.


## v0.19 — INF-007 mở rộng sang refund partial

Ngoài CSKH, route `/payments/hoan-tien` cũng commit refund trong `HoanTienService` trước khi `IdempotencyGuard.save`. RUN-036 inject lỗi ở receipt boundary rồi retry cùng key/body sau 6 phút, tạo hai khoản hoàn partial COMPLETED. Đã thêm probe refund vào `PHAT-HIEN.json`; chưa ASGI, provider hay production. Gốc khắc phục là command receipt/reconciliation dùng chung transaction.

## v0.21 — timer fencing và POS operator recovery

- **INF-005** vẫn là hypothesis cho event worker và nay có static evidence tương tự ở `hen_gio`: claim xong chạy callback ngoài transaction; reclaim hết lease không có generation token; worker cũ hoàn tất bằng `WHERE id`. Chưa chạy slow-handler interleaving DB test.
- **INF-011 MEDIUM/design_gap:** POS `DEAD` row chỉ update DB/log; code/API/dashboard không có operator view, owner, repair/retry/reconcile path, health không đếm POS. POS relay opt-in; đây là cổng hoàn thiện trước khi bật tích hợp, không phải sự cố hiện hành.
- Notification relay at-least-once và POS adapter idempotency là semantics đã ghi nhận; không tách finding khi chưa có hành vi độc lập mới.
- Coverage là selected trace, chưa chạy full worker suite, concurrency lâu, provider thật, load hoặc production.

## v0.21 — timer fencing và POS operator recovery

- **INF-005** vẫn là hypothesis cho event worker và nay có static evidence tương tự ở `hen_gio`: claim xong chạy callback ngoài transaction; reclaim hết lease không có generation token; worker cũ hoàn tất bằng `WHERE id`. Chưa chạy slow-handler interleaving DB test.
- **INF-011 MEDIUM/design_gap:** POS `DEAD` row chỉ update DB/log; code/API/dashboard không có operator view, owner, repair/retry/reconcile path, health không đếm POS. POS relay opt-in; đây là cổng hoàn thiện trước khi bật tích hợp, không phải sự cố hiện hành.
- Notification relay at-least-once và POS adapter idempotency là semantics đã ghi nhận; không tách finding khi chưa có hành vi độc lập mới.
- Coverage là selected trace, chưa chạy full worker suite, concurrency lâu, provider thật, load hoặc production.

## v0.22 — stale lease probe và notification relay

- RUN-043 tái hiện generic worker callback A tiếp tục commit sau khi lease hết, event được reclaim, B commit DONE: 1 passed / 0.20s trên DB synthetic. Hai scratch effects commit; chưa chứng minh consumer nghiệp vụ/provider bị gọi trùng.
- INF-005 được nâng từ hypothesis lên reproduced_local; static source cũng còn thiếu fencing. Template DB main@27e010d6 khác seed pinned, runner áp 42 migration; không phải fresh install.
- INF-012 là confirmed_static: 50 event relay cũ lỗi/thiếu cấu hình có thể chiếm batch cũ nhất; heartbeat xanh, health không đếm backlog event_log. Chưa dựng batch runtime.
- Cần tiếp tục fairness/backoff/dead-letter của relay, metric oldest pending, và test fencing với consumer/projection thực trên DB disposable.

## v0.23 — backup, Caddy và CI

INF-001 mở rộng ảnh chuyển khoản pending. INF-013 health/Ops bỏ sót backlog ảnh; INF-014 CI bỏ qua untracked; INF-015 restart Caddy giữ file bind-mount cũ. Static exact-main, chưa deploy/Docker/GitHub/backup thật.

## v0.24 — giới hạn upload siêu âm

INF-016: BFF request.formData + backend file.read toàn bộ trước khi kiểm 12MB; middleware hiện chỉ chặn CSKH upload. Static, chưa thử body quá cỡ/chunked hoặc proxy ngoài repo.


## v0.25 — DEAD alert lifetime

INF-017 là trace tĩnh: `health.do_su_kien` và Canh gác chỉ đếm delivery `DEAD` trong 24h; hết cửa sổ thì health có thể xanh và cảnh báo được đóng. Worker vẫn coi delivery chưa `DONE` là blocker; `/ops/su-kien` vẫn đếm DEAD toàn thời gian. Nếu có successor PENDING quá 15 phút, `ton_lau` có thể phát tín hiệu lại; vì vậy không gọi dead-letter hoàn toàn vô hình. Test hiện kiểm số `chet_24h` do fixture cung cấp, chưa kiểm một DEAD chưa xử lý đã già hơn 24h và cảnh báo đóng. Chưa chạy DB/production.
Coverage v0.25: đọc đầy đủ worker, event schedule/replay/emit, event/notification service, hai migration event chính và các test worker/relay/health đã nêu trong ledger; chỉ trace các vùng health, Canh gác, `/ops`, event catalogue và consumer registry. Các consumer khác và test đã scan chưa được coi là đã đọc.

## Round 40 — migration runner

Review read-only exact-main: mở rộng INF-008 cho runner thường, không tạo finding trùng. Explicit `COMMIT` trong một trong 23 migration có thể tách schema commit khỏi ledger insert; điều kiện là runner dừng trong cửa sổ đó. Không có test/DB replay hoặc production validation. Xem `blocks/round40.coverage.json`.
