# Round 11 — UI phiếu khám và cập nhật dữ liệu lâm sàng

Nguồn: snapshot exact-main `/tmp/clinicai-audit-main-956ba4f2`, repository SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Đây là static trace, chỉ ghi artifact lượt này; không sửa app/migration và không chạy test, browser, runtime, DB, VPS hoặc truy cập secrets/PHI.

## Candidate mới

- **CAND-R11-DASH-FORM-01 · MEDIUM — chọn hai mẫu phiếu nhanh có thể để response cũ mở mẫu không phải lựa chọn cuối.** `PhieuKhamLuot` giữ các nút lựa chọn mở trong lúc GET đang chờ. Mỗi lần bấm gọi `napPhieu(formId)`; hàm áp dụng response không kiểm tra mã lựa chọn hiện hành. Nếu response của A đến sau B, dữ liệu/revision của A ghi vào state cuối. Bằng chứng và dòng chính xác ở `round11_dashboard_forms.findings.json`.
- **CAND-R11-DASH-FORM-02 · MEDIUM — in từ lượt cũ có thể mở phiếu của lượt gốc.** `XemLuot` đọc/hiển thị theo `dangXem`, nhưng href nút in dùng `visitId` ban đầu. Bấm một lượt trước rồi in sẽ tạo liên kết của lượt khác với lượt đang hiển thị. Không trùng CLIN-021, vốn nói về revision chưa release trong cùng lượt.

## Khử trùng và giới hạn

Đã đối chiếu ledger tại SHA-256 `9d13a96c2f079b855d4cd7b9a98bd7b77b18ac3e29d127dde3cab487cc174601`; ghi liên hệ nhưng không lặp FE-007 (stale dữ liệu khi đổi bệnh nhân), CLIN-020 (ghi sau FINALIZED), FE-005/FE-006, FE-011/CLIN-034, CLIN-021 và SEC-019. Phạm vi source đã đọc sâu có chọn lọc theo coverage cũ: shell phiếu, chọn định nghĩa, bản xem lượt/lịch sử, proxy contract, auto-save và các vùng đọc-only liên quan. Coverage JSON liệt kê từng path, hash, line count và ranges. Những file trong thư mục `phieu-kham/**` chỉ ở trạng thái scan trước đó không được coi là đã đọc thủ công trong lượt này.

Hai candidate là suy luận từ control flow tĩnh; không có xác minh runtime hay dữ liệu production. Không đánh giá business internals của FastAPI/DB.
