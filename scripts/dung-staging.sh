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
# CÁC THỨ PHẢI ĐẢM BẢO CÁCH LY (thiếu hoặc sai là dừng khẩn cấp trước khi dựng):
#   1. SUPABASE_PREFIX=clinicai_stg      — tên container riêng (không được là clinicai)
#   2. SUPABASE_NETWORK=clinicai_stg_db_supabase — mạng DB riêng (không được là clinicai_db_supabase)
#   3. SUPABASE_GATEWAY_HOST=clinicai_stg_supabase_gateway — gateway riêng (không trỏ prod)
#   4. AUTH_GUARD_HOST=clinicai_stg_auth_guard — guard riêng (không trỏ prod)
#   5. SUPABASE_DB_PORT=54332, SUPABASE_API_PORT=54331 — cổng mở localhost riêng
#   6. SUPABASE_JWT_SECRET, SUPABASE_DB_PASSWORD, BACKEND_API_KEY — bí mật riêng, KHÁC prod
#
# LUỒNG NẠP LƯỢC ĐỒ (chống race condition với GoTrue):
#   - Tuyệt đối không chạy bootstrap_plain_postgres.sql (đó là fixture cho Postgres trắng,
#     không dành cho Supabase project có GoTrue).
#   - Fresh DB: gọi scripts/supabase-local-nap.sh (chờ GoTrue tạo auth.users +
#     auth.identities thật, nâng auth.uid/auth.role, chạy migrations chuẩn).
#   - Existing DB: gọi scripts/apply-pending-migrations.sh --apply (chỉ áp migration mới).
#   - Sau khi dựng xong ứng dụng: kiểm tra mạng docker thực tế, cấm nối nhầm mạng prod.
#
#   ./scripts/dung-staging.sh            # dựng / cập nhật staging
#   ./scripts/dung-staging.sh --gieo     # dựng lại cả dữ liệu thử
#
# CHẠY TRÊN MÁY CHỦ (ssh clinic-vps-moi), không phải trên máy cá nhân — script
# dùng docker của máy đang gõ lệnh.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

ENV_FILE=".env.staging"
SB_PROJECT="clinicai_stg_db"
APP_PROJECT="clinicai_staging"

[ -f "$ENV_FILE" ] || {
  echo "!! thiếu $ENV_FILE. Xem .env.staging.example và các biến bắt buộc ở đầu file này." >&2
  exit 1
}

env_get() {
  grep -E "^${1}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\r"' || true
}

# ── KIỂM TRA CHẶT TRƯỚC KHI DỰNG (FAIL-CLOSED) ────────────────────────────────
PREFIX="$(env_get SUPABASE_PREFIX)"
NETWORK="$(env_get SUPABASE_NETWORK)"
GW_HOST="$(env_get SUPABASE_GATEWAY_HOST)"
AG_HOST="$(env_get AUTH_GUARD_HOST)"
DB_PORT="$(env_get SUPABASE_DB_PORT)"
API_PORT="$(env_get SUPABASE_API_PORT)"
JWT_SECRET="$(env_get SUPABASE_JWT_SECRET)"
DB_PASSWORD="$(env_get SUPABASE_DB_PASSWORD)"
BACKEND_KEY="$(env_get BACKEND_API_KEY)"

