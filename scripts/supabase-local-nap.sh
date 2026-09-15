#!/usr/bin/env bash
#
# Nạp lược đồ ClinicAI vào bộ Supabase tự dựng trên Mac.
#
#   SUPABASE_DB_CONTAINER=clinicai_thu_db ./scripts/supabase-local-nap.sh   # môi trường thử (dev-up.sh tự đặt)
#   SUPABASE_DB_CONTAINER=clinicai_db     ./scripts/supabase-local-nap.sh   # dựng mới database máy chủ
#
# CHỈ CHO DATABASE TRỐNG. Database đã có sổ migration thì script dừng — áp phần
# còn thiếu là việc của apply-pending-migrations.sh.
#
# CHẠY SAU KHI GoTrue ĐÃ KHỞI ĐỘNG XONG. Thứ tự bắt buộc, và lý do:
# baseline có `staff.auth_user_id → auth.users(id)`, mà bảng `auth.users` do
# GoTrue tạo. Chạy migration trước GoTrue là đổ ở dòng khoá ngoại ấy.
#
# Script này CHỈ dựng lược đồ. Đổ dữ liệu là bước riêng (Giai đoạn 2) — tách ra
# vì dựng lược đồ chạy lại được bao nhiêu lần cũng không sao, còn đổ dữ liệu thì
# không.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# KHÔNG CÓ ĐÍCH MẶC ĐỊNH. Trước 11/09 biến này mặc định `clinicai_db` — tên
# container của PROD — nên quên đặt biến trên máy có container ấy là chạy cả chuỗi
# migration vào database đang đón bệnh nhân. Cùng luật với
# apply-pending-migrations.sh: script đoán lấy đích là script có ngày sửa nhầm.
DB="${SUPABASE_DB_CONTAINER:-}"
if [ -z "$DB" ]; then
  echo "!! chưa chọn đích: đặt SUPABASE_DB_CONTAINER (xem đầu file)" >&2
  exit 2
fi
psql_() { docker exec -i "$DB" psql -U postgres -X -q -v ON_ERROR_STOP=1 "$@"; }

docker inspect "$DB" >/dev/null 2>&1 || { echo "!! chưa dựng $DB" >&2; exit 1; }

# Mỗi file migration chạy bằng `psql -f` KHÔNG bọc giao dịch: đổ ở dòng 40 thì 39
# dòng trước đã vào. Nạp lại lên database đã có lược đồ là để lại nửa migration.
if [ "$(psql_ -tAc "SELECT to_regclass('supabase_migrations.schema_migrations') IS NOT NULL" | tr -d ' ')" = "t" ] \
   && [ "$(psql_ -tAc "SELECT count(*) FROM supabase_migrations.schema_migrations" | tr -d ' ')" != "0" ]; then
  echo "!! $DB đã có sổ migration — script này chỉ dựng database TRỐNG." >&2
  echo "   Áp phần còn thiếu: CLINIC_DB_CONTAINER=$DB ./scripts/apply-pending-migrations.sh" >&2
  exit 1
fi

# GoTrue tạo schema `auth` bằng migration của chính nó lúc khởi động. Nạp lược đồ
# trước khi `auth.users` có mặt là đổ ở khoá ngoại staff.auth_user_id.
for _ in $(seq 1 120); do
  psql_ -tAc "SELECT to_regclass('auth.users') IS NOT NULL" 2>/dev/null | grep -q t && break
  sleep 1
done
psql_ -tAc "SELECT to_regclass('auth.users') IS NOT NULL" | grep -q t \
  || { echo "!! GoTrue chưa tạo auth.users sau 120 giây — xem log container auth" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Nâng auth.uid() / auth.role() để đọc được CẢ HAI dạng claim
# ---------------------------------------------------------------------------
# GoTrue tạo hai hàm này chỉ đọc GUC kiểu cũ `request.jwt.claim.sub`. PostgREST
# v12 với DB_USE_LEGACY_GUCS=false lại đặt `request.jwt.claims` dạng JSON. Để
# nguyên thì auth.uid() luôn trả NULL, `current_staff_id()` trả NULL, và MỌI
# policy đọc đều cho ra 0 dòng — triệu chứng là "đăng nhập được nhưng màn nào
# cũng trống", một lỗi rất khó lần.
#
# Thay bằng superuser: CREATE OR REPLACE GIỮ NGUYÊN chủ sở hữu, nên lần nâng
# cấp GoTrue sau vẫn thay được.
echo "==> nâng auth.uid() / auth.role()"
psql_ <<'SQL'
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
    )::uuid
$$;

CREATE OR REPLACE FUNCTION auth.role()
RETURNS text LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.role', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
    )::text
$$;
SQL

# ---------------------------------------------------------------------------
# 2. Chuỗi migration
# ---------------------------------------------------------------------------
echo "==> nạp $(ls "$ROOT"/supabase/migrations/*.sql | wc -l | tr -d ' ') migration"
docker cp "$ROOT/supabase/migrations" "$DB:/migrations" >/dev/null
docker exec "$DB" bash -c '
  set -e
  for m in /migrations/*.sql; do
    if ! psql -U postgres -q -v ON_ERROR_STOP=1 -f "$m" >/tmp/o 2>&1; then
      echo "ĐỔ tại $(basename "$m")"; grep -m3 ERROR /tmp/o; exit 1
    fi
  done'

# Đánh dấu đã áp, để `supabase db push` sau này không chạy lại từ đầu.
psql_ -c "CREATE SCHEMA IF NOT EXISTS supabase_migrations;
CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
    version text PRIMARY KEY, statements text[], name text);"
for m in "$ROOT"/supabase/migrations/*.sql; do
  v="$(basename "$m" | cut -d_ -f1)"
  psql_ -c "INSERT INTO supabase_migrations.schema_migrations (version)
            VALUES ('$v') ON CONFLICT DO NOTHING;"
done

# ---------------------------------------------------------------------------
# 3. Quyền cho các vai — chuỗi migration cấp theo policy, nhưng service_role
#    phải chạm được cả bảng chưa có policy nào (ADR-0012: backend là đường ghi).
# ---------------------------------------------------------------------------
psql_ <<'SQL'
GRANT ALL ON ALL TABLES    IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;
SQL

echo "==> xong. Kiểm nhanh:"
psql_ -c "select
    (select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE') as bang,
    (select count(*) from pg_policy) as policy,
    (select count(*) from information_schema.tables where table_schema='auth') as bang_auth,
    (select count(*) from supabase_migrations.schema_migrations) as migration;"
