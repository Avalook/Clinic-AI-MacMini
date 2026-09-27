# Bàn giao Phase C — cho agent/model khác chạy tiếp

Viết ngày 2026-08-02, sau khi C.3 lên PR #14. File này tồn tại để một model
khác (rẻ hơn) làm tiếp mà không phải đọc lại toàn bộ repo.

Plan gốc: `/Users/quangdang/.claude/plans/glimmering-chasing-sunset.md`
Spec: `docs/spec-clinic.md` · Luật chung: `CLAUDE.md`

---

## Trạng thái

| Item | Trạng thái |
|---|---|
| A.5 clinic_secret | PR #9, chưa merge |
| A.6 active-clinic + X-Clinic-ID | PR #10, #11, chưa merge |
| A.7 event_log.actor_staff_id | PR #8, chưa merge |
| A.8 gate CI derive-đừng-pin | PR #7, chưa merge (chờ đổi required status checks) |
| A.9 xoá /enter | ✅ xong 05/08/2026 — route, action và mọi tham chiếu đã gỡ |
| B.3 đường ghi nhà thuốc | PR #12, chưa merge |
| B.4 màn read-only | PR #13, chưa merge |
| **C.3 ClinicPolicy** | **PR #14, chưa merge** |
| C.1 provisioning | **chưa làm — làm tiếp ở đây** |
| C.2 xoá trigger membership | chưa làm, phụ thuộc C.1 |
| C.4 chuỗi thương hiệu | chưa làm, độc lập |
| C.5 provision phòng khám #2 trên VPS | **chặn: chưa có VPS** |

Các PR đang xếp chồng (stacked). Đừng rebase lung tung — đọc `gh pr view <n>`
xem base branch trước.

---

## Quy ước BẮT BUỘC (vi phạm là CI đỏ)

Đây là những thứ đã làm CI đỏ 6 lần liên tiếp. Không phải góp ý.

1. **Schema chỉ đi qua `supabase/migrations/*.sql`.** Không sửa schema bằng tay
   trên dashboard Supabase. Migration mới phải **re-appliable** (chạy 2 lần
   không lỗi) — `run-local.sh` áp lại toàn bộ migration từ `20260730000000` trở
   đi lần thứ hai.
2. **Không sửa migration đã ship.** Sai thì viết migration *tiến*.
3. **Router mỏng, logic ở service.** Không có business rule trong TSX.
   Frontend chỉ nói chuyện thẳng với Supabase cho **auth + realtime**.
4. **Service nhận `pool`**, dùng `async with pool.acquire()` + `conn.transaction()`.
   Lỗi ném từ `clinicai.api.exceptions`: `NotFoundError`(404) /
   `ValidationError`(422) / `ConflictError`(409).
5. **`StaffIdentity(staff_id, auth_user_id, full_name, department, role, clinic_id)`** —
   `clinic_id` luôn suy từ membership, KHÔNG nhận từ body. `X-Clinic-ID` chỉ là
   *bộ chọn* khi có nhiều membership, không phải *thẩm quyền*. Xem
   `src/clinicai/api/identity.py`.
6. **Sai tenant thì trả 404, không trả 403.** ID là UUID → 403 biến chúng thành
   oracle dò phòng khám bên cạnh.
7. **`event_log`**: cột `(clinic_id, event_type, aggregate_type, aggregate_id,
   payload, metadata, source, actor_staff_id, event_published)`. **Không có chữ
   lâm sàng/PHI trong `payload`.** Bảng append-only.
8. **Bảng mới có `clinic_id`** thì phải: `NOT NULL`, **không column default**,
   FK tới `public.clinic`, index dẫn đầu bằng `clinic_id`, RLS bật, SELECT
   policy chứa `current_clinic_ids`, và `GRANT SELECT` cho `authenticated` **khi
   và chỉ khi** có policy đó. Gate `supabase/tests/tenant_invariants.sql` (A.8)
   suy ra danh sách bảng, không pin tên.
9. **DB có 0 policy INSERT/UPDATE/DELETE** — cố ý. Trình duyệt không ghi
   Postgres được. Đường ghi = FastAPI.
10. **Next 16**: route group `(auth)`/`(dashboard)`; param động của API route là
    `Promise<{...}>`; **xoá `.next/types` sau khi thêm/xoá route** nếu không
    `tsc` chết vì validator cũ. Đọc `node_modules/next/dist/docs/` trước khi
    viết — bản này khác bản trong training data.
11. **tsconfig target ES2017** — regex cờ `/s` (dotAll) là lỗi biên dịch TS1501.
12. **Secret chỉ ở `.env.prod`/`.env.staging` + GitHub Actions secrets.**
    Repo này PUBLIC.
13. **`supabase/fixtures/clinic_roster.sql` (35 người thật) cố ý nằm NGOÀI git.**
    Đừng `git add` nó.

---

## Cách chứng minh việc đã xong

Chạy đủ, đừng chạy một cái rồi bảo xong:

```bash
poetry run pytest src/tests/ -q
poetry run mypy src/clinicai
poetry run ruff check src/
python3 scripts/tests/tenant-scope-audit.py --check

cd src/dashboard
rm -rf .next/types && npx tsc --noEmit
npx eslint --max-warnings=0
npm run test:boundary
npm run build

bash supabase/tests/run-local.sh        # cần Docker; áp migration lên postgres:17 thật
```

