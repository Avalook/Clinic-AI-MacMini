# Round 44 — clinical, auth, finance, configuration and recovery

Nguồn bằng chứng: Git SHA ghim `956ba4f236b1c92f1280d2097018c199e90ce8c7`, đọc qua `git show` trong worktree audit. Mọi kết luận code dưới đây là static source review; tests chỉ đọc, không chạy. Không gọi app/API/DB/provider/VPS/production, không đọc secrets/PHI.

## Kết quả

Round này thêm **CLIN-056** và **SEC-036**, đồng thời mở rộng **INF-006** và **INF-021**. Các điểm auth/staff và finance được dedupe với findings/audit notes hiện có; không nhân đôi mã.

- **CLIN-056 — MEDIUM:** `_approved_rows_unchanged` so tên/số lượng/liều/lưu ý nhưng không so `drug_catalog_id`. Với đơn còn nháp, nếu chỉ catalog ID đổi thì nó có thể trả `items=None`, khiến caller bỏ qua thay đơn. Điều kiện và giới hạn được ghi trong finding; chưa có kiểm tra DB hoặc incident.
- **SEC-036 — HIGH:** route duyệt kết quả gác `result.review.approve`; preset TKYK có quyền này. Hàng chờ gọi helper phạm vi bệnh nhân, nhưng lệnh review không gọi. Service ràng buộc result + patient + clinic và khóa hàng, nhưng không kiểm assignment; sau khi chốt, release gate trả `allowed=true`. Không chứng minh thông báo đã gửi hay truy cập chéo clinic.
- **INF-006 mở rộng:** đọc toàn bộ manifest/verify/restore/drill xác nhận restore public là riêng, auth companion chỉ được dùng để seed UUID trong drill chứ drill không khôi phục thông tin đăng nhập thật. Contract còn yêu cầu Supabase Cloud PITR/auth backup trong khi hệ thống được tài liệu hóa là self-hosted; đây là mismatch runbook cần làm rõ, không bằng chứng hiện tại mất backup.
- **INF-021 mở rộng:** các writer cấu hình phòng/cơ sở commit mutation rồi gọi audit qua bước riêng; thêm bằng chứng `set_room_active` và `update_location`.
- **Ứng viên giữ chờ:** phòng đang bật dưới cơ sở đã tắt; node workflow không dành cho phòng lọt qua create-room; race giữa revoke quyền cấu hình và mutation. Chưa nâng thành finding vì impact tích hợp/chính sách chưa đủ chắc.
- **Hoàn tiền:** FIN-004, INF-007 và FIN-016 vẫn khớp source và đã có hồ sơ. Huỷ phiếu dịch vụ có guard pending/completed refund; không nâng suy luận void thuốc thành finding. Đối soát ngân hàng/provider chỉ là policy hold nếu sản phẩm hứa tự động.
- **Auth/staff:** PII roster và revoke-cache đã được ghi trong audit note có sẵn; proxy GoTrue có rate controls theo source, nhưng spoofability của X-Forwarded-For chưa xác minh.

## Coverage và trạng thái

Hai mươi file được đọc toàn bộ và hash/line-count đối chiếu với blob main; các caller/test bổ sung có range riêng trong `round44.coverage.json`. Số trạng thái được tính từ `MAIN-PHAM-VI.json`, không quy đổi thành % hiểu hành vi. **Full source audit vẫn chưa hoàn tất.**
