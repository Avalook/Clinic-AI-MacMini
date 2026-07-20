# HANDOFF — Dr4Women-MacMini (context bàn giao giữa 2 phiên Claude)

> Đọc file này để nối tiếp công việc. Nguồn sự thật kèm theo: `CLAUDE.md`,
> `docs/spec-clinic.md`, `supabase/README.md`, và memory dự án
> (`~/.claude/projects/.../memory/dr4women-macmini-folder.md`).

## 0. Bối cảnh 1 dòng
Folder này = bản **self-host sạch, nguồn-đơn** của ClinicAI (cả app chạy trên Mac mini
bằng Docker, data ở Supabase). Được TÁCH RA từ mớ cũ "2 link / 2 nhánh / 2 Supabase /
paste DB tay". Máy đang chạy CHÍNH LÀ Mac mini (`Mac-mini-cua-Quang`).

## 1. Đã làm trong phiên trước (đã commit trên nhánh `main`)

| Commit | Nội dung |
|---|---|
| `b96a8ee` | Tạo folder sạch (bỏ .git/node_modules/.next/.env → 22M). **Supabase chuẩn hoá:** gộp 62 migration → 1 baseline validated (`supabase/migrations/`), bỏ 3 bảng chết → **32 bảng**, seed lookup (no PII). Gỡ runner Python + tooling import Notion cũ. **Hạ tầng:** compose tham số hoá prod/staging + Caddy + worker + Uptime Kuma + Dozzle + cloudflared; `/health` api+dashboard; CI (ruff+mypy+pytest, tsc+lint+build) + CD (build→up→health→**rollback**); RUNBOOK. |
| `5e57d61` | **Phase 4 cụm #1a:** `src/clinicai/api/identity.py` — FastAPI verify JWT Supabase (HS256+JWKS) → map `staff.auth_user_id` → suy role từ `primary_department` + `require_role()` + `GET /api/v1/me`. **11 test.** Thay cookie `clinic_role` tự chọn (spoof được). |
| `8eed6cf` | **Phase 4 cụm #4:** migration `20260714000002` — trigger 2+1 slot-capacity + `pg_advisory_xact_lock` → **fix bug race overbook** (đã test 2-transaction đua → đúng 1 thắng). Frontend map lỗi 23514→409. |
| `8bce143` | **Phase 4 cụm #5:** port `callRank` → `src/clinicai/services/queue_order.py` (**9 test**) + `GET /api/v1/queue` (đọc DB, xếp sẵn, biên VN-day). `/queue` page render theo backend; QueueBoard bỏ sort. tsc frontend sạch. |

