-- Assertions for 20260802000004_clinic_secret.sql.
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/clinic_secret.sql
--
-- The bug this file exists to prevent came back to life twice in one schema:
-- a GRANT wide enough to expose a column nobody meant to publish, and a policy
-- that looks like protection while granting none. Both are asserted directly
-- against the privilege system rather than read off the migration text.

BEGIN;

DO $secret_table$
DECLARE
    policy_count integer;
    offenders text;
BEGIN
    IF to_regclass('public.clinic_secret') IS NULL THEN
        RAISE EXCEPTION 'clinic_secret is missing';
    END IF;

    IF NOT (SELECT relrowsecurity FROM pg_class
             WHERE oid = 'public.clinic_secret'::regclass) THEN
        RAISE EXCEPTION 'row level security is off on clinic_secret';
    END IF;

    -- Zero policies is the design, not an oversight: 20260730000008 hands a
    -- SELECT grant to authenticated for every table that has a read policy, so
    -- the day this table gets one it also gets a client-readable door.
    SELECT count(*) INTO policy_count
      FROM pg_policy WHERE polrelid = 'public.clinic_secret'::regclass;
    IF policy_count <> 0 THEN
        RAISE EXCEPTION 'clinic_secret must have no policies, found %', policy_count;
    END IF;

    SELECT string_agg(grantee || ':' || priv, ', ') INTO offenders
      FROM unnest(ARRAY['anon', 'authenticated']) AS grantee,
           unnest(ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']) AS priv
     WHERE has_table_privilege(grantee, 'public.clinic_secret', priv);
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'clinic_secret is reachable from the browser: %', offenders;
    END IF;

    IF NOT has_table_privilege('service_role', 'public.clinic_secret', 'SELECT') THEN
        RAISE EXCEPTION 'the backend cannot read clinic_secret';
    END IF;
END
$secret_table$;

DO $clinic_columns$
DECLARE
    readable constant text[] := ARRAY['id', 'code', 'name', 'timezone', 'is_active'];
    hidden constant text[] := ARRAY['settings', 'legal_name', 'tax_code', 'address'];
    offenders text;
BEGIN
    -- A row policy filters rows. It has never filtered columns, which is why
    -- `GRANT SELECT ON public.clinic` was enough to publish every credential
    -- in settings to anyone holding a staff JWT.
    IF has_table_privilege('authenticated', 'public.clinic', 'SELECT') THEN
        RAISE EXCEPTION
            'authenticated holds table-wide SELECT on clinic — settings is readable';
    END IF;

    SELECT string_agg(col, ', ') INTO offenders
      FROM unnest(readable) AS col
     WHERE NOT has_column_privilege('authenticated', 'public.clinic', col, 'SELECT');
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'authenticated lost columns it needs on clinic: %', offenders;
    END IF;

    SELECT string_agg(col, ', ') INTO offenders
      FROM unnest(hidden) AS col
     WHERE has_column_privilege('authenticated', 'public.clinic', col, 'SELECT');
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'authenticated can read clinic columns it must not: %', offenders;
    END IF;
END
$clinic_columns$;

DO $no_credentials_left_behind$
DECLARE
    leftovers integer;
BEGIN
    -- End state of the move, as a property rather than a row count: true on a
    -- fresh database and meaningful on production.
    SELECT count(*) INTO leftovers
      FROM public.clinic
     WHERE settings -> 'pos' ?| ARRAY['retailer', 'client_id',
                                      'client_secret', 'branch_id'];
    IF leftovers <> 0 THEN
        RAISE EXCEPTION '% clinics still keep POS credentials in settings', leftovers;
    END IF;
END
$no_credentials_left_behind$;

-- Behaviour. Fixtures and grants are transaction-local and roll back.
INSERT INTO auth.users (id) VALUES ('10000000-0000-0000-0000-0000000000b1');

INSERT INTO public.staff (id, full_name, primary_department, auth_user_id)
VALUES (
    '20000000-0000-0000-0000-0000000000b1',
    'Secret test manager',
    'MANAGEMENT',
    '10000000-0000-0000-0000-0000000000b1'
);

-- A scope of its own: on a database where the migration already moved real
-- credentials there is a 'pos' row, and a fixture that collides with it turns
-- an assertion file into a unique-violation on exactly the deployment it was
-- written to protect.
INSERT INTO public.clinic_secret (clinic_id, scope, secret)
VALUES (
    'a0000000-0000-4000-8000-000000000001',
    'probe',
    '{"client_secret":"must-never-be-readable"}'
);

SET LOCAL ROLE authenticated;
SELECT set_config(
    'request.jwt.claim.sub',
    '10000000-0000-0000-0000-0000000000b1',
    true
);

DO $browser_cannot_reach_secrets$
BEGIN
    BEGIN
        PERFORM secret FROM public.clinic_secret;
        RAISE EXCEPTION 'a staff JWT read clinic_secret';
    EXCEPTION
        WHEN insufficient_privilege THEN NULL;
    END;

    BEGIN
        PERFORM settings FROM public.clinic;
        RAISE EXCEPTION 'a staff JWT read clinic.settings';
    EXCEPTION
        WHEN insufficient_privilege THEN NULL;
    END;

    -- And the columns the app legitimately needs still work, otherwise this
    -- migration trades a leak for an outage.
    PERFORM id, code, name, timezone, is_active FROM public.clinic;
END
$browser_cannot_reach_secrets$;

RESET ROLE;

DO $backend_can_reach_secrets$
BEGIN
    SET LOCAL ROLE service_role;
    IF NOT EXISTS (
        SELECT 1 FROM public.clinic_secret
         WHERE scope = 'probe'
           AND secret ->> 'client_secret' = 'must-never-be-readable'
    ) THEN
        RAISE EXCEPTION 'the backend cannot read the POS credentials it must push with';
    END IF;
    RESET ROLE;
END
$backend_can_reach_secrets$;

ROLLBACK;
