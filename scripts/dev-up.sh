#!/usr/bin/env bash
# Bring the whole thing up locally, then prove it is up.
#
# One command, because "chạy được" should not require knowing that Supabase must
# start before migrations, that migrations must run before fixtures, that the
# API needs six environment variables, and that the dashboard needs the anon key
# the CLI prints. Every one of those is a step somebody gets wrong once.
#
# It is idempotent: run it as often as you like. It never touches production —
# everything here points at the local Supabase on 127.0.0.1.
#
#   scripts/dev-up.sh            start everything and check it
#   scripts/dev-up.sh --reset    wipe the local database first
#   scripts/dev-up.sh --down     stop the API and dashboard

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

API_PORT="${API_PORT:-8100}"
WEB_PORT="${WEB_PORT:-3100}"
LOG_DIR="${LOG_DIR:-$REPO/.dev-logs}"
mkdir -p "$LOG_DIR"

blue()  { printf '\033[36m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }

stop_services() {
    pkill -f "uvicorn clinicai.main.*--port ${API_PORT}" 2>/dev/null || true
    pkill -f "next start -p ${WEB_PORT}" 2>/dev/null || true
    pkill -f "next dev -p ${WEB_PORT}" 2>/dev/null || true
}

if [ "${1:-}" = "--down" ]; then
    stop_services
    green "API and dashboard stopped. Supabase left running (npx supabase stop to stop it)."
    exit 0
fi

# ---- 1. Supabase ------------------------------------------------------------
blue "1/5  Supabase"
if ! curl -sf http://127.0.0.1:54321/rest/v1/ >/dev/null 2>&1; then
    npx --yes supabase@latest start >"$LOG_DIR/supabase.log" 2>&1 || {
        red "  Supabase failed to start — see $LOG_DIR/supabase.log"; exit 1; }
fi
ANON_KEY=$(npx --yes supabase@latest status -o env 2>/dev/null \
    | grep '^ANON_KEY=' | cut -d'"' -f2)
[ -n "$ANON_KEY" ] || { red "  could not read the anon key from supabase status"; exit 1; }
green "  up on 54321 (db 54322)"

# ---- 2. schema + fixtures ---------------------------------------------------
DB_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
if [ "${1:-}" = "--reset" ]; then
    blue "2/5  database reset (migrations + seed)"
    npx --yes supabase@latest db reset >"$LOG_DIR/db-reset.log" 2>&1 || {
        red "  db reset failed — see $LOG_DIR/db-reset.log"; exit 1; }
else
    blue "2/5  database (migrations only; --reset to wipe)"
fi
# Fixtures are separate from seed.sql on purpose: seed carries catalogue data
# every install needs, fixtures carry the fake staff and patient used for local
# testing. Loading fixtures into a real database would create fake clinicians.
for f in supabase/fixtures/staff_logins.sql supabase/fixtures/local_data.sql; do
    [ -f "$f" ] && psql -q "$DB_URL" -f "$f" >/dev/null 2>&1 || true
done
tables=$(psql -tA "$DB_URL" -c \
    "SELECT count(*) FROM pg_tables WHERE schemaname='public'" 2>/dev/null | tr -d ' ')
green "  $tables tables, fixtures loaded"

# ---- 3. API -----------------------------------------------------------------
blue "3/5  FastAPI"
stop_services
PYTHONPATH=src \
SUPABASE_URL=http://127.0.0.1:54321 \
DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres" \
SUPABASE_ANON_KEY="$ANON_KEY" \
SUPABASE_SERVICE_ROLE_KEY=local-service-role \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-local-not-real}" \
BACKEND_API_KEY=staging-local-api-key \
CHECKPOINTER_BACKEND=memory APP_ENV=staging POS_ADAPTER=none \
    nohup poetry run uvicorn clinicai.main:app \
        --host 127.0.0.1 --port "$API_PORT" >"$LOG_DIR/api.log" 2>&1 &

for _ in $(seq 1 40); do
    curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break; sleep 1
done
curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 \
    && green "  healthy on ${API_PORT}" \
    || { red "  API did not come up — see $LOG_DIR/api.log"; tail -5 "$LOG_DIR/api.log"; exit 1; }

# ---- 4. dashboard -----------------------------------------------------------
blue "4/5  Next.js dashboard"
cd src/dashboard
# A production build, not `next dev`: dev mode did not hydrate client components
# under headless Chromium during this work, and a board whose buttons do nothing
# is worse than one that is honestly still building.
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 \
NEXT_PUBLIC_SUPABASE_ANON_KEY="$ANON_KEY" \
CLINIC_API_URL="http://127.0.0.1:${API_PORT}" \
BACKEND_API_KEY=staging-local-api-key \
    npx next build >"$LOG_DIR/web-build.log" 2>&1 || {
        red "  build failed — see $LOG_DIR/web-build.log"
        grep -m5 -E "Error|error" "$LOG_DIR/web-build.log" | sed 's/^/    /'; exit 1; }

NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 \
NEXT_PUBLIC_SUPABASE_ANON_KEY="$ANON_KEY" \
CLINIC_API_URL="http://127.0.0.1:${API_PORT}" \
BACKEND_API_KEY=staging-local-api-key \
    nohup npx next start -p "$WEB_PORT" >"$LOG_DIR/web.log" 2>&1 &
cd "$REPO"

for _ in $(seq 1 40); do
    curl -sf -o /dev/null "http://127.0.0.1:${WEB_PORT}/" 2>/dev/null && break; sleep 1
done
curl -sf -o /dev/null "http://127.0.0.1:${WEB_PORT}/" 2>/dev/null \
    && green "  serving on ${WEB_PORT}" \
    || { red "  dashboard did not come up — see $LOG_DIR/web.log"; exit 1; }

# ---- 5. prove the stack talks to itself -------------------------------------
blue "5/5  end-to-end check"
TOKEN=$(curl -s -X POST "http://127.0.0.1:54321/auth/v1/token?grant_type=password" \
    -H "apikey: $ANON_KEY" -H 'Content-Type: application/json' \
    -d '{"email":"letan@dr4women.local","password":"clinic-test-pw-123"}' \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
if [ -n "$TOKEN" ]; then
    n=$(curl -s "http://127.0.0.1:${API_PORT}/api/v1/work-items?workspace=bang_dieu_phoi" \
        -H "Authorization: Bearer $TOKEN" -H "X-API-Key: staging-local-api-key" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(len(d) if isinstance(d,list) else "err")' 2>/dev/null)
    green "  reception queue answers with $n item(s)"
else
    red "  could not sign in as the fixture receptionist — fixtures may be missing"
fi

cat <<EOF

$(green "Ready.")

  Dashboard   http://127.0.0.1:${WEB_PORT}
  API         http://127.0.0.1:${API_PORT}/docs
  Supabase    http://127.0.0.1:54323
  Logs        ${LOG_DIR}/

  Đăng nhập (mật khẩu chung: clinic-test-pw-123)
    letan@dr4women.local     Lễ tân      → Hàng đợi tiếp nhận
    bs.a@dr4women.local      Bác sĩ      → Bàn khám, Chỉ định dịch vụ
    dd.sa@dr4women.local     Điều dưỡng  → Sinh hiệu
    thungan@dr4women.local   Thu ngân    → Bàn thu ngân
    ql@dr4women.local        Quản lý     → Sức khoẻ API, Vận hành

  Dừng:  scripts/dev-up.sh --down
EOF
