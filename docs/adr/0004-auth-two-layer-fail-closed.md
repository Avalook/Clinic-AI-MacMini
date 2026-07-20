# ADR-0004 — Auth 2 lớp fail-closed: X-API-Key (service-to-service) + Supabase JWT per-staff (role server-suy); RLS chỉ cho đọc

| | |
|---|---|
| **Status** | Proposed (lớp 2 đã chạy ở patients/payment/ops/me — ADR chốt phủ 100% router) |
| **Date** | 2026-07-18 |
| **Deciders** | Quang (mô hình B chốt trong HANDOFF §2) |
| **Liên quan** | Design doc v5 §5.4, §6.1; `api/identity.py`; memory `identity-model-per-staff-login` |

## Context
Khảo sát 18-07 tìm thấy: (a) API-key middleware **fail-open** khi `BACKEND_API_KEY`
trống; (b) nguyên router staff/scheduling/queue/tools/orchestrator/brief/lab/voice
KHÔNG có JWT/role guard — ai cầm API key (tức mọi user dashboard bất kể vai) gọi được
cả DELETE /staff; (c) idempotency scope rỗng ở POST /appointments; (d) `tools.py` +
`/orchestrator/chat` là dev surface nhưng mount trong prod; (e) runtime prod đang publish
api:8000 ra host (drift so với compose). Mô hình đích đã chốt: 1 Supabase login/staff,
role = `staff.primary_department` suy từ JWT, bỏ role-picker.

## Decision
1. **Lớp 1** `X-API-Key`: giữ cho service-to-service (Next BFF → FastAPI), **fail-closed**
   — app từ chối boot ở `APP_ENV=production` khi `BACKEND_API_KEY` trống; bỏ nhánh
   fail-open trong middleware.
2. **Lớp 2** bắt buộc trên **100% endpoint nghiệp vụ**: `get_current_identity` (JWT →
   `staff.auth_user_id` → role) + `require_role(...)` theo ma trận permissions trong
   manifest module. Catalog read-only được miễn lớp 2 (vẫn sau lớp 1).
3. Idempotency scope luôn `(key, endpoint, actor_id-từ-JWT)` — cấm scope rỗng.
4. `tools.py`, `/orchestrator/chat`, `/docs|/openapi.json` **không mount ở production**
   (hoặc sau `require_role(MANAGEMENT)`).
5. RLS Supabase: browser chỉ SELECT theo policy; **không** policy ghi nào cho
   `authenticated` — mọi write qua backend. Per-role read model cho bảng PII nặng
   (đợt 3). Bật RLS cho `idempotency_key` ngay.
6. Redeploy để đúng posture "Caddy là service duy nhất publish port".

## Considered Options
| Phương án | Ưu | Nhược |
|---|---|---|
| **A (chọn) 2 lớp như trên** | phòng thủ theo lớp; role không giả mạo được từ client; đường di trú đã đi 60% | mỗi request 1 SELECT staff (~1 RTT) — chấp nhận ở 1 RPS, cache 60s nếu cần |
| B Chỉ JWT (bỏ API key) | ít key phải xoay | mất lớp chặn service-to-service khi JWT bug/lộ anon; CORS phải mở |
| C Session riêng tự quản | độc lập Supabase | tự xây auth = rủi ro lớn hơn lợi |

## Consequences
**Tích cực:** đóng toàn bộ auth gap đã liệt kê; audit "ai làm gì" đúng người thật.
**Tiêu cực:** phải hoàn tất cutover #1b/#1c (link `auth_user_id` cho mọi staff, FE đọc
`/me`, xoá cookies legacy) trước khi siết — RUNBOOK đã có checklist; các call nội bộ
(cron, script) cần service-JWT hoặc đường riêng có ghi nhận.
