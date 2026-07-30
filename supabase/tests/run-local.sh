#!/usr/bin/env bash
# Apply the whole migration chain to a disposable Postgres container and run the
# assertion files against it. Nothing here ever touches a Supabase project.
#
#   supabase/tests/run-local.sh
#
# CI runs the same assertion files against a `postgres:17` service container —
# see the `database` job in .github/workflows/ci.yml.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONTAINER="${CONTAINER:-clinicai_db_tests}"
IMAGE="${IMAGE:-postgres:17}"

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker run -d --name "$CONTAINER" \
    -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres "$IMAGE" >/dev/null

for _ in $(seq 1 60); do
    docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 1
done

psql_run() { docker exec -i "$CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres; }

# psql meta-commands (\restrict, COPY ... FROM stdin) are client syntax, not SQL.
# psql swallows them, so this harness stayed green while `supabase db push` and
# `db reset` failed on line 1 — which is how a fresh project ended up
# unlaunchable. Fail here instead.
echo "==> Migrations and seed must be plain SQL"
if grep -nE '^\\(un)?restrict|FROM stdin' \
     "$REPO_ROOT"/supabase/migrations/*.sql "$REPO_ROOT"/supabase/seed.sql; then
    echo "ERROR: psql-only syntax above — the Supabase CLI cannot execute it." >&2
    exit 1
fi

echo "==> Supabase auth fixture"
psql_run < "$REPO_ROOT/supabase/tests/bootstrap_plain_postgres.sql" >/dev/null

echo "==> Migrations"
for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
    printf '    %s\n' "$(basename "$migration")"
    psql_run < "$migration" >/dev/null
done

# Forward-going rule: migrations written from this version onward must be safe to
# run twice, because `db push` retries and restore drills replay them. Older ones
# are already applied in production and are not edited retroactively.
IDEMPOTENT_FROM="${IDEMPOTENT_FROM:-20260730000000}"

echo "==> Migrations from $IDEMPOTENT_FROM onward must be re-appliable"
for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
    version="$(basename "$migration" | cut -d_ -f1)"
    [ "$version" \< "$IDEMPOTENT_FROM" ] && continue
    printf '    %s\n' "$(basename "$migration")"
    psql_run < "$migration" >/dev/null
done

echo "==> Assertions"
for test_file in "$REPO_ROOT"/supabase/tests/*.sql; do
    case "$(basename "$test_file")" in
        bootstrap_plain_postgres.sql) continue ;;
    esac
    printf '    %s\n' "$(basename "$test_file")"
    psql_run < "$test_file" >/dev/null
done

echo "OK — schema and tenant invariants hold."
