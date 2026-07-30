-- Regression assertions for 20260717000001_event_log_least_privilege.sql.
-- Run after migrations against a disposable Supabase database:
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/event_log_rls.sql

BEGIN;

DO $assertions$
DECLARE
    policy_roles name[];
    policy_using text;
    permissive_policy_count integer;
BEGIN
    SELECT roles, qual
      INTO policy_roles, policy_using
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'event_log'
       AND policyname = 'event_log_select_management';

    IF policy_roles IS NULL THEN
        RAISE EXCEPTION 'missing event_log_select_management policy';
    END IF;

    IF NOT ('authenticated'::name = ANY (policy_roles)) THEN
        RAISE EXCEPTION 'event_log policy must apply to authenticated';
    END IF;

    IF position('current_staff_department' IN coalesce(policy_using, '')) = 0
       OR position('MANAGEMENT' IN coalesce(policy_using, '')) = 0 THEN
        RAISE EXCEPTION 'event_log policy is not scoped to MANAGEMENT: %', policy_using;
    END IF;

    SELECT count(*)
      INTO permissive_policy_count
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'event_log'
       AND cmd IN ('SELECT', 'ALL')
       AND (
           policyname = 'event_log_select_authenticated'
           OR coalesce(qual, '') IN ('true', '(true)')
       );

    IF permissive_policy_count <> 0 THEN
        RAISE EXCEPTION 'event_log still has % unrestricted read policies',
            permissive_policy_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.proname = 'current_staff_department'
           AND p.prosecdef
           AND p.provolatile = 's'
    ) THEN
        RAISE EXCEPTION 'current_staff_department must be STABLE SECURITY DEFINER';
    END IF;
END
$assertions$;

-- Behaviour checks. Grants and fixtures are transaction-local and rolled back.
INSERT INTO auth.users (id)
VALUES
    ('10000000-0000-0000-0000-000000000001'),
    ('10000000-0000-0000-0000-000000000002'),
    ('10000000-0000-0000-0000-000000000003');

INSERT INTO public.staff (id, full_name, primary_department, auth_user_id)
VALUES
    (
        '20000000-0000-0000-0000-000000000001',
        'RLS test manager',
        'MANAGEMENT',
        '10000000-0000-0000-0000-000000000001'
    ),
    (
        '20000000-0000-0000-0000-000000000002',
        'RLS test receptionist',
        'RECEPTION',
        '10000000-0000-0000-0000-000000000002'
    );

-- Since W3 (20260730000004) reading anything also requires active membership of
-- the clinic that owns the row. The staff inserts above get theirs from the
-- staff_ensure_default_membership trigger, which resolves the clinic while the
-- deployment is single-tenant.

INSERT INTO public.event_log (
    event_id,
    clinic_id,
    event_type,
    aggregate_type,
    aggregate_id,
    payload,
    source
)
VALUES (
    '30000000-0000-0000-0000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'patient.updated',
    'patient',
    '40000000-0000-0000-0000-000000000001',
    '{"status":"test"}',
    'rls-test'
);

GRANT SELECT ON public.event_log TO authenticated, service_role;

SET LOCAL ROLE authenticated;
SELECT set_config(
    'request.jwt.claim.sub',
    '10000000-0000-0000-0000-000000000002',
    true
);

DO $reception_cannot_read$
BEGIN
    IF (SELECT count(*) FROM public.event_log) <> 0 THEN
        RAISE EXCEPTION 'RECEPTION must not read event_log';
    END IF;
END
$reception_cannot_read$;

SELECT set_config(
    'request.jwt.claim.sub',
    '10000000-0000-0000-0000-000000000001',
    true
);

DO $management_can_read$
BEGIN
    -- "can read", not "reads exactly one row": every e2e run adds real events,
    -- so pinning the count made an unrelated test run look like an RLS break.
    -- The row this test inserted is the one that must be visible.
    IF NOT EXISTS (
        SELECT 1 FROM public.event_log
         WHERE aggregate_id = '40000000-0000-0000-0000-000000000001'
    ) THEN
        RAISE EXCEPTION 'linked active MANAGEMENT must read event_log';
    END IF;
END
$management_can_read$;

SELECT set_config(
    'request.jwt.claim.sub',
    '10000000-0000-0000-0000-000000000003',
    true
);

DO $unlinked_cannot_read$
BEGIN
    IF (SELECT count(*) FROM public.event_log) <> 0 THEN
        RAISE EXCEPTION 'unlinked authenticated user must not read event_log';
    END IF;
END
$unlinked_cannot_read$;

RESET ROLE;
SET LOCAL ROLE service_role;

DO $service_role_compatible$
BEGIN
    -- Same reason as above: presence, not an exact count.
    IF NOT EXISTS (
        SELECT 1 FROM public.event_log
         WHERE aggregate_id = '40000000-0000-0000-0000-000000000001'
    ) THEN
        RAISE EXCEPTION 'service_role must retain event_log access';
    END IF;
END
$service_role_compatible$;

RESET ROLE;

ROLLBACK;
