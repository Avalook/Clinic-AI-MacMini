#!/usr/bin/env bash
# BẢN STAGING Y HỆT PROD — trên máy Mac, từ BẢN SAO LƯU ĐÊM (01/10/2026).
#
# VÌ SAO CÓ FILE NÀY. Bản local dựng bằng dev-up.sh chạy DỮ LIỆU THỬ. Thanh bên,
# phòng, lịch trực, lego của từng tài khoản, danh mục dịch vụ đều là DỮ LIỆU —
# code giống prod mà dữ liệu khác thì màn vẫn khác. Script này nạp bản sao lưu
# prod mới nhất (Mac kéo về lúc 0:30 / 6:30, xem keo-ve.sh) vào database local,
# gồm cả tài khoản đăng nhập: đăng nhập local bằng chính tài khoản prod.
#
# KHÔNG đụng prod: chỉ đọc tệp sao lưu đã nằm trên Mac. Tin nhắn ra ngoài
# (Telegram, Zalo, SMS) không gửi được vì .env.thu-local không có khoá gửi.
# Ảnh / tệp kết quả không có (không kéo tệp prod về đây) — màn hiện "không mở
# được tệp" là đúng.
#
# NÓ XOÁ SẠCH dữ liệu thử local trong container clinicai_thu_db. Muốn quay lại
# dữ liệu thử: scripts/dev-up.sh --reset.
#
#   scripts/staging-tu-ban-sao.sh          hỏi lại rồi làm
#   scripts/staging-tu-ban-sao.sh --yes    không hỏi
#
# Chạy từ thư mục repo đang đứng ở nhánh main (git pull trước) — code phải là
# bản prod đang chạy thì mới "y hệt".

set -euo pipefail

REPO="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO"

THU_MUC="${BAN_SAO_DIR:-$HOME/Projects/ClinicAI-Backups/ban-sao}"
DB="${CLINIC_THU_DB:-clinicai_thu_db}"
API_PORT="${API_PORT:-8100}"
WEB_PORT="${WEB_PORT:-3100}"
LOG_DIR="${LOG_DIR:-$REPO/.dev-logs}"
mkdir -p "$LOG_DIR"

xanh() { printf '\033[32m%s\033[0m\n' "$*"; }
do_() { printf '\033[31m%s\033[0m\n' "$*" >&2; }
dung() { do_ "DỪNG: $*"; exit 1; }

psql_db() { docker exec -i "$DB" psql -v ON_ERROR_STOP=1 -q -U postgres -d postgres "$@"; }

# ---- 0. kiểm đầu vào ---------------------------------------------------------
[ -f .env.thu-local ] || dung "thiếu .env.thu-local — chạy scripts/dev-up.sh một lần trước."
docker inspect "$DB" >/dev/null 2>&1 || dung "không có container $DB — chạy scripts/dev-up.sh trước."

BAN="$(ls -t "$THU_MUC"/clinicai_production_*.sql.gz 2>/dev/null | grep -v '_auth\.sql\.gz$' | head -1 || true)"
[ -n "$BAN" ] || dung "không thấy bản sao lưu nào trong $THU_MUC"
AUTH="${BAN%.sql.gz}_auth.sql.gz"
[ -f "$AUTH" ] || dung "thiếu tệp tài khoản $AUTH"

# Tệp hỏng nửa chừng thì dừng TRƯỚC khi xoá gì.
if [ -f "$BAN.manifest" ]; then
    MONG="$(sed -n 's/^archive_sha256=//p' "$BAN.manifest")"
    THAT="$(shasum -a 256 "$BAN" | cut -d' ' -f1)"
    [ -z "$MONG" ] || [ "$MONG" = "$THAT" ] || dung "tệp sao lưu sai mã kiểm (sha256) — đừng nạp."
fi
gzip -t "$BAN" && gzip -t "$AUTH" || dung "tệp sao lưu không giải nén được."

echo "Bản sao lưu: $(basename "$BAN")"
echo "Database:    container $DB (dữ liệu thử local sẽ bị XOÁ SẠCH)"
echo "Code:        $(git log --oneline -1)"
git fetch -q origin main 2>/dev/null || true
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main 2>/dev/null || echo x)" ]; then
    do_ "Lưu ý: code ở đây KHÁC origin/main — bản local sẽ không y hệt prod. Nên: git checkout main && git pull"
fi
if [ "${1:-}" != "--yes" ]; then
    read -r -p "Gõ CO để làm: " tl
    [ "$tl" = "CO" ] || dung "không làm gì."
fi

