# Triage vòng 14 — exact-main 956ba4f2

Ngày 20/10/2026. Chỉ triage các lát code tĩnh được giao và đọc trong snapshot `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Không chạy app, test, database, VPS, CI hoặc production; không truy cập secrets/PHI và không sửa code ứng dụng/migration.

## Đưa vào sổ phát hiện

- **API-004 — MEDIUM, confirmed_static.** Command `start/complete/skip/cancel` của work item kiểm tra clinic, quyền/role, gate và version nhưng không so `location_id` của visit/appointment liên kết với `StaffIdentity.location_id`, trong khi worklist lọc theo cơ sở. Kết luận giới hạn ở cùng clinic; không thấy cross-clinic bypass. Cần test tổng hợp hai cơ sở; item OPS không gắn lượt/lịch giữ policy locationless hiện có. Dedupe: khác side effect với API-001 (đổi thứ tự hàng đợi) và API-002 (đọc chi tiết workflow), nhưng liên quan cùng nhóm scope theo cơ sở.
- **FIN-015 — LOW, confirmed_static; tác động suy ra từ call chain.** Receipt transactional của thu dịch vụ không fingerprint `cong_ty_id`; replay cùng key vẫn chạy bước gắn snapshot bằng body hiện tại. Nếu cycle chưa có snapshot và caller tái dùng key với company khác, invoice export có thể dùng đơn vị mua mới. Không tạo lần thu thứ hai; UI hiện tại đưa company vào key, nên chưa có bằng chứng người dùng gặp đường này. Dedupe: khác INF-007, vốn là receipt lease bên ngoài transaction và có thể chạy lại side effect thu.
- **SEC-024 — LOW, confirmed_static.** Middleware ghi `str(exception)` vào trường telemetry `detail`, giữ tối đa 300 ký tự và endpoint `/ops/telemetry` trả trường đó cho `ops.view`. Không có scrubber trên buffer này; kho lỗi bền vững là sink riêng và có scrubber. Chưa chứng minh exception thật mang PII/PHI hay sự cố production; giữ giới hạn kết luận này. Dedupe: khác SEC-021 về sink, trigger và loại lỗi; cùng chủ đề data-minimization.

## Không tạo finding mới

- **RLS/grants:** hai permission views trùng trực tiếp SEC-017; các điểm liên quan function ACL đã có SEC-007/SEC-011/DB-001. Candidate đọc trực tiếp stock ledger không còn hiện diện trong source exact-main sau migration `20261019120000_restrict_stock_postgrest_reads.sql` trên 11 bảng. Không suy ra ACL đang hiệu lực trong database.
- **SECURITY DEFINER:** lát helper đã đọc tĩnh không tạo candidate mới; 72 định nghĩa trong migration scan có `SET search_path`, nhưng việc này không xác nhận owner/BYPASSRLS, grant thực tế hoặc tenant behavior tại runtime.
- Work-item BFF `reassign` mismatch và câu hỏi `mine_only` tiếp tục ở `STATE.json.held_observations`; không gộp thành API-004. API-004 chỉ nói command mutation thiếu predicate location cho item có visit/appointment.

Artifacts chi tiết: `round14_work_items.*`, `round14_payment_settlement.*`, `round14_rls_grants.*`, `round14_observability.*`. Các finding mới đã có source hash và line evidence được đối chiếu với snapshot. Coverage block ghi từng file/đoạn và mức đọc. Đây là checkpoint, không phải full source audit; việc đọc code và kiểm chứng runtime còn dang dở.

## Tiện ích lõi — không có finding mới

Lát `round14_core_primitives.*` đọc trọn 7 module được chọn (clock/date, chọn cơ sở, phone, mã vị trí, GS1, helpers quan sát, Sentry) và 5 test liên quan; thêm một đoạn test phone được đọc có mục tiêu. Không thấy candidate mới trong phần đã đọc. Test chỉ được đọc, không chạy. `main.py` vẫn gọi bootstrap Sentry khi có `SENTRY_DSN`, dù quy tắc dự án đánh dấu dịch vụ này đã chết; cấu hình trong code tắt PII mặc định/local variables/request body. Vì chưa biết env/runtime, ghi nhận đây là policy/configuration drift, không phải bằng chứng Sentry đang bật ở production. Caller phone/date và các module `core/` còn lại vẫn mở.
