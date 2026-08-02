-- Tenant invariants, derived from the schema instead of listed by hand.
-- Run after migrations against a disposable database:
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/tenant_invariants.sql
--
-- Every other assertion file names the tables it checks. That is right for the
-- rules those files encode and useless for the rule this one encodes, because
-- the failure it exists to catch IS a table nobody remembered. drug_batch and
-- inventory_txn arrived in 20260802000001 carrying a clinic_id DEFAULT and no
-- GRANT, and not one gate objected — none of them had heard of those two tables.
-- A hand-written list can only ever be as complete as the last person's memory.
--
-- So every list below is a query. Table 51 is covered the day it is created,
-- by nobody's diligence.
--
-- MUST run against a database where the migrations were applied EXACTLY ONCE —
-- the shape `supabase db push` produces in production. Applying them twice
-- repairs both of the bugs above before this file gets to look at them, which is
-- precisely how they reached main. See db_fresh / db_replay in ci.yml.

BEGIN;

DO $tenant_invariants$
DECLARE
    offenders text;
    tenant_count integer;
    -- Tables that legitimately carry no clinic_id, and the reason each one is
    -- allowed to. Anything not on this list and without clinic_id is a table
    -- that was never classified — which is the state drug_batch was in.
    shared_tables constant text[] := ARRAY[
        'clinic',             -- is the tenant
        'clinic_membership',  -- maps staff to tenants; carries clinic_id as a value, not a scope
        'province',           -- national reference data
        'ward',               -- national reference data
        'staff',              -- multi-clinic, scoped through clinic_membership
        'staff_capability',   -- scoped through staff
        'idempotency_key',    -- infra, actor-scoped and short-lived
        'schema_migrations',  -- CLI bookkeeping
        -- Feedback about the SOFTWARE, not about a clinic's data (20260801000004
        -- argues this at length). Nobody but service_role can read it, so it is
        -- fail-closed today. The day it is shown to clinic staff it needs
        -- clinic_id and this line has to go.
        'owner_feedback'
    ];
BEGIN
    -- Derived once; every check below reads from it.
    CREATE TEMP TABLE tenant_table ON COMMIT DROP AS
    SELECT c.oid, c.relname,
           (SELECT a.attnum FROM pg_attribute a
             WHERE a.attrelid = c.oid AND a.attname = 'clinic_id') AS clinic_attnum
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind = 'r'
       AND c.relname <> ALL (shared_tables)
       AND EXISTS (SELECT 1 FROM pg_attribute a
                    WHERE a.attrelid = c.oid AND a.attname = 'clinic_id'
                      AND a.attnum > 0 AND NOT a.attisdropped);

    SELECT count(*) INTO tenant_count FROM tenant_table;

    -- 0a. The allowlist must be exhaustive: no unclassified table may exist.
    SELECT string_agg(c.relname, ', ' ORDER BY c.relname) INTO offenders
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind = 'r'
       AND c.relname <> ALL (shared_tables)
       AND NOT EXISTS (SELECT 1 FROM pg_attribute a
                        WHERE a.attrelid = c.oid AND a.attname = 'clinic_id'
                          AND a.attnum > 0 AND NOT a.attisdropped);
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION
            'table without clinic_id and not on the shared allowlist: %. '
            'Either give it clinic_id or add it to shared_tables with a reason.',
            offenders;
    END IF;

    -- 0b. And checked in the other direction, like every allowlist in this repo:
    -- an entry naming a table that no longer exists reads as review nobody did.
    SELECT string_agg(s, ', ' ORDER BY s) INTO offenders
      FROM unnest(shared_tables) AS s
     WHERE to_regclass('public.' || quote_ident(s)) IS NULL;
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'shared_tables names tables that do not exist: %', offenders;
    END IF;

    -- 1. A nullable clinic_id is a row belonging to no tenant at all.
    SELECT string_agg(t.relname, ', ' ORDER BY t.relname) INTO offenders
      FROM tenant_table t
      JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = t.clinic_attnum
     WHERE NOT a.attnotnull;
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'clinic_id must be NOT NULL, but is nullable on: %', offenders;
    END IF;

    -- 2. A DEFAULT is worse than a missing value. 20260730000014 removed
    -- default_clinic_id() from every table for a reason: with it, clinic #2
    -- forgetting clinic_id writes into Dr4Women silently, and a silent wrong
    -- answer beats a NOT NULL violation to production every time.
    SELECT string_agg(t.relname, ', ' ORDER BY t.relname) INTO offenders
      FROM tenant_table t
      JOIN pg_attrdef d ON d.adrelid = t.oid AND d.adnum = t.clinic_attnum;
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'clinic_id must have no DEFAULT, but one is set on: %', offenders;
    END IF;

    -- 3. Without an FK a tenant can be deleted out from under its own data.
    SELECT string_agg(t.relname, ', ' ORDER BY t.relname) INTO offenders
      FROM tenant_table t
     WHERE NOT EXISTS (
        SELECT 1 FROM pg_constraint fk
         WHERE fk.conrelid = t.oid
           AND fk.contype = 'f'
           AND fk.confrelid = 'public.clinic'::regclass
           AND fk.conkey = ARRAY[t.clinic_attnum]);
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'clinic_id must reference public.clinic, missing on: %', offenders;
    END IF;

    -- 4. Every read is scoped by clinic_id, so every table needs an index that
    -- starts with it. Without one, tenant isolation is paid for with a seq scan
    -- on somebody else's rows.
    SELECT string_agg(t.relname, ', ' ORDER BY t.relname) INTO offenders
      FROM tenant_table t
     WHERE NOT EXISTS (
        SELECT 1 FROM pg_index i
         WHERE i.indrelid = t.oid AND i.indkey[0] = t.clinic_attnum);
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'no index leading with clinic_id on: %', offenders;
    END IF;

    -- 5. RLS off means the browser's anon key reads every clinic.
    SELECT string_agg(t.relname, ', ' ORDER BY t.relname) INTO offenders
      FROM tenant_table t
      JOIN pg_class c ON c.oid = t.oid
     WHERE NOT c.relrowsecurity;
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'row level security is off on: %', offenders;
    END IF;

    -- 6. A policy that does not consult membership is a policy in name only.
    -- This is the check that catches a regression to USING (true) on a table
    -- that already looked protected.
    SELECT string_agg(t.relname || '.' || p.polname, ', ' ORDER BY t.relname || '.' || p.polname)
      INTO offenders
      FROM tenant_table t
      JOIN pg_policy p ON p.polrelid = t.oid
     WHERE p.polcmd IN ('r', '*')
       AND coalesce(pg_get_expr(p.polqual, p.polrelid), '')
           !~ '(current_clinic_ids|current_clinical_clinic_ids)';
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION
            'SELECT policy does not consult current_clinic_ids: %', offenders;
    END IF;

    -- 7. Grant and policy have to agree, in both directions.
    --
    -- A policy narrows privileges that already exist; it never creates them. So
    -- a table with a perfect policy and no GRANT answers every browser query
    -- with permission denied (drug_batch, until 20260802000002), and a table
    -- with a GRANT and no policy answers every browser query with every
    -- clinic's rows. The two failures look nothing alike and have one cause.
    SELECT string_agg(t.relname, ', ' ORDER BY t.relname) INTO offenders
      FROM tenant_table t
     WHERE has_table_privilege('authenticated', t.oid, 'SELECT')
       AND NOT EXISTS (SELECT 1 FROM pg_policy p
                        WHERE p.polrelid = t.oid AND p.polcmd IN ('r', '*'));
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION
            'authenticated can SELECT but no policy restricts it (reads every clinic): %',
            offenders;
    END IF;

    SELECT string_agg(t.relname, ', ' ORDER BY t.relname) INTO offenders
      FROM tenant_table t
     WHERE NOT has_table_privilege('authenticated', t.oid, 'SELECT')
       AND EXISTS (SELECT 1 FROM pg_policy p
                    WHERE p.polrelid = t.oid AND p.polcmd IN ('r', '*'));
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION
            'SELECT policy exists but authenticated was never granted SELECT '
            '(every read returns permission denied): %', offenders;
    END IF;

    RAISE NOTICE 'tenant invariants hold on % tenant-scoped tables', tenant_count;
