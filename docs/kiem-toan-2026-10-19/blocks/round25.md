# Round 25 — static exact-main review

Snapshot `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Không chạy test ClinicAI, API/DB/provider/production; không dùng secrets hoặc hồ sơ bệnh nhân.

## Findings tích hợp

- `FE-025` (MEDIUM): lỗi duplicate check có thể hiển thị như không có kết quả; khác FE-012 (stale candidate sau khi input đổi).
- `API-006` (LOW): loại số điện thoại sai bị BFF chuẩn hóa thành CHINH; không có bằng chứng đường UI chuẩn gửi sai.
- `OPS-006` (LOW, điều kiện): retention=0 có thể prune mọi ngày backup CFS; chưa xác minh override trên VPS.
- `OPS-007` (LOW, design gap): chú thích `supabase/config.toml` mâu thuẫn runbook migration active; chưa có bằng chứng ai làm theo chỉ dẫn cũ.
- `CLIN-043` (MEDIUM): lock order đổi bác sĩ/undo check-in ngược nhau có thể deadlock khi cùng appointment chạy đồng thời; chưa có concurrent DB test.
- `LAB-002` (LOW): finalize có thể đóng task hiện tại trước khi triage dùng row cache cũ để tạo lại LAB_REVIEW khẩn; race chưa tái hiện.
- Mở rộng `FE-023`: pattern pending sau fetch reject có ở ThaiKy, BaoXepBacSi, DauUuTien và LichTrungCuaKhach.

## Chưa promote

Role capability so với doctor/signer identity còn cần owner nghiệp vụ; tenant test không chứng minh table nào đang tắt RLS; route metrics `/ops/su-kien` có thể thiếu clinic filter nhưng chưa có caller/policy nên giữ held; fixed-name container cleanup chưa gắn với prod; bootstrap warning thiếu caller context. Event/recovery slice không có finding mới ngoài INF hiện hữu. Release helper/backend mismatch không có production caller nên giữ held. Chi tiết và lý do giữ ở `STATE.json → held_observations`.

Đọc trọn `src/tests/test_tenant_scope_audit.py` (111 dòng): test kiểm tenant SQL predicate, chưa kiểm tra mọi table có RLS enabled; chưa chứng minh có table nào đang tắt RLS, nên tiếp tục held. Lát này không thêm finding.

Hashes, excerpt và trạng thái read/traced nằm trong `round25.coverage.json`; nguồn finding ở `round25_findings.json` và canonical `../PHAT-HIEN.json`.
