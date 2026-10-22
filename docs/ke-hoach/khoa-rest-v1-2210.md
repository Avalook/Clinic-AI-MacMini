# KẾ HOẠCH (Mức 3) — Khoá `/rest/v1`, chỉ chừa đúng phần giao diện cần

22/10/2026 · **Tuyền đã duyệt KHOÁ HẲN** · Bước 1 xong (PR `claude/khoa-rest-v1`) ·
**chưa đụng staging/prod** — lệnh bước 2–4 ở mục 9.

## 1. Vấn đề, nói gọn

`/rest/v1` (PostgREST — dịch vụ của Supabase biến mỗi bảng Postgres thành một địa chỉ web) đang đi
ra Internet qua Caddy (`caddy/Caddyfile:191`). Ai có tài khoản đăng nhập (kể cả **đối tác** và **tivi
phòng chờ**) gọi thẳng được vào bảng. Chính sách đọc hiện chỉ hỏi "người này có thuộc phòng khám
không" (`clinic_id IN current_clinic_ids()`), **không hỏi vai**.

Đã kiểm 22/10 trên DB local (cùng migration, dữ liệu thử, giao dịch chỉ-đọc rồi ROLLBACK): tài khoản
`PARTNER` đọc được `patient` 70 dòng, `appointment` 51, `visit` 19, `payment` 1, `prescription` 2,
`staff` 21. Local có **117 bảng/view** `authenticated` đọc được. Nguồn: phát hiện C1–C5 trong
`docs/soat-he-thong-2210/4-lego-quyen.md` (PR #527).

**Chưa biết:** ACL thật trên prod (bản sao lưu dùng `--no-acl`, nên bản sao không cho thấy). Phải đo
ở bước 0 dưới đây.

## 2. Giao diện thực sự cần gì từ PostgREST (đã grep code, 22/10)

| Chỗ | Bảng · cột | Dùng khi |
|---|---|---|
| `src/dashboard/proxy.ts:141` | `staff` · `id` (lọc `auth_user_id`, `is_active`) | mỗi lần mở trang |
| `src/dashboard/app/(auth)/login/actions.ts:43` | `staff` · `id, primary_department, is_active, auth_user_id` | đăng nhập |
| `src/dashboard/app/(auth)/login/actions.ts:55` | `clinic_membership` · `clinic_id, role, is_active` | đăng nhập |

→ **Hai bảng: `staff`, `clinic_membership`, và chỉ HÀNG CỦA CHÍNH NGƯỜI ĐANG ĐĂNG NHẬP.**
Không có `.rpc(...)`, không còn `postgres_changes`. Hai nơi khác là **mã chết** (không ai nhập):
`lib/event-log.ts`, `lib/roster-names.ts`; `patients/check-phone` đã tắt. `grep rest/v1` trong
`src/` và `scripts/` không ra gì. Đăng nhập dùng `/auth/v1` (GoTrue), **không bị ảnh hưởng**.

## 3. Thiết kế (một migration, chỉ đổi quyền, KHÔNG đổi dữ liệu)

Dải giờ: `20261022900000`–`20261022999999` (soát trùng số với nhánh khác lúc viết).

1. `REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;` (gồm cả view — giải C4).
   Tương tự cho sequence. `ALTER DEFAULT PRIVILEGES … REVOKE` để bảng mới sau này **không tự mở**.
2. `GRANT SELECT (id, auth_user_id, is_active, primary_department) ON staff TO authenticated;`
   `GRANT SELECT (clinic_id, staff_id, role, is_active) ON clinic_membership TO authenticated;`
   — **không có cột CCCD, SĐT, ngày sinh, số CCHN** (giải C2).
3. Chính sách đọc của hai bảng đó thu về **chỉ hàng của mình** (`auth_user_id = auth.uid()`;
   membership theo `staff_id` của mình). Không lọc `is_active` — màn đăng nhập cần thấy hàng
   của mình kể cả khi đã nghỉ để báo đúng câu. Hai policy mới không gọi hàm `public` nào.
4. Thu `EXECUTE` mặc định của hàm cho `anon, authenticated` (PostgREST còn mở `/rpc/<hàm>`), trừ
   danh sách cho phép cố định — **5 hàm policy RLS còn gọi**, cả 5 chỉ trả thông tin về CHÍNH
   người gọi: `current_staff_id()`, `current_clinic_ids()`, `current_clinic_ids_for_roles(text[])`,
   `current_clinical_clinic_ids()`, `thu_ky_duoc_xem_khach(uuid,uuid)`. Giữ vì policy của ~130
   bảng khác vẫn để nguyên làm **lớp thứ hai**: lỡ sau này ai GRANT lại một bảng thì policy vẫn
   lọc đúng thay vì đổ lỗi. Thu khỏi `authenticated`: `clinic_hours_for_date`,
   `resolve_effective_cap(s)`, `la_ca_kham_bac_si`, `current_clinic_roles`, `read_prescription_draft`
   (không policy nào gọi; FastAPI gọi bằng chủ database nên không ảnh hưởng).
5. **Bài canh vĩnh viễn** (pytest): đọc `information_schema.role_table_grants` /
   `routine_privileges` của `anon, authenticated`, so với danh sách cho phép ở mục 2; thêm bảng mới
   mà tự mở là CI đỏ.

**Việc tách riêng, làm sau (không gộp):** bỏ `/realtime/v1` khỏi Caddy + dừng dịch vụ `realtime`
(C5 — app đã thôi dùng từ 27/09). Chặn hẳn `/rest/v1` ở Caddy khi gỡ nốt hai chỗ đọc `staff`/
`clinic_membership` sang FastAPI (Mức 2, đợt sau).

**Vì sao không chọn cách rẻ hơn** (chỉ thêm chính sách "vai ∉ PARTNER, DISPLAY"): nhanh hơn nhưng
~40 bảng vẫn lộ cho mọi nhân viên (thu ngân đọc được bảng phân quyền, CCCD đồng nghiệp). Khoá hẳn
còn **đơn giản hơn**, vì giao diện chỉ cần hai bảng.

## 4. Các bước

| Bước | Việc | Ai | Dừng nếu |
|---|---|---|---|
| **0** | Đo ACL thật trên prod (câu SELECT chỉ-đọc bên dưới), ngoài giờ cao điểm | Tuyền | — |
| **1** | Viết migration + bài canh + `rollback` (mục 5); PR nhỏ từ `origin/main` | Codex/Claude | CI máy đỏ |
| **2** | **Diễn tập** trên DB local nạp bản sao prod (`scripts/staging-tu-ban-sao.sh`): áp migration → chạy checklist mục 6 | AI | một mục đỏ |
| **3** | Staging (sau 21:30, kiểm load<2, RAM, đĩa như runbook): áp + bấm theo checklist, mọi vai | Tuyền chạy lệnh, AI soạn | đăng nhập lỗi / vai nào thấy rỗng |
| **4** | Prod: sao lưu → chụp ACL (mục 5) → áp **riêng, không lúc deploy** → checklist → theo dõi log 30 phút | Tuyền | xem mục 5 |

Câu đo ACL cho bước 0 (chỉ đọc):

```sql
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee IN ('anon','authenticated') AND table_schema='public'
ORDER BY 1,2,3;
```

## 5. Hoàn tác

- Migration **chỉ đổi quyền**, không sửa/xoá dòng nào → hoàn tác không mất dữ liệu.
- **Trước khi áp ở prod:** chụp ACL hiện tại ra tệp (`\dp public.*` + câu trên) và **sinh sẵn**
  `rollback.sql` = các lệnh `GRANT` đúng như đã chụp. Giữ ngoài thư mục `supabase/migrations/`;
  khi cần mới thêm thành migration MỚI (luật repo: DB chỉ đổi qua migration).
- Thời gian hoàn tác ước ~1 phút (áp một tệp SQL). Diễn tập hoàn tác ở bước 2: áp → rollback →
  kiểm ACL **về y hệt** bản chụp.
- **Dấu hiệu phải hoàn tác ngay:** đăng nhập báo "Tài khoản chưa gắn với nhân viên" / "phải có đúng
  một phòng khám"; vai nào vào thấy rỗng; log GoTrue/PostgREST nhiều `42501 permission denied`.

## 6. Checklist diễn tập / staging / prod

1. Đăng nhập **từng vai** (Quản lý, Lễ tân, Thu ngân, Bác sĩ, ĐD, Dược, TKYK, Đối tác, Tivi) → vào
   được trang chủ; mở 5 màn chính, **không** lỗi 4xx/5xx mới.
2. Đối tác/Tivi gọi `/rest/v1/patient|appointment|payment|visit|staff?select=*` → **403/rỗng**.
3. Nhân viên thường gọi `/rest/v1/staff?select=national_id_number` → bị từ chối; `?select=id`
   chỉ ra **đúng một hàng (của mình)**.
4. `/rest/v1/capability_grant`, `/rest/v1/payment_cycle`, `/rpc/clinic_hours_for_date` (và mọi
   hàm ngoài 5 hàm ở mục 3.4) → bị từ chối. `/rpc/current_staff_id` trả id của chính mình — chủ ý.
5. Tivi phòng chờ + màn Đối tác vẫn chạy (đi qua FastAPI, không qua PostgREST).
6. FastAPI, worker `su-kien`, sao lưu, `canh_bao` chạy bình thường (kiểm rằng chúng **không** dùng
   vai `authenticated`; cổng DB của API dùng tài khoản riêng).
7. Bấm ở 375 và 1280. Pytest: `scripts/test-nhanh.sh` bài canh mới + bài RLS cũ; sau cùng
   `./scripts/ci-may.sh --bao-github` (08:00–23:00).

## 7. Rủi ro chưa loại bỏ

| Rủi ro | Giảm bằng |
|---|---|
| Còn nơi đọc PostgREST mà grep không thấy (Uptime Kuma, script ngoài git, công cụ lạ cài 30/09) | Bước 0 + đọc log Caddy 7 ngày: đếm `/rest/v1` theo đường dẫn trước khi áp |
| Hàm chính sách mất `EXECUTE` làm RLS lỗi | Diễn tập bước 2 chạy đủ vai |
| Khách đang dùng lúc áp | Áp ngoài giờ cao điểm; migration chạy chỉ vài giây |
| ACL prod khác local | Bước 0; nếu khác, cập nhật kế hoạch trước bước 3 |

## 8. Cần Tuyền chốt

1. ~~Duyệt khoá hẳn hay chỉ chặn PARTNER/DISPLAY?~~ → **khoá hẳn** (Tuyền 22/10).
2. Bước 0: Tuyền chạy câu ACL trên prod, dán kết quả.
3. ~~Tách `/realtime/v1`?~~ → **việc sau**, không làm trong PR này.
4. Giờ áp lên staging / prod (khuyến nghị: sau 21:30, ngoài giờ khám).
5. Tắt tạm tài khoản Đối tác/Tivi cho tới khi khoá xong? (Đã phơi ra từ 30/07; nếu không có đối tác thật
   đang dùng token, có thể chưa gấp.)

## 9. Lệnh cụ thể cho bước 2, 3, 4 (Tuyền chạy — chép nguyên khối, không có chỗ phải điền)

Ba công cụ đi kèm PR (đều **chỉ đọc**):

| Công cụ | Làm gì |
|---|---|
| `scripts/chup-acl-rest.sh THƯ-MỤC` | chụp quyền anon/authenticated → `acl.txt` (để `diff`), `dp.txt` (để đọc), **`rollback.sql`** (đưa quyền về y hệt lúc chụp). Không ghi đè bản chụp cũ. |
| `scripts/kiem-khoa-rest.sql` | checklist mục 6 ý 2–4 ở tầng database, đóng vai tài khoản THẬT của từng vai (Đối tác, Tivi, Lễ tân, Thu ngân, Bác sĩ) — không cần mật khẩu. In ĐẠT/HỎNG; có HỎNG thì lỗi. |
| `scripts/kiem-khoa-rest-http.sh` | cùng checklist nhưng **qua đường thật** (Caddy → PostgREST). Hỏi tên đăng nhập + mật khẩu từng tài khoản muốn thử (gõ tay, không hiện). |

> **Bẫy đã gỡ trong PR này:** `staging-nap-ban-sao.sh` (staging, mỗi đêm 03:30) và
> `staging-tu-ban-sao.sh` (Mac) sau khi nạp bản sao đều `GRANT ALL ON ALL TABLES … TO
> authenticated`. Không sửa thì staging tự mở lại mỗi đêm. Nay cả hai áp lại migration khoá ngay
> sau đó (nếu code có tệp).

### Bước 2 — diễn tập trên Mac (DB local nạp bản sao prod)

Mở Terminal ở thư mục repo ClinicAI trên Mac.

```bash
git checkout main && git pull --ff-only
# Nạp bản sao đêm vào clinicai_thu_db. main CHƯA có khoá → đây đúng là trạng thái prod hiện giờ.
./scripts/staging-tu-ban-sao.sh --yes
git fetch origin claude/khoa-rest-v1
git worktree add ../khoa-rest-v1 origin/claude/khoa-rest-v1
cd ../khoa-rest-v1
CLINIC_DB_CONTAINER=clinicai_thu_db ./scripts/chup-acl-rest.sh ../acl-rest/dien-tap-truoc
# Thử khô: phải liệt kê ĐÚNG MỘT tệp 20261022900000_khoa_rest_v1.sql — khác thì dừng.
CLINIC_DB_CONTAINER=clinicai_thu_db ./scripts/apply-pending-migrations.sh
CLINIC_DB_CONTAINER=clinicai_thu_db ./scripts/apply-pending-migrations.sh --apply
docker exec -i clinicai_thu_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/kiem-khoa-rest.sql
ENV_FILE="$(git worktree list | head -1 | awk '{print $1}')/.env.thu-local" URL=http://127.0.0.1:54421 ./scripts/kiem-khoa-rest-http.sh
```

Bấm thật: mở http://127.0.0.1:3100, đăng nhập **từng vai** ở 375 và 1280 (checklist mục 6 ý 1, 5).

Diễn tập hoàn tác (phải ra "HOÀN TÁC TRÙNG KHÍT"), rồi khoá lại:

```bash
docker exec -i clinicai_thu_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < ../acl-rest/dien-tap-truoc/rollback.sql
CLINIC_DB_CONTAINER=clinicai_thu_db ./scripts/chup-acl-rest.sh ../acl-rest/dien-tap-sau-hoan-tac
diff ../acl-rest/dien-tap-truoc/acl.txt ../acl-rest/dien-tap-sau-hoan-tac/acl.txt && echo "HOÀN TÁC TRÙNG KHÍT"
docker exec -i clinicai_thu_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < supabase/migrations/20261022900000_khoa_rest_v1.sql
docker exec -i clinicai_thu_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/kiem-khoa-rest.sql
```

Test + CI (cùng thư mục worktree), rồi dọn:

```bash
./scripts/test-nhanh.sh src/tests/services/test_khoa_rest_v1_db.py src/tests/services/test_prescription_draft_privacy_db.py src/tests/services/test_order_authorization_db.py src/tests/services/test_tien_thuoc_cp1_db.py
./scripts/ci-may.sh --bao-github
cd "$(git worktree list | head -1 | awk '{print $1}')" && git worktree remove ../khoa-rest-v1
```

### Bước 3 — staging (sau 21:30, gõ từ Mac)

```bash
ssh clinic-vps-moi "uptime; free -h; df -h /"
```

Load (số đầu sau `load average`) > 2, RAM trống < 1 GB hoặc đĩa > 90% → dừng, để hôm khác.

```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && ./scripts/deploy-staging.sh claude/khoa-rest-v1"
ssh clinic-vps-moi "cd ~/clinicai-staging && CLINIC_DB_CONTAINER=clinicai_stg_db ./scripts/chup-acl-rest.sh ~/acl-rest/staging-truoc"
ssh clinic-vps-moi "cd ~/clinicai-staging && CLINIC_DB_CONTAINER=clinicai_stg_db ./scripts/apply-pending-migrations.sh"
ssh clinic-vps-moi "cd ~/clinicai-staging && CLINIC_DB_CONTAINER=clinicai_stg_db ./scripts/apply-pending-migrations.sh --apply"
ssh clinic-vps-moi "cd ~/clinicai-staging && docker exec -i clinicai_stg_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/kiem-khoa-rest.sql"
ssh -t clinic-vps-moi "cd ~/clinicai-staging && ENV_FILE=.env.staging URL=https://staging.dr4women.io.vn ./scripts/kiem-khoa-rest-http.sh"
```

Lệnh thử khô (dòng thứ 3) phải liệt kê đúng tệp `20261022900000_khoa_rest_v1.sql` (cùng các migration
khác của đợt, nếu đợt có) — lạ thì dừng. Bấm thật https://staging.dr4women.io.vn **mọi vai** theo
checklist mục 6 ý 1, 5, 7. Xem PostgREST/GoTrue có lỗi quyền mới không:

```bash
ssh clinic-vps-moi "docker logs --since 30m clinicai_stg_rest 2>&1 | tail -40; docker logs --since 30m clinicai_stg_auth 2>&1 | grep -ci error"
```

Sáng hôm sau (sau lần nạp lại 03:30) — khoá phải còn nguyên:

```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && docker exec -i clinicai_stg_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/kiem-khoa-rest.sql"
```

Hoàn tác staging (nếu cần):

```bash
ssh clinic-vps-moi "cd ~/clinicai-staging && docker exec -i clinicai_stg_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < ~/acl-rest/staging-truoc/rollback.sql"
```

### Bước 4 — prod (staging ĐẠT, PR đã merge vào `main`; sau 21:30)

Áp **riêng**, không cùng lúc deploy. Migration không đổi code app nên không cần deploy để có hiệu lực.

```bash
ssh clinic-vps-moi
```

Trên VPS:

```bash
cd /home/clinicai/clinicai
uptime; free -h; df -h /
# Ai đang gọi /rest/v1 (rủi ro mục 7). Chỉ được thấy /rest/v1/staff và /rest/v1/clinic_membership —
# thấy đường khác thì DỪNG, báo lại (có nơi đọc PostgREST mà grep không thấy).
docker logs --since 168h clinicai_prod-caddy-1 2>/dev/null | grep -o '"uri":"/rest/v1/[^"?]*' | sort | uniq -c | sort -rn | head -30
git fetch origin
SHA=$(git log origin/main -1 --format=%H -- supabase/migrations/20261022900000_khoa_rest_v1.sql)
git log --oneline -1 "$SHA"
git worktree add --detach /home/clinicai/wt-khoa-rest "$SHA"
PG_DUMP_BIN=scripts/pg-dump-qua-container.sh CLINIC_DB_CONTAINER=clinicai_db \
  BACKUP_ENV_FILE=.env.prod CLINIC_BACKUP_DIR=/home/clinicai/backups/clinicai \
  ./scripts/backup-db.sh
cd /home/clinicai/wt-khoa-rest
CLINIC_DB_CONTAINER=clinicai_db ./scripts/chup-acl-rest.sh /home/clinicai/backups/acl-rest-prod-truoc
# Thử khô: phải liệt kê ĐÚNG tệp 20261022900000_khoa_rest_v1.sql — có tệp khác thì DỪNG, hỏi.
CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh
```

Thử khô đúng thì áp và kiểm:

```bash
CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh --apply
docker exec -i clinicai_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/kiem-khoa-rest.sql
ENV_FILE=/home/clinicai/clinicai/.env.prod URL=https://dr4women.io.vn ./scripts/kiem-khoa-rest-http.sh
```

Bấm thật mọi vai trên https://dr4women.io.vn (375 + 1280), mở Tivi phòng chờ và màn Đối tác. Rồi
theo dõi 30 phút — dòng nào hiện ra là có ai bị từ chối ở `/rest/v1` (Ctrl+C để thoát):

```bash
docker logs -f --since 1m clinicai_prod-caddy-1 2>/dev/null | grep --line-buffered '"uri":"/rest/v1/' | grep --line-buffered -E '"status":(401|403)'
```

Xong thì dọn worktree (bản chụp ACL giữ lại trong `/home/clinicai/backups/acl-rest-prod-truoc`):

```bash
cd /home/clinicai/clinicai && git worktree remove /home/clinicai/wt-khoa-rest
```

**Hoàn tác prod** (~1 phút; dấu hiệu ở mục 5):

```bash
docker exec -i clinicai_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < /home/clinicai/backups/acl-rest-prod-truoc/rollback.sql
```

Sau đó chép `rollback.sql` thành một migration MỚI trong PR (luật repo: DB chỉ đổi bằng migration),
để lần nạp/khôi phục sau không khoá lại ngoài ý muốn.
