#!/usr/bin/env bash
#
# Nạp lược đồ ClinicAI vào bộ Supabase tự dựng trên Mac.
#
#   ./scripts/supabase-local-nap.sh
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
DB=clinicai_db
psql_() { docker exec -i "$DB" psql -U postgres -X -q -v ON_ERROR_STOP=1 "$@"; }

docker inspect "$DB" >/dev/null 2>&1 || { echo "!! chưa dựng $DB" >&2; exit 1; }

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
