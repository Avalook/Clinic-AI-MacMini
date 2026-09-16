---
title: "CI — 5 job, ratchet chỉ được hạ, 24 SQL test, 163 pytest, 63 test dashboard"
lop: 3
lop_ten: Code đang chạy
tag_nguon: ".github/workflows/ci.yml · SO-LUAT Luật 12.5"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# CI — 5 job, ratchet chỉ được hạ, 24 SQL test, 163 pytest, 63 test dashboard

> [!abstract] 'Luật không có người canh thì không phải luật' — đây là người canh; mọi bất biến mới của thiết kế đích phải có một dòng ở đây.

Năm job:
- **backend**: ruff lint + `ruff format --check` (hay quên) · mypy `src/` · `tenant-scope-audit.py --check` (ceiling **0**) · pytest unit `--cov-fail-under=80` (hiện ~79,8%, cổng thực 79,5 vì làm tròn).
- **frontend**: tsc · eslint `--max-warnings=0` · `test:audit` · `test:ops` · **`test:boundary`** (service-role allowlist trần 2, chỉ được hạ; ratchet `[..px]` trần 102; route chạm DB trần 42) · `next build`.
- **infra-safety**: smoke test hạ tầng.
- **portability**: cấm `/Users/…` trong compose/env · compose resolve từ example · build 2 image `linux/amd64` · chạy thật `/health` + `/health/db`.
- **database**: Postgres 17 dùng một lần · «Migrations and seed must be plain SQL» (chặn `\restrict`, `FROM stdin`) · áp toàn bộ migration · **áp lần hai** mọi migration từ `20260730` (idempotent) · 24 SQL assertion (`multi_tenant_foundation.sql` đếm 69/45/0, `tenant_scoped_rls.sql`, `role_scoped_clinical_read.sql`, `workflow_kernel.sql`…).

Test đáng nhớ: `test_middleware_order` (Starlette đăng ký ngược); `test_doc_dung_cot_da_chon.py` («capacity_service đọc cột không SELECT, cả bộ test xanh, staging vỡ»); `test_ly_do_huy_drift.py`, `test_audit_labels_drift.py`; `px-tu-che-ratchet-boundary.test.mts`; `kiem-vang.sh` 286 test/1,3s flow sống còn.

> «Canh chuỗi cứng thì đổi code là biểu thức trượt, và bài kiểm ngừng kiểm mà vẫn xanh […]. Canh quan hệ thì sống qua thay đổi: "router nào cầm idempotency_guard phải có chốt thả khoá" bắt được cả endpoint thứ năm chưa ra đời. Mỗi bài kiểm mới phải thử ngược.» — *SO-LUAT Luật 12.5*

### Bất biến mới thiết kế đích sẽ đưa vào đây

1. `event_log` không có INSERT trực tiếp ngoài `ghi_su_kien()` — grep ceiling từ 29 → 0 ([[tk-emit-function|ghi_su_kien()]]).
2. Mọi `event_type` xuất hiện trong code phải có dòng `event_catalog` (mở rộng drift test).
3. Mỗi UPDATE `status` của `appointment/visit/work_item` phải đi kèm đúng một event cùng transaction — SQL test đếm cặp trên fixture.
4. `work_item` PENDING/IN_PROGRESS không có `owner` hoặc `assigned_queue` = 0 (sau Phase A).
5. Timer: SQL test «expectation quá hạn không FIRED sau một vòng worker = đỏ».
6. Projection rebuild: test xoá view rồi dựng lại cho kết quả bằng nhau.
Chi tiết: [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']].

## Nối tới
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-event-catalog-table|event_catalog]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[decision-checklist|Decision checklist cho mọi feature]]

## Được dẫn từ
- [[decision-checklist|Decision checklist cho mọi feature]]
- [[stack|Stack đang chạy]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