**Boundary test là bắt buộc cho mỗi item.** Kiểu test ở đây: quét NGUỒN bằng
`readFileSync`, **suy ra** danh sách thay vì ghim tên file, và so **chuỗi chính
xác giữa hai ngôn ngữ** khi một luật sống ở cả SQL lẫn TS/Python. Mẫu tốt nhất
để copy: `src/dashboard/tests/booking-policy-boundary.test.mts` (C.3) và
`src/dashboard/tests/service-role-boundary.test.mts`.

**Mutation testing là điều kiện nghiệm thu**, không phải tuỳ chọn: cố tình tái
phạm đúng cái bug vừa sửa, chứng minh test đỏ, rồi khôi phục. **KHÔNG dùng
`git checkout --` để khôi phục** — cây làm việc đang có việc chưa commit.
Snapshot/restore *nội dung file* bằng Python. Mẫu:
`scratchpad/mutate_policy_boundary.py` trong session C.3 (đã mô tả trong PR #14).

---

## C.1 — provisioning_service.py (việc tiếp theo)

**Vấn đề:** tạo phòng khám #2 hôm nay = ~12 bước INSERT thủ công, không script,
không transaction. `supabase/seed.sql` nhúng UUID Dr4Women 116 lần. Làm nửa vời
tệ hơn không làm: khách #20 sẽ thiếu node catalogue / bảng giá / admin đầu tiên
và phát hiện lúc 8h sáng ngày khám đầu tiên.

**Phải giao:**

1. `src/clinicai/services/provisioning_service.py` — **MỘT transaction** dựng:
   `clinic` → `clinic_location` → node catalogue (tham số hoá từ
   `supabase/migrations/20260730000006_seed_node_catalogue.sql`, đang hardcode
   UUID Dr4Women) → `service_type` + bảng giá → `staff` MANAGEMENT đầu tiên →
   `clinic_membership` → `clinic.settings` mặc định.
   `clinic.settings.booking` phải hợp lệ theo CHECK constraint mà C.3 vừa thêm
   (`supabase/migrations/20260803000001_clinic_booking_policy.sql`) — cách an
   toàn nhất là **không ghi `settings`**, để column default lo.
2. `POST /v1/admin/clinics` — router mới, chưa tồn tại (`src/clinicai/api/v1/routers/`
   chưa có `admin.py`). Chỉ MANAGEMENT. Nhớ `idempotency_guard` như
   `booking.py:73-105` — gọi lại không được thành hai phòng khám.
3. `scripts/provision-clinic.sh --code CLINIC2 --name "..." --admin-email a@b.vn`

**Test:** `supabase/tests/` một file SQL chứng minh phòng khám vừa provision
thoả **đúng những gì `scripts/tests/tenant-scope-runtime-check.py` đòi** —
script đó đã dựng phòng khám #2 thật để chứng minh cách ly, dùng lại nó thay vì
viết mới.

**Cái dễ làm sai:** transaction nửa vời. Nếu bước 5 hỏng mà bước 1–4 đã commit,
kết quả là một phòng khám tồn tại nhưng không dùng được, và lần chạy lại sẽ đụng
UNIQUE. Một `conn.transaction()` bao trọn, hoặc không làm.

---

## C.2 — xoá trigger `staff_ensure_default_membership`

Trigger nằm ở `supabase/migrations/20260730000004_tenant_scoped_rls.sql`, được
nhắc lại ở `20260730000014_drop_clinic_id_default.sql`, và
`src/clinicai/api/identity.py` có tham chiếu.

**Nó tự vô hiệu ngay khi có phòng khám thứ hai** — nhân viên mới sẽ vào app
trống trơn, không báo lỗi gì. Hôm nay (1 phòng khám) nó vẫn còn tác dụng, nên
đây là thời điểm cuối cùng xoá nó còn miễn phí.

Việc: migration *tiến* drop trigger; `StaffService.create_staff` nhận
`clinic_id` **bắt buộc**; thêm assertion CI: **0 staff không có membership**.
Phụ thuộc C.1 (không có đường tạo membership tử tế thì đừng xoá trigger).

---

## C.4 — chuỗi thương hiệu từ `clinic.settings`

**CHỈ ~8 chuỗi thương hiệu** (tên, logo, hotline, địa chỉ). **KHÔNG phải i18n** —
2.385 dòng tiếng Việt trong 165 file cố ý giữ nguyên, thị trường là Việt Nam.

Chỗ cần sửa: `src/dashboard/app/layout.tsx:19-20`, `DisplayBoard.tsx:148`, và 2
template in (`app/(dashboard)/print/`).

Mẫu để copy nguyên: **C.3 vừa làm đúng việc này cho luật đặt lịch** —
`src/dashboard/lib/booking-policy.ts` (đọc từ backend, không có mặc định),
`app/(dashboard)/BookingPolicyContext.tsx` (phát xuống cây), `layout.tsx` (đọc
một lần ở server). Brand khác một điểm: **thiếu brand thì có mặc định được**
(hiện tên chung), vì thiếu logo không làm ai đặt nhầm giờ. Thiếu luật đặt lịch
thì không.

---

## Đang chặn, đừng cố

- **C.5** cần VPS (A.1) — chưa dựng.
- **Task #8** (đổi required status checks của branch protection `main` sang
  `["backend","frontend","infra-safety","portability","db_fresh","db_replay"]`)
  cần Quang chạy tay:
  ```bash
  gh api -X PUT repos/:owner/:repo/branches/main/protection --input <file.json>
  ```
- **Merge các PR đang chồng** — thứ tự và base branch cần người quyết.
