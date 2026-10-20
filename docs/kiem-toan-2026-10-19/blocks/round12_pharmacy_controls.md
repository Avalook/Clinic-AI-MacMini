# Round 12 — kiểm soát kho thuốc và vật tư

**Snapshot:** `/tmp/clinicai-audit-main-956ba4f2`, pin SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Đây là bản export không có `.git`; SHA là pin do task cung cấp, không xác minh lại được từ Git. Hash từng tệp bằng SHA-256 được ghi trong `round12_pharmacy_controls.coverage.json` và trong evidence.

**Phạm vi:** đọc tĩnh có chọn lọc các luồng kiểm kê ca/điều chỉnh/hoàn tác, nhập–điều chỉnh tồn thuốc theo lô, phiếu vật tư và tests trực tiếp. Không phải full-source audit. Đã đọc toàn bộ `kiem_ke_ca_service.py`, `vat_tu_kho_man_service.py`, `vat_tu_kho_service.py`, `test_vat_tu_kho_man_db.py` và migration guard P1; các file lớn `pharmacy_service.py`, router, migrations nền và test suites chỉ đọc đoạn liên quan, không đọc hết. Chọn trong các file còn `scanned` ở MAIN-PHAM-VI (cùng một số file đã partial-trace nơi khác); các hash khớp snapshot pin. Không chạy test, runtime, DB, CI hay VPS; không đọc secrets/PHI.

## Kết quả

Có một candidate tĩnh mới, độ nghiêm trọng **LOW**: điều chỉnh tồn thuốc thủ công không giới hạn trị tuyệt đối/độ chính xác theo schema, khác với các đường nhập/huỷ có validate số lượng. Endpoint nhận `float` chỉ chặn NaN/Infinity; service chỉ chặn parse lỗi, số không hữu hạn và zero. Cột sổ là `numeric(12,3)`. Do đó giá trị quá lớn có thể đi tới lỗi tràn numeric ở DB; độ chính xác vượt 3 chữ số thập phân có thể bị DB làm tròn, trong đó số nhỏ có thể thành zero rồi bị constraint từ chối. Đây là suy luận từ static trace/schema, chưa tái hiện HTTP/status thực tế. Giao dịch DB bảo vệ tính toàn vẹn sổ; tác động đã xác lập chỉ là input hợp lệ theo API có thể nhận lỗi DB thay vì 422 có hướng dẫn, hoặc bị làm tròn khi ghi.

**Trigger:** người có quyền kho gửi `POST /api/v1/pharmacy/adjust` với số lượng lớn hơn miền `numeric(12,3)` hoặc có quá 3 số thập phân (ví dụ `0.0004`).

**Đề xuất:** dùng Decimal tại boundary, xác thực finite, giới hạn hợp lý và scale 3 trước khi mở transaction; thống nhất với helper `_so` ở nhập/huỷ. Trả lỗi validation rõ ràng. Giữ constraint DB làm lớp bảo vệ cuối.

**Acceptance:** unit + ASGI test xác nhận số vượt max, thừa scale, NaN/Infinity và zero bị từ chối bằng 422 trước ghi; số hợp lệ 3 chữ số thập phân ghi đúng Decimal; kiểm tra sổ và tồn không đổi với payload bị từ chối. Chưa chạy test theo giới hạn task.

## Dedupe và giới hạn

Đã đối chiếu chủ đề với PHAR-001, FIN-002/008, FIN-003, CLIN-007/030 và các block pharmacy/round3: candidate này chỉ nói về validate số lượng của thao tác điều chỉnh tồn thủ công; không trùng logic hoàn/đổi thuốc, pagination, retry thêm thuốc quầy, sai lô thuốc hay tạo hồ sơ khách.

Không thấy candidate khác đủ bằng chứng trong các luồng kiểm kê ca và phiếu vật tư đã đọc. Kết luận này không bao phủ các caller, UI, migrations khác hoặc toàn bộ `pharmacy_service.py`.
