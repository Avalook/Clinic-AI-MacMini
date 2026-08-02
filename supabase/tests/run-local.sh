#!/usr/bin/env bash
# Apply the whole migration chain to a disposable Postgres container and run the
# assertion files against it. Nothing here ever touches a Supabase project.
#
#   supabase/tests/run-local.sh
#
# Two databases, because they answer different questions:
#
#   fresh   migrations applied exactly once — the shape `supabase db push`
#           produces in production. Every assertion runs here.
#   replay  migrations applied, then applied again. Asserts nothing beyond "no
#           error", because the schema a second pass leaves behind is not one
#           this project ever ships. 20260730000014 drops every clinic_id
#           DEFAULT and 20260730000008 grants SELECT wherever a policy exists,
#           so replaying repairs mistakes before an assertion can catch them —
#           which is exactly how the pharmacy tables shipped broken.
#
# CI runs the same files in the same shape — see `db_fresh` and `db_replay` in
# .github/workflows/ci.yml.
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

# psql_run <database>
psql_run() { docker exec -i "$CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$1"; }

docker exec "$CONTAINER" createdb -U postgres replay

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

for db in postgres replay; do
    echo "==> [$db] Supabase auth fixture"
    psql_run "$db" < "$REPO_ROOT/supabase/tests/bootstrap_plain_postgres.sql" >/dev/null

    echo "==> [$db] Migrations"
    for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
        printf '    %s\n' "$(basename "$migration")"
        psql_run "$db" < "$migration" >/dev/null
    done
done

echo "==> [postgres] Assertions against the single-pass schema"
for test_file in "$REPO_ROOT"/supabase/tests/*.sql; do
    case "$(basename "$test_file")" in
        bootstrap_plain_postgres.sql|derive_tenant_tables.sql) continue ;;
    esac
    printf '    %s\n' "$(basename "$test_file")"
    psql_run postgres < "$test_file" >/dev/null
done

# The audit's table list is derived here rather than carried inside the script,
# which is why running it needs a database at all. Without this file it refuses
# to run — an audit with a stale list reports zero findings and looks identical
# to an audit that passes.
TENANT_TABLES_FILE="${TENANT_TABLES_FILE:-$(mktemp -t tenant-tables)}"
echo "==> [postgres] Tenant-scope audit"
docker exec -i "$CONTAINER" psql -At -v ON_ERROR_STOP=1 -U postgres -d postgres \
    < "$REPO_ROOT/supabase/tests/derive_tenant_tables.sql" > "$TENANT_TABLES_FILE"
printf '    %s tenant-scoped tables\n' "$(wc -l < "$TENANT_TABLES_FILE" | tr -d ' ')"
python3 "$REPO_ROOT/scripts/tests/tenant-scope-audit.py" --check \
    --tenant-tables "$TENANT_TABLES_FILE"

# Forward-going rule: migrations written from this version onward must be safe to
# run twice, because `db push` retries and restore drills replay them. Older ones
# are already applied in production and are not edited retroactively.
IDEMPOTENT_FROM="${IDEMPOTENT_FROM:-20260730000000}"

echo "==> [replay] Migrations from $IDEMPOTENT_FROM onward must be re-appliable"
for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
    version="$(basename "$migration" | cut -d_ -f1)"
    [ "$version" \< "$IDEMPOTENT_FROM" ] && continue
    printf '    %s\n' "$(basename "$migration")"
    psql_run replay < "$migration" >/dev/null
done

echo "OK — schema and tenant invariants hold."
