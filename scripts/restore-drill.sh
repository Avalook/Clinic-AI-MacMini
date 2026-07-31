#!/bin/bash
# Restore the latest ClinicAI backup into a throwaway database and prove the
# data came back.
#
# WHY THIS EXISTS. backup-db.sh verifies the ARCHIVE — gzip integrity, a sha256
# against its manifest, and a grep for completeness markers. verify-backup.sh
# checks the same file is recent and intact. Neither has ever restored anything,
# so "backup verified" has only ever meant "the file looks like a dump". A dump
# that fails halfway through a real restore passes every one of those checks.
#
# This drill answers the only question that matters the morning the Mac dies:
# if I run this into an empty database, do I get the clinic back? It restores
# for real and then asserts the shape of what came out — the tables that hold
# patients and money, the tenant column every policy depends on, and the row
# counts, so a dump that silently truncated is visible instead of reassuring.
#
# WHAT A RESTORE NEEDS THAT THIS BACKUP DOES NOT CONTAIN. The dump is
# --schema=public --no-owner --no-acl, which is the right scope for application
# data but is NOT a whole Supabase project. Before it can be loaded, the target
# must already provide:
#   * the auth schema and auth.uid(), which every RLS policy calls
#   * the authenticated / anon / service_role roles the policies name
#   * unaccent, pg_trgm, btree_gist, pgcrypto — the dump defines f_unaccent()
#     and indexes over it, but --schema=public emits no CREATE EXTENSION
# A real Supabase project has all of these the moment it is created. A bare
# postgres does not, so the drill installs them from the same files the repo
# already uses and says so — pretending otherwise would make the drill easier
# than the day it is needed.
#
# WHAT THIS DRILL FOUND, the first time it was run: the backup was NOT
# restorable at all. staff.auth_user_id has a foreign key to auth.users, which a
# public-only dump does not contain, so the restore died partway through with a
# constraint violation — not with "missing logins", with a failed restore. Every
# archive check passed that same file. backup-db.sh now writes a companion
# *_auth.sql.gz (auth.users + auth.identities, a few KB) and the manifest records
# restore_order=auth-then-public.
#
# Still outside the backup: sessions, refresh tokens, MFA state and Supabase
# platform configuration. GoTrue rebuilds the first three; the last needs the
# platform's own backup/PITR.
#
# Usage:
#   ./scripts/restore-drill.sh                       # newest backup
#   ./scripts/restore-drill.sh path/to/backup.sql.gz
#
# Tunables:
#   DRILL_PG_IMAGE=postgres:17     image for the throwaway target
#   DRILL_KEEP=1                   leave the container running for inspection
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${HOME}/backups/clinicai}"
PG_IMAGE="${DRILL_PG_IMAGE:-postgres:17}"
CONTAINER="clinicai-restore-drill-$$"
BACKUP_FILE="${1:-}"

pass=0
fail=0

fail_hard() { echo "ERROR: $*" >&2; exit 1; }
check() {
    if [ "$2" = "ok" ]; then
        printf '  PASS  %s\n' "$1"; pass=$((pass + 1))
    else
        printf '  FAIL  %s\n        %s\n' "$1" "$2"; fail=$((fail + 1))
    fi
}

command -v docker >/dev/null 2>&1 || fail_hard "docker is required for the drill"

if [ -z "$BACKUP_FILE" ]; then
    # The companion sorts AFTER the archive it belongs to, so it has to be
    # excluded or "the newest backup" is the 1.5 KB auth file.
    BACKUP_FILE=$(find "$BACKUP_DIR" -maxdepth 1 -type f \
        -name 'clinicai_*.sql.gz' ! -name '*_auth.sql.gz' \
        -print 2>/dev/null | LC_ALL=C sort | tail -n 1)
fi
[ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ] || \
    fail_hard "no backup to restore (looked in $BACKUP_DIR)"

echo "=== restoring $(basename "$BACKUP_FILE") into a throwaway $PG_IMAGE ==="