# ---- 1. dừng web / API / người đưa tin của bản local --------------------------
xanh "1/5  Dừng web, API, người đưa tin local"
pkill -f "uvicorn clinicai.main.*--port ${API_PORT}" 2>/dev/null || true
pkill -f "next (start|dev) -p ${WEB_PORT}" 2>/dev/null || true
pkill -f "clinicai.worker --su-kien" 2>/dev/null || true
# Dừng dịch vụ đọc DB của Supabase local cho khỏi giữ kết nối lúc thay dữ liệu.
for c in clinicai_thu_auth clinicai_thu_rest clinicai_thu_realtime; do
    docker stop "$c" >/dev/null 2>&1 || true
done

# ---- 2. tài khoản: thay auth.users + auth.identities -------------------------
# GỠ lược đồ public TRƯỚC: DB local (dev-up) có khoá ngoại public → auth.users
# (prod thì không), nên TRUNCATE auth.users CASCADE sẽ lan sang bảng lịch hẹn và
# đụng chốt "append-only" (01/10/2026, lần chạy đầu dừng ở đây — không mất gì vì
# lệnh hỏng bị huỷ cả khối). DROP SCHEMA không chạy trigger xoá hàng.
xanh "2/5  Gỡ dữ liệu thử + nạp tài khoản đăng nhập"
psql_db -c "DROP SCHEMA public CASCADE;"
psql_db -c "TRUNCATE auth.users CASCADE;"
gzcat "$AUTH" | psql_db >/dev/null

# ---- 3. dữ liệu phòng khám: lược đồ public từ bản sao lưu ---------------------
xanh "3/5  Nạp dữ liệu phòng khám (vài chục giây)"
gzcat "$BAN" | psql_db >/dev/null
# Quyền cho vai Supabase local (bản dump không chở GRANT của vai — Owner: -).
psql_db <<'SQL'
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated, service_role;
SQL

# ---- 4. sổ migration khớp dữ liệu vừa nạp ------------------------------------
# Sổ ghi (`supabase_migrations.schema_migrations`) KHÔNG nằm trong bản sao lưu
# (chỉ lược đồ public). Dữ liệu vừa nạp là prod lúc 02:15, đã áp mọi migration
# của bản prod đang chạy → ghi sổ = mọi migration trong thư mục này. Đúng khi
# code ở đây LÀ bản prod (main vừa pull). Code mới hơn prod (nhánh có migration
# chưa deploy) thì sau script chạy thêm apply-pending-migrations.sh --apply.
xanh "4/5  Ghi sổ migration theo bản prod"
{
    echo "CREATE SCHEMA IF NOT EXISTS supabase_migrations;"
    echo "CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (version text PRIMARY KEY, name text, statements text[]);"
    echo "TRUNCATE supabase_migrations.schema_migrations;"
    for f in supabase/migrations/*.sql; do
        b="$(basename "$f" .sql)"
        echo "INSERT INTO supabase_migrations.schema_migrations (version, name) VALUES ('${b%%_*}', '${b#*_}');"
    done
} | psql_db
for c in clinicai_thu_auth clinicai_thu_rest clinicai_thu_realtime; do
    docker start "$c" >/dev/null 2>&1 || true
done
sleep 3
psql_db -c "NOTIFY pgrst, 'reload schema';"

# ---- 5. bật lại API + web + người đưa tin ------------------------------------
xanh "5/5  Bật API, web, người đưa tin"
./scripts/dev-nap-lai.sh
set -a; . ./.env.thu-local; set +a
PYTHONPATH=src \
DATABASE_URL="postgresql+asyncpg://postgres:${SUPABASE_DB_PASSWORD}@127.0.0.1:${SUPABASE_DB_PORT:-54422}/postgres" \
SUPABASE_URL="http://127.0.0.1:${SUPABASE_API_PORT:-54421}" \
SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-local-not-real}" \
CHECKPOINTER_BACKEND=memory APP_ENV=staging POS_ADAPTER=none \
    nohup poetry run python -m clinicai.worker --su-kien >"$LOG_DIR/su-kien.log" 2>&1 &
sleep 2
pgrep -f "clinicai.worker --su-kien" >/dev/null || do_ "người đưa tin không chạy — xem $LOG_DIR/su-kien.log"

SO="$(psql_db -At -c "SELECT (SELECT count(*) FROM staff)||' nhân sự · '||(SELECT count(*) FROM clinic_room WHERE is_active)||' phòng · '||(SELECT count(*) FROM visit)||' lượt khám'")"
xanh "XONG — bản local giờ là bản sao prod: $SO"
echo "Mở http://127.0.0.1:${WEB_PORT} — đăng nhập bằng TÀI KHOẢN PROD của bạn."
echo "Quay về dữ liệu thử: scripts/dev-up.sh --reset"
