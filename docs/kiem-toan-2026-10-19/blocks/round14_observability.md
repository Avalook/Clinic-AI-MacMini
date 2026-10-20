# Round 14 — Telemetry lỗi và giảm thiểu dữ liệu

Snapshot exact-main: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Static-only; không chạy test/API/DB, không đọc production logs/secrets/PHI và không sửa source. Lát này đọc trọn `core/telemetry.py` và test trực tiếp, cùng các đoạn middleware, `/ops/telemetry`, và bộ scrubber của kho lỗi.

## Candidate CAND-OBS-RAW-ERROR-001 — Telemetry vận hành có thể trả exception detail chưa được scrub

**LOW · confirmed_static.** `TimingMiddleware` nhận exception chưa được xử lý và gán `str(exc)` vào `detail`. `Telemetry.record` lưu nguyên detail tối đa 300 ký tự cho mọi status 5xx; `snapshot` trả trường `detail`; `/ops/telemetry` trả snapshot cho identity có `ops.view`. Không thấy scrubber trên đường ring-buffer này. Test hiện có kiểm tra việc 5xx xuất hiện và giữ `kind`, nhưng không đặt sentinel nhạy cảm vào `detail` hoặc kiểm tra response đã scrub.

Trigger cần một exception message của 5xx chứa dữ liệu đầu vào/giá trị nhạy cảm, rồi một người có `ops.view` đọc feed. Tác động có điều kiện; **không có bằng chứng** exception thực tế chứa PII/PHI, tài khoản cụ thể có quyền, hoặc dữ liệu này đã xuất hiện trong production. Buffer giới hạn 200 lỗi và nằm trong bộ nhớ tiến trình.

Kho lỗi bền vững có đường khác: `services/kho_loi.thong_diep_sach` áp dụng `_redact_text`, che giá trị `Key (...)=(...)`, thay UUID và cắt 200 ký tự. Finding này không nói scrubber đó bị lỗi; nó chỉ ra ring buffer `/ops/telemetry` không dùng bộ lọc ấy. SEC-021 cũng khác trigger/sink: đó là mã hồ sơ trong structured application log khi lookup miss.

**Đề xuất:** Chỉ giữ error type/code, status, request ID và route template trong telemetry; nếu cần message chẩn đoán, dùng sink đã scrub và quyền phù hợp. Thêm unit test sentinel UUID/email và ASGI test bảo đảm response `/ops/telemetry` không chứa raw sentinel.

Coverage/giới hạn chi tiết nằm trong `round14_observability.coverage.json`. Candidate cần triage, không xác nhận sự cố production. Full source audit tiếp tục chưa hoàn tất.