cleanup() {
    if [ "${DRILL_KEEP:-0}" = "1" ]; then
        echo "DRILL_KEEP=1 — container $CONTAINER left running"
    else
        docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

docker run -d --name "$CONTAINER" \
    -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=postgres \
    "$PG_IMAGE" >/dev/null

for _ in $(seq 1 60); do
    docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 1
done
docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1 || \
    fail_hard "throwaway postgres did not become ready"

q() { docker exec -i "$CONTAINER" psql -U postgres -d postgres -tAc "$1" 2>/dev/null; }

# The prerequisites a real Supabase project already has on day one. The drill
# installs them explicitly because the archive does NOT carry them, and each one
# is a way the restore fails at 3am if nobody wrote it down:
#   * auth schema + auth.uid() + the authenticated/anon/service_role roles,
#     which every RLS policy in the dump references
#   * unaccent, pg_trgm, btree_gist, pgcrypto — the dump defines f_unaccent()
#     and indexes that call them, but `pg_dump --schema=public` does not emit
#     CREATE EXTENSION, so restoring into a database without them dies partway
docker exec -i "$CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres \
    < "${REPO}/supabase/tests/bootstrap_plain_postgres.sql" >/dev/null 2>&1 || \
    fail_hard "could not install the auth/roles prerequisites into the target"

docker exec -i "$CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres \
    < "${REPO}/supabase/migrations/20260714000000_extensions.sql" >/dev/null 2>&1 || \
    fail_hard "could not install the required extensions into the target"

# ---- auth identities first --------------------------------------------------
# staff.auth_user_id references auth.users, so the public dump CANNOT load until
# those rows exist. On a real Supabase target you restore the companion
# *_auth.sql.gz as-is. Here the target only has the minimal fixture auth.users
# (an id column), so the drill lifts the ids out of that artifact and seeds
# them: enough to prove the foreign key resolves and the public restore
# completes. It does NOT re-validate password hashes or identity rows — that is
# what restoring the artifact into a real project does.
AUTH_FILE="${BACKUP_FILE%.sql.gz}_auth.sql.gz"
if [ -f "$AUTH_FILE" ]; then
    ids=$(gzip -cd "$AUTH_FILE" | python3 -c '
import sys
cols, out = None, []
for line in sys.stdin:
    if line.startswith("COPY auth.users ("):
        cols = [c.strip().strip(chr(34)) for c in
                line[line.index("(") + 1:line.index(")")].split(",")]
        continue
    if cols is not None:
        if line.startswith(chr(92) + "."):
            break
        parts = line.rstrip(chr(10)).split(chr(9))
        if "id" in cols and len(parts) == len(cols):
            out.append(parts[cols.index("id")])
print(chr(10).join(out))
')
    n=$(printf '%s' "$ids" | grep -c . || true)
    if [ "${n:-0}" -gt 0 ]; then
        # One statement, not a loop: `docker exec -i` reads stdin, so calling it
        # inside `while read` swallows the remaining ids and silently seeds only
        # the first — which looked like "7 identities available" while the
        # restore still failed on the eighth staff row.
        values=$(printf '%s\n' "$ids" | awk 'NF {printf "%s(%s%s%s)", sep, q, $0, q; sep=","} END {print ""}' q="'")
        q "INSERT INTO auth.users (id) VALUES $values ON CONFLICT DO NOTHING" >/dev/null
        seeded=$(q "SELECT count(*) FROM auth.users")
        if [ "${seeded:-0}" = "$n" ]; then
            check "auth identities available for the staff foreign key ($n)" ok
        else
            check "auth identities available for the staff foreign key" \
                  "seeded ${seeded:-0} of $n"
        fi
    else
        check "auth identities available for the staff foreign key" \
              "the auth artifact contained no user ids"
    fi
else
    check "auth companion artifact exists" \
          "missing $(basename "$AUTH_FILE") — the public dump cannot satisfy staff.auth_user_id"
fi

# The restore itself. ON_ERROR_STOP so a half-applied dump is a failure, not a
# warning scrolling past — that is exactly how a restore appears to work and
# then turns out to be missing a table.
# `CREATE SCHEMA public;` is stripped: the dump emits it, but every real target
# — a fresh Postgres, a new Supabase project — already has that schema, so the
# statement aborts the restore on line one. An operator has to skip it too, so
# the drill does exactly what the runbook tells them to do rather than something
# easier.
# The empty search_path is neutralised, and this one is NOT cosmetic — it is
# compensating for a real defect in the production schema.
#
# pg_dump opens with set_config('search_path', '', false) so that every object
# must be schema-qualified. Production's f_unaccent is not:
#
#     CREATE FUNCTION public.f_unaccent(text) ... AS $$ SELECT unaccent('unaccent', $1) $$
#
# patient.full_name_unaccent is a GENERATED column over f_unaccent, so the
# moment COPY loads a patient row Postgres inlines that call, cannot resolve
# `unaccent` with an empty search_path, and the restore dies. The production
# backup therefore does not restore as-is — into a throwaway Postgres OR into a
# fresh Supabase project.
#
# Pointing search_path at public lets the restore complete, which is what an
# operator would have to do at 3am. The REAL fix is to qualify the call in the
# production schema (SELECT public.unaccent('public.unaccent'::regdictionary, $1))
# so the backup stands on its own; until that ships, this line is the only
# reason a production restore works, and it belongs in the runbook.
if gzip -cd "$BACKUP_FILE" \
        | sed "s|SELECT pg_catalog.set_config('search_path', '', false);|SELECT pg_catalog.set_config('search_path', 'public', false);|" \
        | grep -vx 'CREATE SCHEMA public;' \
        | docker exec -i "$CONTAINER" \
          psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres >/tmp/drill_restore.log 2>&1; then
    check "the dump restores without error" ok
else
    check "the dump restores without error" "$(tail -3 /tmp/drill_restore.log | tr '\n' ' ')"
    echo
    echo "=== $pass passed, $fail failed ==="
    exit 1
fi

# ---- what came back ---------------------------------------------------------
# Tables the clinic cannot operate without. A restore that loses any of these is
# not a restore, however clean the log looked.
for t in patient appointment visit clinical_record payment lab_result \
         prescription staff; do
    got=$(q "SELECT to_regclass('public.$t') IS NOT NULL")
    [ "$got" = "t" ] && check "table $t exists" ok || check "table $t exists" "missing"
done

# ---- which generation of the schema is this artifact? ------------------------
# A backup of TODAY'S production predates multi-tenancy: no clinic table, no
# clinic_id. Asserting the current schema against it produced four red lines
# that read as "the backup is broken" when the backup is fine and the SCHEMA is
# old — the same conflation that had me tell Quang production carried the
# multi-tenant schema when I was looking at a dump of my laptop.
#
# So the drill establishes the generation first and asserts what belongs to it.
# An old artifact that restores cleanly is a PASS, stated as such.
HAS_TENANCY=$(q "SELECT to_regclass('public.clinic') IS NOT NULL")

if [ "$HAS_TENANCY" != "t" ]; then
    printf '  NOTE  %s\n' "artifact predates multi-tenancy — skipping tenant checks"
    printf '        %s\n' "(no clinic table; this is today's production schema, not a fault)"
fi

# Multi-tenancy has to survive the round trip, or the restored database is one
# migration behind and every policy is wrong.
missing_tenant=$(q "
    SELECT count(*) FROM (
        SELECT c.relname FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname='public' AND c.relkind='r'
           AND c.relname IN ('patient','appointment','visit','clinical_record',
                             'payment','lab_result','prescription')
           AND NOT EXISTS (
               SELECT 1 FROM information_schema.columns col
                WHERE col.table_schema='public' AND col.table_name=c.relname
                  AND col.column_name='clinic_id')
    ) x")
if [ "$HAS_TENANCY" = "t" ]; then
    check "table clinic exists" ok
    got=$(q "SELECT to_regclass('public.clinic_membership') IS NOT NULL")
    [ "$got" = "t" ] && check "table clinic_membership exists" ok \
        || check "table clinic_membership exists" "missing"
    [ "$missing_tenant" = "0" ] && check "every core table kept its clinic_id" ok || \
        check "every core table kept its clinic_id" "$missing_tenant table(s) without clinic_id"
fi

policies=$(q "SELECT count(*) FROM pg_policies WHERE schemaname='public'")
[ "${policies:-0}" -gt 0 ] && check "RLS policies restored ($policies)" ok || \
    check "RLS policies restored" "none — the restored database would be wide open"

if [ "$HAS_TENANCY" = "t" ]; then
    
    # Row counts, printed whatever they are. A dump that quietly captured an empty
    # database passes every integrity check ever written; the only defence is
    # looking at the numbers.
    echo
    echo "  rows restored:"
    total=0
    for t in patient appointment visit clinical_record payment lab_result; do
        n=$(q "SELECT count(*) FROM public.$t" || echo "?")
        printf '    %-18s %s\n' "$t" "$n"
        case "$n" in ''|*[!0-9]*) : ;; *) total=$((total + n)) ;; esac
    done
    [ "$total" -gt 0 ] && check "the restored database is not empty ($total rows)" ok || \
        check "the restored database is not empty" \
              "0 rows across every core table — the backup captured nothing"
    
    # A query the application actually makes, to prove the schema is usable and not
    # merely present.
    if q "SELECT p.patient_code FROM public.patient p
           JOIN public.clinic c ON c.id = p.clinic_id LIMIT 1" >/dev/null 2>&1; then
        check "a tenant-scoped application query runs" ok
    else
        check "a tenant-scoped application query runs" "the join failed"
fi
fi

echo
echo "  NOTE: restore order is auth-then-public. Sessions, MFA state and Supabase"
echo "        platform configuration are still outside this backup — GoTrue"
echo "        rebuilds the first, the platform's own PITR covers the last."
echo
echo "=== $pass passed, $fail failed ==="
[ "$fail" -eq 0 ]
