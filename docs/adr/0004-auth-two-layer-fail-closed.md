# ADR-0004 — Auth 2 lớp fail-closed: X-API-Key (service-to-service) + Supabase JWT per-staff (role server-suy); RLS chỉ cho đọc

| | |
|---|---|
| **Status** | **Accepted** 2026-07-30 — Quang chốt "login riêng làm từ giờ luôn" + "siết RLS". Không còn giai đoạn chờ: cutover per-staff login và siết RLS làm trong đợt này. |
| **Date** | 2026-07-18 (accepted 2026-07-30) |
| **Deciders** | Quang (mô hình B chốt trong HANDOFF §2) |
| **Liên quan** | Design doc v5 §5.4, §6.1; `api/identity.py`; memory `identity-model-per-staff-login`; ADR-0009 (RLS theo tenant), ADR-0012 (hợp đồng backend) |

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

## Trạng thái thực hiện (cập nhật 2026-07-30)
- **Xong (W3)** — `supabase/migrations/20260730000004_tenant_scoped_rls.sql`:
  26 policy `USING (true)` bị thay bằng `clinic_id IN (SELECT current_clinic_ids())`
  (23 bảng) + `staff` theo `clinic_membership` + `event_log` giữ MANAGEMENT **và** thêm
  ràng buộc tenant. `province`/`ward` (danh mục hành chính quốc gia, không có PII) cố ý
  giữ mở. Ghi vẫn **0 policy** — mọi ghi qua backend.
- **Chặn trước khi áp:** migration `RAISE EXCEPTION` nếu còn nhân viên `is_active` chưa
  có `auth_user_id`, hoặc chưa có `clinic_membership`. Không có chuyện áp nửa chừng rồi
  khoá cả phòng khám ra ngoài.
- **Bất biến tự giữ:** trigger `staff_ensure_default_membership` tạo membership ngay khi
  insert `staff`, bất kể đường nào (StaffService, UI admin, SQL tay).
- **Lỗ đã bịt tiện thể:** `idempotency_key` là bảng duy nhất **tắt hẳn RLS** trong
  `public`, mà nó lưu request/response đã replay (có payload bệnh nhân). Supabase mặc
  định cấp SELECT cho `authenticated` ⇒ ai đăng nhập cũng đọc được. Nay bật RLS, không
  policy, `REVOKE` khỏi `anon`/`authenticated`.
- **Tài khoản dùng chung (`CLINIC_SHARED_EMAIL`, màn `/enter`)** không còn đọc được gì:
  nó không có dòng `staff` nên `current_clinic_ids()` rỗng ⇒ 0 dòng ở mọi bảng. Cổng vẫn
  còn để vào được trang `/login`; **bỏ hẳn cổng này là quyết định của bạn**, vì nó đổi
  cách cả phòng khám đăng nhập.
- **Còn lại (W5):** siết theo **vai trò** trong cùng phòng khám (Lễ tân/Thu ngân đọc
  `clinical_record` ra 0 dòng — DOD ROLE-02). Chưa làm được vì `/tasks` đọc `lab_result`
  + `prescription` và `/home` đọc `clinical_record` + `payment` bằng chính session người
  dùng, từ những màn mà Lễ tân/Thu ngân được vào. Phải dời các lệnh đọc đó ra sau FastAPI
  (ADR-0012) rồi mới siết được, nếu không chỉ làm trắng màn hình.
