# Round 23 — pharmacy lifecycle và clinical form boundary

**Baseline:** exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Static review only.

- Đọc trọn ba service dược/đơn hàng/phiếu chỉ định liên quan; không thêm finding dược. Câu hỏi về mapping Bio là hint hay allowlist và cap 200 lịch sử chưa được nâng thành lỗi vì thiếu policy/ngưỡng thực tế.
- Thêm `CLIN-041` (MEDIUM) chỉ cho đường **generic Form Engine**: router nhận payload dictionary; validator kiểm tra một số thuộc tính nhưng không xác thực chính xác frame/schema keys và kiểu value trước khi lưu JSON. Dashboard renderer chỉ hiện field khai trong schema. Tác động phụ thuộc client được phép gửi payload malformed; chưa có request tái hiện hoặc bằng chứng payload sai đã phát sinh.
- Ranh giới quan trọng: đường **phiếu khám v5** dùng frame đã ghim và kiểm tra key theo schema; test hiện hữu từ chối key ngoài khung. Không áp `CLIN-041` cho v5 và không thêm finding v5 trong lát này.
- Giữ câu hỏi requiredness của form generic để chủ sản phẩm/lâm sàng định nghĩa field bắt buộc; chưa coi thiếu metadata bắt buộc là bug đã xác nhận.

**Giới hạn:** Không chạy app/API/DB/provider/production tests; test chỉ được đọc. Exact paths/ranges/hash ở `round23_clinical_coverage.json`, `round23_clinical_findings.json`, `round23_clinical_v5_boundary.json`, `round23_pharmacy_coverage.json`. Đọc thêm `refine_round23_clinical.py` để thấy cách tách generic/v5 trước khi thay đổi phân loại.
