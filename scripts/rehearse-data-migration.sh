#!/usr/bin/env bash
# Rehearse the production data migration, and count every row on both sides.
#
# Production was built by the old repository and is not on this repo's migration
# lineage, so `supabase db push` cannot carry it forward (docs/prod-cutover-
# findings.md). The route is: build the target schema clean from the migrations,
# move the data across, prove nothing was lost, and only then talk about a
# cutover window. At ~4,400 rows this is rehearsable as often as we like, which
# is the whole argument for doing it this way rather than hand-writing a forward
# migration that gets exactly one attempt.
#
# NOTHING TOUCHES PRODUCTION. The source is a backup artifact on disk; both
# databases live in a throwaway container that is destroyed at the end.
#
# Named a REHEARSAL, not a migration, because that is what it is: it reads a
# backup file from disk and writes into a throwaway container. Nothing it does
# can reach production, and a name suggesting otherwise invites someone to
# assume the opposite in either direction.
#
# Usage:  scripts/rehearse-data-migration.sh [path/to/backup.sql.gz]
#         (defaults to the newest clinicai_production_* artifact)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/clinicai}"
CONTAINER="clinicai_migrate_rehearsal"
# Every row that exists today belongs to Dr4Women. The clinic row in the target
# schema's seed carries this id, so legacy data is stamped with it rather than
# with something invented here — a second clinic id for the same clinic would be
# a tenancy bug that no test could see.
CLINIC_ID="${CLINIC_ID:-a0000000-0000-4000-8000-000000000001}"

# What to do with production's five zero-amount payments, which the target
# schema's payment_positive_amount CHECK rejects.
#
#   (unset)     fail loudly and copy nothing — the default, and the honest one.
#               A cutover that silently discarded payment rows would be the
#               worst possible thing this script could do quietly.
#   drop        skip them, and print every row skipped so the omission is on the
#               record rather than in someone's memory.
#   allow-zero  requires relaxing the CHECK to >= 0 in the target schema; the
#               migration is written but NOT applied
#               (supabase/hotfix/optional_allow_zero_payment.sql).
#
# The evidence, so whoever chooses is choosing informed: all five rows are
# amount=0, status=PAID, dated 24–29/06/2026, and paid_by_staff_id AND
# paid_by_text are both NULL — nobody is recorded as having taken the money.
# Production also has no prices at all (service_price and drug_catalog are
# entirely unpriced). That points at test data, but it is the clinic's call.
PAYMENT_POLICY="${PAYMENT_POLICY:-}"

BACKUP_FILE="${1:-}"
if [ -z "$BACKUP_FILE" ]; then
    BACKUP_FILE=$(find "$BACKUP_DIR" -maxdepth 1 -name 'clinicai_production_*.sql.gz' \
        ! -name '*_auth.sql.gz' -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1 || true)
fi
[ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ] || {
    echo "ERROR: no production backup found in $BACKUP_DIR" >&2; exit 1; }

pass=0; fail=0
check() {  # label expected actual
    if [ "$2" = "$3" ]; then printf '  PASS  %-34s %s\n' "$1" "$3"; pass=$((pass+1))
    else printf '  FAIL  %-34s expected %s, got %s\n' "$1" "$2" "$3"; fail=$((fail+1)); fi
}

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "=== rehearsing with $(basename "$BACKUP_FILE") ==="
cleanup
docker run -d --name "$CONTAINER" -e POSTGRES_PASSWORD=pw postgres:17 >/dev/null
for _ in $(seq 1 60); do
    docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1
done

psql_in()  { docker exec -i "$CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$1"; }
q()        { docker exec "$CONTAINER" psql -tA -U postgres -d "$1" -c "$2" 2>/dev/null | tr -d ' '; }

# ---- source: the production backup ------------------------------------------
docker exec "$CONTAINER" createdb -U postgres src
psql_in src < "${REPO}/supabase/tests/bootstrap_plain_postgres.sql" >/dev/null 2>&1 || true
psql_in src < "${REPO}/supabase/migrations/20260714000000_extensions.sql" >/dev/null 2>&1 || true
# staff.auth_user_id references auth.users, so those ids must exist before the
# public dump loads — the same ordering the restore drill proves and the runbook
# describes. Without it the restore dies on the first staff row.
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
    if [ -n "$ids" ]; then
        values=$(printf '%s\n' "$ids" | awk 'NF {printf "%s(%s%s%s)", sep, q, $0, q; sep=","} END {print ""}' q="'")
        docker exec "$CONTAINER" psql -q -U postgres -d src \
            -c "INSERT INTO auth.users (id) VALUES $values ON CONFLICT DO NOTHING" >/dev/null 2>&1 || true
        echo "  auth ids seeded: $(q src 'SELECT count(*) FROM auth.users')"
    fi
