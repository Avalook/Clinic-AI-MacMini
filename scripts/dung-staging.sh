#!/usr/bin/env bash
# Dựng (hoặc dựng lại) môi trường STAGING trên máy chủ — TÁCH HẲN khỏi bản
# phòng khám đang chạy thật.
#
# VÌ SAO CÓ FILE NÀY. Tách được ứng dụng thì dễ: compose đã tham số hoá
# prod/staging từ lâu. Nhưng nếu hai bên dùng CHUNG database thì staging không
# tách gì cả — một migration thử nghiệm hay một lần xoá dữ liệu là chạm thẳng
# vào phòng khám. Nên staging có bộ Supabase RIÊNG: database riêng, khoá JWT
# riêng, cổng riêng.
#
# BA THỨ PHẢI KHÁC NHAU, thiếu một là hỏng cách ly:
#   1. SUPABASE_PREFIX      — tên container (tên toàn cục trên máy chủ)
#   2. SUPABASE_JWT_SECRET  — token của bên này KHÔNG đọc được dữ liệu bên kia
#   3. SUPABASE_GATEWAY_HOST — Caddy chuyển /auth /rest /realtime về ĐÚNG bộ
#      của mình. Ghi cứng tên gateway prod là staging gọi vào database khách.
#
# Đã đo ngày 07/08/2026: token prod đọc dữ liệu staging → 401
# JWSInvalidSignature, và ngược lại. Đó là bảo đảm thật, không phải lời hứa.
#
#   ./scripts/dung-staging.sh            # dựng / cập nhật staging
#   ./scripts/dung-staging.sh --gieo     # dựng lại cả dữ liệu thử
#
# CHẠY TRÊN MÁY CHỦ (ssh clinic-vps), không phải trên máy cá nhân — script
# dùng docker của máy đang gõ lệnh.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

ENV_FILE=".env.staging"
SB_PROJECT="clinicai_stg_db"
APP_PROJECT="clinicai_staging"

[ -f "$ENV_FILE" ] || {
  echo "!! thiếu $ENV_FILE. Xem .env.staging.example và ba biến bắt buộc ở đầu file này." >&2
  exit 1
}

# Cách ly phải kiểm TRƯỚC khi dựng, không phải sau.
for bien in SUPABASE_PREFIX SUPABASE_JWT_SECRET SUPABASE_GATEWAY_HOST; do
  grep -qE "^${bien}=." "$ENV_FILE" || {
    echo "!! $ENV_FILE thiếu $bien — không có nó thì staging KHÔNG tách khỏi prod." >&2
    exit 1
  }
done
for bien in SUPABASE_JWT_SECRET SUPABASE_DB_PASSWORD BACKEND_API_KEY; do
  a="$(grep -E "^${bien}=" "$ENV_FILE" | cut -d= -f2-)"
  b="$(grep -E "^${bien}=" .env.prod 2>/dev/null | cut -d= -f2- || true)"
  [ -n "$b" ] && [ "$a" = "$b" ] && {
    echo "!! $bien của staging TRÙNG prod. Sinh khoá riêng, nếu không token đi chéo được." >&2
    exit 1
  }
done

echo "==> [1/4] bộ Supabase riêng của staging"
docker compose --env-file "$ENV_FILE" -f docker-compose.supabase.yml -p "$SB_PROJECT" up -d

DB="$(grep -E '^SUPABASE_PREFIX=' "$ENV_FILE" | cut -d= -f2-)_db"
for _ in $(seq 1 40); do
  docker exec "$DB" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done

echo "==> [2/4] lược đồ"
docker cp supabase "$DB":/sb >/dev/null
docker exec "$DB" sh -c '
  P="psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres"
  $P -f /sb/tests/bootstrap_plain_postgres.sql >/dev/null 2>&1 || true
  for m in /sb/migrations/*.sql; do $P -f "$m" >/dev/null 2>&1 || exit 1; done
  $P -c "CREATE SCHEMA IF NOT EXISTS supabase_migrations;
         CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations(
           version text primary key, statements text[], name text);" >/dev/null
'
for f in supabase/migrations/*.sql; do
  b="$(basename "$f" .sql)"
  docker exec "$DB" psql -q -U postgres -d postgres -c \
    "INSERT INTO supabase_migrations.schema_migrations(version,name)
     VALUES ('${b%%_*}','${b#*_}') ON CONFLICT DO NOTHING" >/dev/null
done
echo "    $(ls supabase/migrations/*.sql | wc -l | tr -d ' ') migration"

if [ "${1:-}" = "--gieo" ]; then
  echo "==> [2b] dữ liệu thử"
  for f in seed.sql fixtures/staff_logins.sql fixtures/local_data.sql \
           fixtures/demo_clinic_day.sql; do
    [ -f "supabase/$f" ] || continue
    docker exec "$DB" psql -q -U postgres -d postgres -f "/sb/${f}" >/dev/null 2>&1 \
      && echo "    OK  $f" || echo "    bỏ qua  $f"
  done
  # Seed bật lại toàn bộ danh mục dịch vụ; thu về đúng năm loại khám.
  docker exec "$DB" psql -q -U postgres -d postgres \
    -f /sb/migrations/20260807000007_nam_dich_vu_kham.sql >/dev/null
fi

# PostgREST giữ MỘT BẢN SAO LƯỢC ĐỒ TRONG BỘ NHỚ, đọc một lần lúc khởi động.
# Migration vừa chạy ở bước trên không tự chui vào đó. Bản sao cũ không làm hỏng
# truy vấn thường, nhưng mọi phép NHÚNG theo khoá ngoại thì trả về
# "Could not find a relationship between 'appointment' and 'patient' in the
# schema cache" — và màn hình chỉ hiện một dải đỏ, số đếm thì vẫn ra, nên trông
# như lỗi dữ liệu chứ không như lược đồ cũ. Gặp thật ngày 07/08/2026.
echo "==> [2c] bảo PostgREST đọc lại lược đồ"
docker exec "$DB" psql -q -U postgres -d postgres \
  -c "NOTIFY pgrst, 'reload schema'" >/dev/null

echo "==> [3/4] ứng dụng staging"
CLINIC_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" \
  -p "$APP_PROJECT" up -d --build api dashboard caddy

echo "==> [4/4] kiểm — và kiểm luôn PROD còn sống"
CONG="$(grep -E '^CADDY_HTTP_PORT=' "$ENV_FILE" | cut -d= -f2-)"
printf '    staging :%s → %s\n' "$CONG" \
  "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${CONG}/login")"
printf '    prod    :80   → %s\n' \
  "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/login)"
echo "==> xong."
