# Round 24 — static exact-main review

Snapshot `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Không chạy test ClinicAI, API/DB/provider/production; không dùng secrets hoặc hồ sơ bệnh nhân.

## Findings tích hợp

- `SEC-031`: scrubber staging có thể bỏ sót biến thể tên/số trong text/JSON. Chỉ áp nếu đường staging cũ còn chạy; AGENTS.md hiện đánh dấu staging là dead. Không có bằng chứng bản sao thật được nạp hay dữ liệu bị lộ.
- `SEC-032`: script cấp tài khoản dùng mật khẩu mặc định dễ đoán nếu operator không override; chưa có bằng chứng đã chạy như vậy.
- `FE-023`: ThaiKy có thể kẹt trạng thái gửi sau fetch reject; chưa fault-injection.
- `FE-024`: home board lấy 300 lượt cũ nhất và không báo cắt; volume >300 chưa xác minh. Khác `FE-003`.
- `API-005`: lịch sử chart có thể phát đến 200 SELECT nối tiếp; chưa benchmark.
- Mở rộng `FE-002`: ThaiKy giữ data cũ/thiếu lỗi refresh; SSE heartbeat/open không chứng minh LISTEN delivery; poll fallback 60 giây.

## Observation chưa promote

`/reports/toan-canh` có API/UI capability mismatch nhưng comment API nói gồm báo cáo, cần owner chốt policy. Roster dedupe theo tên có thể gộp người trùng tên nhưng chưa kiểm dữ liệu. Script xóa trước khai trương có blast radius nhưng là one-off; script test cleanup có backup/preview/confirm/transaction song vẫn cần marker rõ. Script CSV/display-account cần xác minh trust boundary/multi-clinic. Ghi chú tư vấn whole-note last-writer-wins nhưng history giữ bản trước. In đơn trong debounce có timing window, nhưng flush/keepalive tồn tại nên thứ tự chưa rõ. Lab helper/test/spec lệch backend nhưng không có app caller; GoldenRecordEngine là scaffold chưa thấy caller. Lát cashier không thêm lỗi. Các lý do chi tiết ở `STATE.json → held_observations`.

Full reads/targeted findings, hashes và excerpts ở `round24.coverage.json`, `round24_findings.json` và canonical `../PHAT-HIEN.json`.
