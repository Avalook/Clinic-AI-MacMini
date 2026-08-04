# Khôi phục dữ liệu khi hỏng

Gói Supabase Free **không có backup tự động và không có PITR** — bảng điều khiển
ghi thẳng `Last backup: No backups`. Cái che lưng duy nhất là bản `pg_dump` chạy
hằng đêm trên chính máy Mac mini.

## Đang có gì

| | |
|---|---|
| Lịch chạy | 02:00 mỗi ngày, `/Library/LaunchDaemons/com.dr4women.db-backup.plist` |
| Script | [`scripts/backup-db.sh`](../scripts/backup-db.sh) |
| Nơi lưu | `~/backups/clinicai/` (ngoài repo — repo này public, bản lưu chứa bệnh án thật) |
| Mỗi lần | 2 file: `*.sql.gz` (schema `public`) và `*_auth.sql.gz` (dữ liệu đăng nhập, **data-only**) |
| Mất tối đa | **24 giờ** dữ liệu — hỏng lúc 20:00 là mất cả ngày làm việc |

## Khôi phục

**Đích phải là một project Supabase mới**, không phải Postgres tự dựng. Lý do:
bản lưu `auth` là *data-only* (chỉ có `COPY`, không có `CREATE TABLE`), nên nó
chỉ nạp được vào nơi đã có sẵn schema `auth` của Supabase. Khôi phục vào Postgres
thường thì được toàn bộ dữ liệu lâm sàng nhưng **mất hết đăng nhập**.

```bash
# 1. Tạo project Supabase mới, lấy connection string (bỏ "+asyncpg" nếu copy từ .env)
DSN='postgresql://postgres:...@...supabase.com:5432/postgres'

# 2. BẮT BUỘC — không chạy bước này thì bản lưu KHÔNG nạp được
psql "$DSN" -f scripts/restore-preflight.sql

# 3. Nạp dữ liệu (chọn bản theo ngày)
B=~/backups/clinicai/clinicai_production_atfmxvdfnbeenrdbbllp_20260804_020003
gzcat "$B.sql.gz"      | psql "$DSN"
gzcat "${B}_auth.sql.gz" | psql "$DSN"

# 4. Đổi SUPABASE_URL / các key / DATABASE_URL trong .env.prod, rồi
./scripts/deploy-backend.sh prod
```

### Hai lỗi được phép bỏ qua

```
ERROR:  schema "public" already exists          ← vô hại
ERROR:  relation "auth.users" does not exist    ← chỉ xảy ra khi đích là Postgres
                                                  thường; project Supabase có sẵn
```

Bất kỳ lỗi nào khác là **dừng lại và đọc**, đừng chạy tiếp.

### Kiểm sau khi khôi phục

```bash
psql "$DSN" -c "
select 'staff='||(select count(*) from staff)
    ||' patient='||(select count(*) from patient)
    ||' appointment='||(select count(*) from appointment)
    ||' RLS='||(select count(*) from pg_policies where schemaname='public')"
```

`RLS` phải bằng **53**. Số 0 nghĩa là database khôi phục xong đang **mở toang** —
nhìn thì đủ dữ liệu, nhưng ai đăng nhập cũng đọc được bệnh án của mọi phòng khám.

Rồi đăng nhập thử **ít nhất một tài khoản mỗi vai** (bác sĩ, CSKH, lễ tân). Nếu
báo 403 khi ghi: `staff.auth_user_id` không khớp `auth.users.id` — tức bước 3
thiếu file `_auth.sql.gz`.

## Đã kiểm ngày 04/08/2026

Khôi phục thật bản lưu 02:00 vào một Postgres 17 trắng trong Docker:

| | |
|---|---|
| Trước khi sửa `f_unaccent` | **60 lỗi**, không dựng được bảng nào |
| Sau khi sửa | **2 lỗi** (cả hai vô hại ở trên) |
| Dữ liệu | 8/8 bảng khớp production từng dòng |
| RLS | **53/53** chính sách còn nguyên |

Lỗi cũ là `f_unaccent` không ghi rõ schema: `pg_dump` khôi phục với `search_path`
rỗng nên cột sinh `patient.full_name_unaccent` không giải được tên hàm, hỏng ở
bảng `patient` rồi kéo theo 55 lỗi phía sau. Sửa ở
[`20260804000009_f_unaccent_restorable.sql`](../supabase/migrations/20260804000009_f_unaccent_restorable.sql).

**Backup vẫn chạy suốt thời gian đó và dữ liệu bên trong vẫn đúng** — chỉ là
không nạp lại được, và không có gì báo cho tới ngày cần dùng.

## Còn hở, chưa làm

1. **Bản lưu chỉ nằm trên đúng ổ đĩa của máy Mac.** Mac hỏng là mất cả hệ thống
   lẫn bản lưu. Cần một bản chép sang nơi khác (ổ ngoài, hoặc R2/S3 — script đã
   có sẵn đường đẩy qua `rclone`, chưa cấu hình).
2. **FileVault đang Tắt.** Ổ đĩa không mã hoá, mà trong đó có bệnh án thật của
   bệnh nhân thật. Chỉ Quang bật được (cần mật khẩu máy).
3. **Mất tối đa 24 giờ.** Muốn ngắn hơn thì tăng số lần chạy trong ngày — dump
   chỉ 20MB nên chạy mỗi 6 giờ là rẻ.
4. **Chưa ai diễn tập khôi phục vào một project Supabase thật**, mới chỉ vào
   Postgres trắng. Phần `auth` là phần duy nhất chưa được kiểm đầu-cuối.