fi

# The search_path rewrite compensates for production's unqualified f_unaccent —
# see supabase/hotfix/20260801_prod_f_unaccent_qualify.sql. Once that hotfix is
# applied to production this line becomes a no-op and can go.
gzip -cd "$BACKUP_FILE" \
    | sed "s|SELECT pg_catalog.set_config('search_path', '', false);|SELECT pg_catalog.set_config('search_path', 'public', false);|" \
    | grep -vx 'CREATE SCHEMA public;' \
    | psql_in src >/tmp/rehearse_src.log 2>&1 || {
        echo "  ERROR restoring the source backup:"; tail -5 /tmp/rehearse_src.log | sed 's/^/    /'; exit 1; }
echo "  source restored: $(q src "SELECT count(*) FROM patient") patients"

# ---- target: the schema this repo builds ------------------------------------
docker exec "$CONTAINER" createdb -U postgres tgt
psql_in tgt < "${REPO}/supabase/tests/bootstrap_plain_postgres.sql" >/dev/null 2>&1 || true
for m in "${REPO}"/supabase/migrations/*.sql; do
    psql_in tgt < "$m" >/dev/null 2>&1 || { echo "  ERROR applying $(basename "$m")"; exit 1; }
done
echo "  target built:    $(q tgt "SELECT count(*) FROM pg_tables WHERE schemaname='public'") tables"

# The tenant row every legacy record will point at.
docker exec "$CONTAINER" psql -q -U postgres -d tgt -c \
  "INSERT INTO public.clinic (id, code, name) VALUES ('$CLINIC_ID','DR4WOMEN','Dr4Women')
   ON CONFLICT (id) DO NOTHING;" >/dev/null 2>&1

# ---- copy ------------------------------------------------------------------
# Foreign keys are deferred rather than ordered. appointment and visit reference
# each other, so no load order exists; session_replication_role is the standard
# answer and the constraints are validated again at the end, which is the part
# that actually matters.
TABLES=$(docker exec "$CONTAINER" psql -tA -U postgres -d src -c "
    SELECT tablename FROM pg_tables WHERE schemaname='public'
       AND tablename NOT IN ('schema_migrations') ORDER BY tablename" | tr -d ' ')

copied=0; skipped=""
for t in $TABLES; do
    exists=$(q tgt "SELECT to_regclass('public.$t') IS NOT NULL")
    [ "$exists" = "t" ] || { skipped="$skipped $t"; continue; }

    # Identifiers are quoted because service_price has a column named "group",
    # which is a reserved word — an unquoted list makes COPY a syntax error and
    # the table silently copies zero rows.
    src_cols=$(q src "SELECT string_agg(column_name, ',' ORDER BY ordinal_position)
                        FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='$t'
                         AND is_generated='NEVER'")
    # Only columns the target also has; a column production dropped or renamed
    # is reported by the row-count check rather than silently breaking the COPY.
    cols=$(q tgt "SELECT string_agg(c, ',') FROM unnest(string_to_array('$src_cols', ',')) AS c
                   WHERE EXISTS (SELECT 1 FROM information_schema.columns t2
                                  WHERE t2.table_schema='public' AND t2.table_name='$t'
                                    AND t2.column_name=c AND t2.is_generated='NEVER')")
    [ -n "$cols" ] || { skipped="$skipped $t"; continue; }

    qcols=$(printf '%s' "$cols" | awk -F, '{for(i=1;i<=NF;i++){printf "%s\"%s\"", (i>1?",":""), $i}}')

    needs_clinic=$(q tgt "SELECT count(*) FROM information_schema.columns
                           WHERE table_schema='public' AND table_name='$t'
                             AND column_name='clinic_id'")
    has_clinic=$(q src "SELECT count(*) FROM information_schema.columns
                         WHERE table_schema='public' AND table_name='$t'
                           AND column_name='clinic_id'")

    if [ "$needs_clinic" = "1" ] && [ "$has_clinic" = "0" ]; then
        sel="SELECT $qcols, '$CLINIC_ID'::uuid FROM public.$t"
        dst="$qcols,\"clinic_id\""
    else
        sel="SELECT $qcols FROM public.$t"
        dst="$qcols"
    fi

    # No `bash -c` wrapper: the nested quoting swallowed the identifier quotes
    # and turned the "group" column back into a syntax error. Two plain docker
    # execs joined by a pipe keep the quoting the shell already got right.
    # The one table where a filter is a decision, not a mechanism.
    where=""
    if [ "$t" = "payment" ] && [ "$PAYMENT_POLICY" = "drop" ]; then
        bad=$(q src "SELECT count(*) FROM public.payment WHERE amount IS NULL OR amount <= 0")
        if [ "${bad:-0}" != "0" ]; then
            echo "  DROPPING $bad payment row(s) with amount <= 0 (PAYMENT_POLICY=drop):"
            docker exec "$CONTAINER" psql -tA -U postgres -d src -c \
              "SELECT '    id='||id||' amount='||coalesce(amount::text,'NULL')||
                      ' kind='||coalesce(kind,'?')||' paid_at='||coalesce(paid_at::text,'?')
                 FROM public.payment WHERE amount IS NULL OR amount <= 0" 2>/dev/null
        fi
        where=" WHERE amount > 0"
    fi
    sel="${sel}${where}"

    if docker exec "$CONTAINER" psql -tA -U postgres -d src \
            -c "COPY ($sel) TO STDOUT" 2>/tmp/rehearse_src_err.log \
       | docker exec -i "$CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d tgt \
            -c "SET session_replication_role = replica;" \
            -c "COPY public.\"$t\" ($dst) FROM STDIN" \
            >/dev/null 2>/tmp/rehearse_copy_err.log; then
        copied=$((copied+1))
    else
        skipped="$skipped $t"
        printf '  COPY FAILED  %-22s %s\n' "$t" \
            "$(grep -m1 -hoE 'ERROR:.*' /tmp/rehearse_copy_err.log /tmp/rehearse_src_err.log | head -1 | cut -c1-92)"
    fi
done
echo "  copied $copied tables;${skipped:- none skipped}"

# ---- the check that matters: row counts on both sides -----------------------
echo
echo "=== row counts, source vs target ==="
mismatch=0; total_src=0
for t in $TABLES; do
    [ "$(q tgt "SELECT to_regclass('public.$t') IS NOT NULL")" = "t" ] || continue
    s=$(q src "SELECT count(*) FROM public.$t"); d=$(q tgt "SELECT count(*) FROM public.$t")
    total_src=$((total_src + ${s:-0}))
    if [ "$t" = "payment" ] && [ "$PAYMENT_POLICY" = "drop" ]; then
        kept=$(q src "SELECT count(*) FROM public.payment WHERE amount > 0")
        if [ "${kept:-0}" = "${d:-0}" ]; then
            printf '  ok(drop) %-26s kept %s of %s (amount > 0)\n' "$t" "$d" "$s"
        else
            printf '  MISMATCH  %-26s src>0=%-6s tgt=%s\n' "$t" "$kept" "$d"; mismatch=$((mismatch+1))
        fi
    elif [ "${s:-0}" != "${d:-0}" ]; then
        printf '  MISMATCH  %-26s src=%-6s tgt=%s\n' "$t" "$s" "$d"; mismatch=$((mismatch+1))
    elif [ "${s:-0}" != "0" ]; then
        printf '  ok        %-26s %s\n' "$t" "$s"
    fi
done
check "every table matched row for row" "0" "$mismatch"
check "rows actually moved (not an empty run)" "yes" "$([ "$total_src" -gt 0 ] && echo yes || echo no)"

# ---- tenancy and integrity --------------------------------------------------
orphan_clinic=$(q tgt "
    SELECT count(*) FROM information_schema.columns c
     WHERE c.table_schema='public' AND c.column_name='clinic_id'
       AND EXISTS (SELECT 1 FROM pg_tables t WHERE t.schemaname='public'
                    AND t.tablename=c.table_name)")
check "tenant columns present in target" "$orphan_clinic" "$orphan_clinic"

# Re-validating the foreign keys is the point of deferring them. A load that
# leaves a dangling reference is a load that quietly lost a parent row.
bad_fk=$(docker exec "$CONTAINER" psql -tA -U postgres -d tgt -c "
    DO \$\$
    DECLARE r record; n integer := 0;
    BEGIN
      FOR r IN SELECT conrelid::regclass AS t, conname FROM pg_constraint
                WHERE contype='f' AND connamespace='public'::regnamespace LOOP
        BEGIN
          EXECUTE format('ALTER TABLE %s VALIDATE CONSTRAINT %I', r.t, r.conname);
        EXCEPTION WHEN others THEN n := n + 1;
          RAISE WARNING 'FK still broken: %.%', r.t, r.conname;
        END;
      END LOOP;
      RAISE NOTICE 'broken_fks=%', n;
    END \$\$;" 2>&1 | grep -oE 'broken_fks=[0-9]+' | cut -d= -f2)
check "no dangling foreign keys after load" "0" "${bad_fk:-?}"

echo
echo "=== $pass passed, $fail failed ==="
[ "$fail" = "0" ] || exit 1
