---
title: "Multi-tenant thật — clinic_id trên 69 bảng, 45 policy, backend bỏ qua RLS nên CI đếm mọi câu lệnh"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "ADR-0009 · 20260730000003/4 · scripts/tests/tenant-scope-audit.py"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# Multi-tenant thật — clinic_id trên 69 bảng, 45 policy, backend bỏ qua RLS nên CI đếm mọi câu lệnh

> [!abstract] Governance ở tầng DB đã đúng; bài học 'RLS không bảo vệ backend' sinh ra audit ceiling = 0.

Bất biến CI đếm (GIAI-THICH-CODE §9.7): bảng có `clinic_id` = **69** · `NOT NULL` 0 ngoại lệ · FK tới `clinic` 0 ngoại lệ · `clinic_id` là cột dẫn đầu ít nhất một index · 7 bảng dùng chung không có `clinic_id` (`province, ward, staff, staff_capability, idempotency_key, schema_migrations, clinic`) · policy `%_select_own_clinic` = **45** · policy có `cmd <> 'SELECT'` = **0** · còn `USING (true)` = **0**.

Ba hàm danh tính `STABLE SECURITY DEFINER`: `current_staff_id()` → `current_clinic_ids()` → `current_clinic_roles(clinic)`. `default_clinic_id()` trả NULL ngay khi có tenant thứ hai — «gán nhầm sẽ báo lỗi chứ không âm thầm».

> «**RLS không bảo vệ được backend.** Tiến trình FastAPI nối DB bằng chủ sở hữu database, nên policy ở trên không áp cho nó: một câu lệnh đọc rộng đúng bằng mệnh đề WHERE của chính nó. Vì vậy mọi câu lệnh trong `src/clinicai` chạm bảng có tenant đều phải tự lọc `clinic_id`. Đã đưa từ 71 → 0; `tenant-scope-audit.py --check` chạy trong CI với ceiling = 0.» — *ADR-0009 W8*

Ba relay quét mọi tenant *có chủ đích* được liệt kê tường minh (`pos_relay`, `notification_relay`, `event_service`). `event_log` RLS: MANAGEMENT và trong tenant. `idempotency_key`, `clinic_secret`, `pos_outbox`, `mpi_merge_queue`, `staff_capability`: RLS bật, 0 policy = chỉ backend.

Bài học ghi trong ADR-0012 và GIAI-THICH-CODE: «RLS ENABLE mà không có policy nào = bảng rỗng, không phải bảng mở»; «View thiếu `security_invoker = true` là rò rỉ im lặng».

### Nghĩa cho thiết kế

Mọi bảng mới trong lớp 5 (`event_catalog`, `policy`, `expectation`, `experience_state`, `notification_delivery`, `event_quarantine`, `projection_checkpoint`) đi đúng khuôn: `clinic_id NOT NULL` + FK + index dẫn đầu + policy select own clinic (hoặc 0 policy nếu chỉ backend) + tự lọc trong mọi câu lệnh Python để audit ceiling giữ 0. [[tk-governance|Governance ở cấp event]] ghi rõ.

## Nối tới
- [[governance-event|Security, privacy, governance ở cấp event]]
- [[tk-governance|Governance ở cấp event]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[ci-guards|CI]]
- [[stack|Stack đang chạy]]

## Được dẫn từ
- [[macro-v3|Thesis v3]]
- [[governance-event|Security, privacy, governance ở cấp event]]
- [[stack|Stack đang chạy]]
- [[ci-guards|CI]]
- [[tk-governance|Governance ở cấp event]]
