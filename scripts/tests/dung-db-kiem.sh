#!/usr/bin/env bash
# Dựng database dùng một lần cho test `-m db`: auth giả + toàn bộ migration + seed.
#
# CI (job backend) và máy dev dùng CHUNG script này, để "test DB xanh ở máy tôi"
# và "xanh trên CI" là cùng một phép đo.
#
#   PSQL="psql -h localhost -U postgres -d postgres" scripts/tests/dung-db-kiem.sh
#
# Máy dev không có psql: đặt DB_CONTAINER, script tự dựng postgres:17 ở cổng
# DB_PORT (mặc định 55433 — cổng các test SQL TEMP chấp nhận) rồi in ra DATABASE_URL_TEST.
#
#   DB_CONTAINER=clinicai_ci01_db scripts/tests/dung-db-kiem.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [ -n "${DB_CONTAINER:-}" ]; then
    DB_PORT="${DB_PORT:-55433}"
    docker rm -fv "$DB_CONTAINER" >/dev/null 2>&1 || true
    docker run -d --name "$DB_CONTAINER" -p "127.0.0.1:${DB_PORT}:5432" \
        -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres postgres:17 >/dev/null
    for _ in $(seq 1 60); do
        docker exec "$DB_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
        sleep 1
    done
    sleep 1
    psql_run() { docker exec -i "$DB_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres; }
else
    : "${PSQL:?đặt PSQL (vd psql -h localhost -U postgres -d postgres) hoặc DB_CONTAINER}"
    # shellcheck disable=SC2086
    psql_run() { $PSQL -q -v ON_ERROR_STOP=1; }
fi

psql_run < "$REPO_ROOT/supabase/tests/bootstrap_plain_postgres.sql" >/dev/null
for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
    psql_run < "$migration" >/dev/null
done
psql_run < "$REPO_ROOT/supabase/seed.sql" >/dev/null

echo "OK — migration + seed đã nạp."
if [ -n "${DB_CONTAINER:-}" ]; then
    echo "DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:${DB_PORT}/postgres"
fi