## 2. QUYẾT ĐỊNH đã chốt với Quang (giữ nguyên, đừng lật)
1. **Auth = mô hình B (mỗi người 1 tài khoản):** backend suy danh tính+vai TỪ JWT Supabase
   (link `staff.auth_user_id`), **bỏ role-picker**. (Cụm #1a là nền; #1b/#1c chưa làm.)
2. **CAP-01 (ngân sách phút) = ADVISORY**, KHÔNG chặn đặt lịch (Quang chốt 2026-07-03).
   Luật đặt lịch chính thức = **2+1 mỗi khung 15'** (đã thành net cứng DB ở cụm #4).
3. **DB đổi CHỈ qua Supabase CLI** (`supabase/migrations/` + `supabase db push`) — KHÔNG
   bấm tay trong dashboard. `supabase/README.md` mô tả cách apply.
4. **Nhánh:** `main`=prod, `staging`=staging. Data staging phải giả/ẩn danh (no PII thật).
5. **Không cần data** trong DB mới (Quang: bỏ đống 5000+ BN cũ). Schema-only + seed lookup.
6. **Không over-engineer** (spec §6): 1 node + Supabase, không sharding/multi-region/HA/k8s.

## 3. Còn lại (thứ tự ĐỀ XUẤT — trả lời cho "Trọng tâm=#3, Mức=Right-sized")
Làm nốt Phase 4 (mỗi cụm = dời logic + vá đúng đắn), rồi lớp reliability:

**A. Phase 4 — dời logic FE→BE (đang dở, đi từng cụm):**
- **#3 payment guard** → dùng `require_role` (#1a): thu ngân chỉ thu khi visit COMPLETED + đúng vai. *(gợi ý làm tiếp — bắt đầu DÙNG nền auth)*
- **#2 clinical write-guards** → backend: FINALIZED gate + `canWriteClinical` + ownership (BS chỉ ghi lịch của mình).
- **#1b/#1c** hoàn tất auth: admin-tooling link `auth_user_id` + Quang tạo login per-person; frontend gửi JWT + đọc `/me`, bỏ role-picker.
- **#6** MPI dedup (bỏ fallback frontend, dồn về FastAPI) + form-schemas backend-served.

**B. Reliability right-sized (lớp lên SAU, map vào System Design):**
- **Outbox → notification** (Zalo/Telegram nhắc lịch) — Bài 23 Notification + outbox pattern.
  Bảng `event_log` đã append-only → thêm 1 outbox consumer (worker đã có khung `clinicai/worker.py`).
- **Idempotency** cho POST tạo lịch/thanh toán (idempotency-key) — Bài 14.
- **Observability nhẹ:** request-id middleware + structured log (đã có structlog) + deep `/health/db`
  (đã có) → gắn Uptime Kuma monitors + cảnh báo Telegram — Bài 11.
- **Indexing** rà theo truy vấn nóng (queue/booking) — Bài 18. Đã có gin_trgm/unaccent cho search.

**C. Ops trên Mac (Quang/tay):** tạo Supabase prod+staging project mới → `supabase db push`;
FileVault; PITR + test restore; đăng ký self-hosted runner; Cloudflare/Tailscale tunnel; test reboot thật.

## 4. System Design — bài nào ÁP, bài nào BỎ (right-sized)
**ÁP:** Bài 35 (Ticket Booking = concurrency đặt chỗ, đúng cụm #4) · Bài 23 (Notification/outbox) ·
Bài 10 (Reliability patterns: retry/timeout/circuit right-sized) · Bài 11 (Observability nhẹ) ·
Bài 14 (idempotency/transaction) · Bài 18 (indexing) · Bài 4/5 (API/DB nền).
**BỎ (quá quy mô):** Bài 12 HA/replication · 13 Sharding · 15 Consensus · 16/17 nặng ·
20 Multi-region · 24/25/26 Chat/Feed/Video · 28/29/31/32/33 case study lớn. Supabase đã lo
replication/backup; 1 node nên không cần LB/CDN/consensus.

## 5. Cách VERIFY trong folder này (đã dùng, chạy được)
- **Backend test/lint:** venv có sẵn deps:
  `VBIN=/Users/quangdang/Library/Caches/pypoetry/virtualenvs/clinicai-QNA9VmYd-py3.12/bin`
  `PYTHONPATH=src $VBIN/python -m pytest src/tests/test_identity.py src/tests/test_queue_order.py -q`
  `$VBIN/ruff check src/... ; PYTHONPATH=src $VBIN/mypy src/...`
- **Test SQL/migration + concurrency:** docker `postgres:17-alpine` tạm + shim
  (roles anon/authenticated/service_role + schema `auth` + `auth.users` + `auth.uid()`),
  apply `supabase/migrations/*` theo thứ tự, rồi psql/asyncpg. (Baseline + trigger đã pass vậy.)
- **tsc frontend** (folder chưa có node_modules): symlink tạm
  `ln -s "/Users/quangdang/Projects/AI Clinic Dr4Women/Clinic-AI-Dr4Women/src/dashboard/node_modules" src/dashboard/node_modules`
  rồi `SKIP_ENV_VALIDATION=1 node_modules/.bin/tsc --noEmit` (nhớ xoá symlink sau).
- **Compose:** `docker compose --env-file .env -p clinicai_prod config -q` (validate).

## 6. Bẫy đã gặp (đừng dẫm lại)
- Biến PL/pgSQL trùng tên cột (`is_walkin`) → ambiguous. Đặt prefix `v_`.
- `pg_dump --schema=public` KHÔNG kèm CREATE EXTENSION → cần migration `..._extensions.sql` trước.
- `f_unaccent` phải qualify `public.unaccent('public.unaccent'::regdictionary, ...)` (search_path='' lúc build index).
- appointment **append-only** (chặn DELETE) — reset test bằng bác sĩ mới, không DELETE.
- Supabase JWT: dự án mới thường ES256/JWKS (không secret) — `identity.py` đã hỗ trợ cả HS256 lẫn JWKS.