[ "$PREFIX" = "clinicai_stg" ] || {
  echo "!! SUPABASE_PREFIX trong $ENV_FILE phải là clinicai_stg (hiện là: '${PREFIX:-rỗng}')" >&2
  exit 1
}
[ "$PREFIX" != "clinicai" ] || {
  echo "!! SUPABASE_PREFIX không được là clinicai (trùng prod)" >&2
  exit 1
}
[ "$NETWORK" = "clinicai_stg_db_supabase" ] || {
  echo "!! SUPABASE_NETWORK trong $ENV_FILE phải là clinicai_stg_db_supabase (hiện là: '${NETWORK:-rỗng}')" >&2
  exit 1
}
[ "$NETWORK" != "clinicai_db_supabase" ] || {
  echo "!! SUPABASE_NETWORK không được là clinicai_db_supabase (trùng mạng prod)" >&2
  exit 1
}
[ "$GW_HOST" = "clinicai_stg_supabase_gateway" ] || {
  echo "!! SUPABASE_GATEWAY_HOST trong $ENV_FILE phải là clinicai_stg_supabase_gateway (hiện là: '${GW_HOST:-rỗng}')" >&2
  exit 1
}
[ "$AG_HOST" = "clinicai_stg_auth_guard" ] || {
  echo "!! AUTH_GUARD_HOST trong $ENV_FILE phải là clinicai_stg_auth_guard (hiện là: '${AG_HOST:-rỗng}')" >&2
  exit 1
}
[ "$DB_PORT" = "54332" ] || {
  echo "!! SUPABASE_DB_PORT trong $ENV_FILE phải là 54332 (hiện là: '${DB_PORT:-rỗng}')" >&2
  exit 1
}
[ "$API_PORT" = "54331" ] || {
  echo "!! SUPABASE_API_PORT trong $ENV_FILE phải là 54331 (hiện là: '${API_PORT:-rỗng}')" >&2
  exit 1
}
[ -n "$JWT_SECRET" ] || { echo "!! thiếu SUPABASE_JWT_SECRET trong $ENV_FILE" >&2; exit 1; }
[ -n "$DB_PASSWORD" ] || { echo "!! thiếu SUPABASE_DB_PASSWORD trong $ENV_FILE" >&2; exit 1; }
[ -n "$BACKEND_KEY" ] || { echo "!! thiếu BACKEND_API_KEY trong $ENV_FILE" >&2; exit 1; }

DB="${PREFIX}_db"
[ "$DB" != "clinicai_db" ] || {
  echo "!! Target DB container là clinicai_db (trùng prod)! Dừng khẩn cấp." >&2
  exit 1
}

# Chặn trùng bí mật với prod
for bien in SUPABASE_JWT_SECRET SUPABASE_DB_PASSWORD BACKEND_API_KEY; do
  a="$(env_get "$bien")"
  b="$(grep -E "^${bien}=" .env.prod 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r"' || true)"
  [ -n "$b" ] && [ "$a" = "$b" ] && {
    echo "!! $bien của staging TRÙNG prod. Sinh khoá riêng, nếu không token đi chéo được." >&2
    exit 1
  }
done

echo "==> [1/5] bộ Supabase riêng của staging ($SB_PROJECT)"
docker compose --env-file "$ENV_FILE" -f docker-compose.supabase.yml -p "$SB_PROJECT" up -d

echo "==> chờ Postgres staging ($DB) sẵn sàng..."
for _ in $(seq 1 40); do
  docker exec "$DB" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$DB" pg_isready -U postgres >/dev/null 2>&1 || {
  echo "!! Postgres staging ($DB) không sẵn sàng sau 40s" >&2
  exit 1
}

AUTH_CONTAINER="${PREFIX}_auth"
echo "==> chờ GoTrue staging (${AUTH_CONTAINER}) khởi động..."
for _ in $(seq 1 60); do
  status="$(docker inspect --format='{{json .State.Health.Status}}' "$AUTH_CONTAINER" 2>/dev/null || echo '""')"
  if [ "$status" = '"healthy"' ]; then
    break
  fi
  sleep 1
done

AUTH_HEALTH="$(docker inspect --format='{{json .State.Health.Status}}' "$AUTH_CONTAINER" 2>/dev/null || echo '""')"
[ "$AUTH_HEALTH" = '"healthy"' ] || {
  echo "!! GoTrue staging ($AUTH_CONTAINER) chưa healthy sau 60s (trạng thái: $AUTH_HEALTH)" >&2
  exit 1
}