END
$tenant_invariants$;

-- The rules above are per-table. These are about the schema as a whole, and
-- they hold for shared tables too, so they are derived over all of public.
DO $global_boundaries$
DECLARE
    offenders text;
    public_read_tables constant text[] := ARRAY['province', 'ward'];
BEGIN
    -- ADR-0012: the database grants the browser no write path at all. Not "the
    -- frontend is disciplined about writes" — there is no policy to write
    -- through, and no privilege behind it either.
    SELECT string_agg(c.relname || '.' || p.polname, ', ') INTO offenders
      FROM pg_policy p
      JOIN pg_class c ON c.oid = p.polrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND p.polcmd IN ('a', 'w', 'd');
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'write policy in public (ADR-0012 says there are none): %', offenders;
    END IF;

    SELECT string_agg(c.relname, ', ' ORDER BY c.relname) INTO offenders
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind = 'r'
       AND (has_table_privilege('authenticated', c.oid, 'INSERT')
         OR has_table_privilege('authenticated', c.oid, 'UPDATE')
         OR has_table_privilege('authenticated', c.oid, 'DELETE'));
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'authenticated holds a write privilege on: %', offenders;
    END IF;

    -- anon is the key shipped inside the JavaScript bundle. It reads nothing.
    SELECT string_agg(c.relname, ', ' ORDER BY c.relname) INTO offenders
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind = 'r'
       AND has_table_privilege('anon', c.oid, 'SELECT');
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'anon can read: %', offenders;
    END IF;

    -- The backend is the only writer, so a missing service_role grant is an
    -- outage on the first write rather than a leak — silent until then, because
    -- 20260801000003 hand-wrote the read grants and the write grants went with
    -- a loop that had already run.
    SELECT string_agg(c.relname, ', ' ORDER BY c.relname) INTO offenders
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind = 'r'
       AND NOT has_table_privilege('service_role', c.oid, 'INSERT');
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'service_role cannot write: %', offenders;
    END IF;

    -- USING (true) is the shape a scoped policy decays into. Allowed only where
    -- the rows really are the same for every tenant.
    SELECT string_agg(c.relname || '.' || p.polname, ', ') INTO offenders
      FROM pg_policy p
      JOIN pg_class c ON c.oid = p.polrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND p.polcmd IN ('r', '*')
       AND pg_get_expr(p.polqual, p.polrelid) = 'true'
       AND c.relname <> ALL (public_read_tables);
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'SELECT policy is USING (true) outside reference data: %', offenders;
    END IF;

    RAISE NOTICE 'global read/write boundaries hold';
END
$global_boundaries$;

ROLLBACK;
