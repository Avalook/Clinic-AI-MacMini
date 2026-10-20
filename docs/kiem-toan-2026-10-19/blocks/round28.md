# Round 28 — CSKH retry, kiểm kê ca và freshness đo sinh hiệu

Snapshot exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Static source review only. Không chạy tests/app/API/DB/provider/VPS/production; không đọc secrets/PHI.

## Finding mới

- **CLIN-044 MEDIUM:** tạo hẹn gọi lại không có operation key hoặc domain dedupe. Mất response sau commit rồi retry có thể sinh hai việc mở và hai thông báo cho cùng nội dung. Đây là static path; chưa tái hiện và không chứng minh đã xảy ra production. `nhac-tai-kham` có unique conflict riêng nên không bị gộp vào finding này.
- **PHAR-003 MEDIUM:** hai nhân viên cùng sửa một phiếu NHAP có thể ghi đè số đếm cũ: service chỉ khóa/tuần tự hóa, không compare revision; upsert last-write-wins. Đã đối chiếu test ghi đè tuần tự nhưng không có multi-editor stale-revision test. Khác miền dữ liệu với CLIN-039.
- **PHAR-004 LOW:** UI gọi lỗi mạng là “CHƯA lưu” dù POST chốt có thể đã commit. Retry qua giao diện chạy lưu nháp trước, nên chạm conflict trạng thái trước khi tới nhánh close replay-safe. Backend ngăn ghi/chốt lặp; chưa có bằng chứng điều chỉnh tồn bị trùng.

## Finding được mở rộng

- **FE-002:** thêm `/do-sinh-hieu` vào cùng nhóm freshness: refresh lỗi giữ hàng chờ cũ, cảnh báo chỉ nằm trong panel bệnh nhân đang chọn nên có thể không thấy khi chưa chọn. Không tạo finding riêng.

## Candidate được giữ lại

- **CSKH-ROSTER-CAP-001:** query ghép ca trực và tuần đã công bố có `LIMIT 5000` không có `ORDER BY`. Chỉ có thể thiếu hàng nếu volume vượt cap; chưa đo production volume hoặc chốt policy, nên giữ ở STATE thay vì tính finding.

## Bằng chứng và phạm vi

`blocks/round28.coverage.json` ghi hash, line range, prior/current coverage status và mức đọc cho các lát CSKH, KiemKeCa và đo sinh hiệu. `round28_findings.json` chứa ba finding mới; `round28_finding_extensions.json` ghi bản FE-002 sau khi bổ sung.

Coverage path-level chỉ nói file đã inventory/read/traced/scanned; không đại diện cho tỷ lệ hành vi đã hiểu. Full source audit tiếp tục mở.
