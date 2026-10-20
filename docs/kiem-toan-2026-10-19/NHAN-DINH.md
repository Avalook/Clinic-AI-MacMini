# Nhận định theo các lát cắt đã kiểm — Round 44: clinical, quyền duyệt và recovery

Nguồn code là Git main ghim `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Risk register giữ 198 hồ sơ (27 HIGH, 143 MEDIUM, 28 LOW). Path ledger 2.890 đường dẫn: 882 read, 497 traced một phần, 1001 scanned, 502 inventoried, 8 excluded. Đây là trạng thái theo path, không phải behavioral coverage; **full source audit chưa hoàn tất**.

Round 44 thêm CLIN-056 MEDIUM: một lần lưu bệnh án có draft có thể bỏ qua thay đổi riêng `drug_catalog_id` vì comparator không bao gồm trường này và caller bỏ qua thay đơn khi kết quả nói “không đổi”. Trigger có điều kiện; chưa tái hiện DB hoặc chứng minh bệnh nhân đã nhận sai thuốc.

Round 44 thêm SEC-036 HIGH: route chốt kết quả gác capability `result.review.approve`, preset TKYK có quyền này. Worklist lọc theo bác sĩ được phân, nhưng lệnh review không gọi assignment guard; service chỉ xác nhận exact result/patient/clinic và chốt. Release gate sau đó cho phép khi `is_finalized`. Đây là lỗ hổng phạm vi trong cùng clinic; cần UUID và capability, không phải cross-tenant bypass. Chưa chứng minh thông báo hay sự cố.

INF-006 được mở rộng bằng việc đọc full backup/verify/restore/drill: manifest nói cần Supabase Cloud PITR/auth backup trong khi project chạy self-hosted; drill chỉ trích UUID để seed auth.users và không xác nhận login thật. Đây là recovery-contract/runbook gap, không bằng chứng artifact đang mất. INF-021 được bổ sung writer cấu hình commit trước khi ghi audit.

Round 44 đọc toàn bộ 20 file mới theo hash/line count exact-main, cùng một số caller/test ranges. Auth/staff và hoàn tiền không tạo finding trùng; config phòng active dưới cơ sở inactive, room node category và permission revoke race còn held do impact end-to-end chưa chắc. Xem `blocks/round44.md`, `blocks/round44.coverage.json` và từng hồ sơ trong `PHAT-HIEN.json`.

Các test liên quan chỉ đọc, không chạy. Không truy cập app/API/DB/runtime/provider/VPS/production; không đọc secrets hoặc PHI. Report/ZIP QA chỉ xác nhận artifact bàn giao.