echo "==> [2/5] lược đồ (không dùng bootstrap_plain_postgres.sql)"
HAS_LEDGER="$(docker exec -i "$DB" psql -U postgres -d postgres -tAc "SELECT to_regclass('supabase_migrations.schema_migrations') IS NOT NULL" 2>/dev/null | tr -d ' ' || true)"
MIGRATION_COUNT="0"
if [ "$HAS_LEDGER" = "t" ]; then
  MIGRATION_COUNT="$(docker exec -i "$DB" psql -U postgres -d postgres -tAc "SELECT count(*) FROM supabase_migrations.schema_migrations" 2>/dev/null | tr -d ' ' || echo "0")"
fi

if [ "$HAS_LEDGER" != "t" ] || [ "$MIGRATION_COUNT" = "0" ]; then
  echo "    [fresh DB] nạp lược đồ qua supabase-local-nap.sh (chờ GoTrue auth.users + auth.identities)"
  SUPABASE_DB_CONTAINER="$DB" ./scripts/supabase-local-nap.sh
else
  echo "    [existing DB] đã có $MIGRATION_COUNT migration ghi sổ, áp migration còn thiếu"
  CLINIC_DB_CONTAINER="$DB" ./scripts/apply-pending-migrations.sh --apply
fi

if [ "${1:-}" = "--gieo" ]; then
  echo "==> [2b] dữ liệu thử"
  docker cp supabase "$DB":/sb >/dev/null
  for f in seed.sql fixtures/staff_logins.sql fixtures/local_data.sql \
           fixtures/demo_clinic_day.sql; do
    [ -f "supabase/$f" ] || continue
    docker exec "$DB" psql -q -U postgres -d postgres -f "/sb/${f}" >/dev/null 2>&1 \
      && echo "    OK  $f" || echo "    bỏ qua  $f"
  done
  # Seed bật lại toàn bộ danh mục dịch vụ; thu về đúng các loại khám đang dùng.
  docker exec "$DB" psql -q -U postgres -d postgres \
    -f /sb/migrations/20260807000007_nam_dich_vu_kham.sql >/dev/null
  # …rồi bật lại Thủ thuật + Sàn chậu chuyên sâu (24/09) mà câu trên vừa tắt.
  docker exec "$DB" psql -q -U postgres -d postgres \
    -f /sb/migrations/20260925000006_dat_lich_thu_thuat_san_chau.sql >/dev/null
  docker exec "$DB" rm -rf /sb >/dev/null 2>&1 || true

  echo "==> [2c] bảo PostgREST đọc lại lược đồ sau khi gieo"
  docker exec "$DB" psql -q -U postgres -d postgres \
    -c "NOTIFY pgrst, 'reload schema'" >/dev/null
fi

echo "==> [3/5] ứng dụng staging"
CLINIC_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" \
  -p "$APP_PROJECT" up -d --build api dashboard caddy

echo "==> [4/5] kiểm tra cách ly mạng docker"
for svc in caddy dashboard api; do
  cid="$(docker compose --env-file "$ENV_FILE" -p "$APP_PROJECT" ps -q "$svc" 2>/dev/null || true)"
  if [ -n "$cid" ]; then
    networks="$(docker inspect --format='{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$cid")"
    if ! grep -q "clinicai_stg_db_supabase" <<<"$networks"; then
      echo "!! VI PHẠM: container $svc ($cid) KHÔNG nằm trên mạng clinicai_stg_db_supabase!" >&2
      exit 1
    fi
    if grep -q "clinicai_db_supabase" <<<"$networks"; then
      echo "!! NGUY HIỂM: container $svc ($cid) BỊ NỐI VÀO MẠNG PROD clinicai_db_supabase!" >&2
      exit 1
    fi
  fi
done
echo "    OK: staging containers chỉ gắn vào clinicai_stg_db_supabase, không dính clinicai_db_supabase."

echo "==> [5/5] kiểm đăng nhập — và kiểm luôn PROD còn sống"
CONG="$(env_get CADDY_HTTP_PORT)"
printf '    staging :%s → %s\n' "${CONG:-8080}" \
  "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${CONG:-8080}/login" 2>/dev/null || echo 'err')"
printf '    prod    :80   → %s\n' \
  "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/login 2>/dev/null || echo 'err')"
echo "==> xong."
