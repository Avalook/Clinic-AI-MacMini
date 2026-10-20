# Round 22 — quyền PostgREST, dịch vụ và event/provider

**Baseline:** exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Static review only.

- Thêm `SEC-030` (MEDIUM): một số bảng payment-cycle/bill-line/refund/transfer metadata có thể được SELECT trực tiếp qua PostgREST theo RLS clinic-wide, trong khi endpoint cashier có thêm giới hạn theo ngày/loại/roster/location/shift/actor. Migration cũ cho thấy một phần clinic-wide read có thể là chủ ý phục vụ lễ tân/đối soát; cần product owner chốt scope, không khẳng định đây là vượt chính sách hay đã có người đọc dữ liệu.
- Mở rộng `SEC-011`: một số bảng appointment/service-order draft/prescription allocation thiếu policy RLS assignment chuyên biệt; API `get_draft` có thêm doctor-assignment guard. Đây là cùng gốc rủi ro assignment, không tách thành finding thứ hai. Test hiện hữu chỉ bao phủ một phần bảng clinical.
- Đọc trọn 14 file worker/provider/event trong lát này, không tìm thấy finding mới đủ chứng cứ. Các điểm service-order legacy API không được gọi bởi dashboard hiện tại nên giữ ngoài risk register.
- Candidate stale write selection/carry-over bị loại sau khi đối chiếu row lock và tập quyết định; không còn đủ bằng chứng lỗi.

**Giới hạn:** Không gửi request PostgREST/JWT, không đọc DB hay production, không chạy ClinicAI tests. Không có bằng chứng cross-clinic access, incident hoặc dữ liệu đã bị đọc. Exact ranges, fingerprints và disposition nằm trong `round22_coverage.json`, `round22_findings.json`, `round22_finding_extensions.json`.
