-- Regression assertions for 20260730000003_multi_tenant_foundation.sql (ADR-0009).
-- Run after migrations against a disposable database:
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/multi_tenant_foundation.sql
--
-- These are the invariants that make multi-tenancy real rather than aspirational:
-- every business table carries the tenant, tenant columns cannot be null, human
-- readable codes are unique per tenant rather than globally, and a member of one
-- clinic cannot see another clinic.

BEGIN;

DO $structure$
DECLARE
    missing text;
    nullable text;
    unindexed text;
    leaked text;
    -- Tables that must NOT be tenant-scoped, and why.
    shared_tables text[] := ARRAY[
        'province',           -- national reference
        'ward',               -- national reference
        'staff',              -- multi-clinic, scoped via clinic_membership
        'staff_capability',   -- scoped via staff
        'idempotency_key',    -- infra, actor-scoped
        'schema_migrations',  -- CLI bookkeeping
        'clinic',             -- is the tenant
        'owner_feedback'      -- feedback about the software, not a clinic's data
    ];
BEGIN
    -- The count of tenant tables used to be pinned here, at 41, with a comment
    -- claiming it caught both directions. It caught neither one that mattered:
    -- a new table that forgets clinic_id does not change the count, so
    -- owner_feedback sat outside tenancy unnoticed, and drug_batch was counted
    -- while shipping with a DEFAULT and no GRANT. tenant_invariants.sql now
    -- derives the whole classification from the schema and requires every
    -- public table to be either tenant-scoped or named on an allowlist, which
    -- is the check this number was standing in for.

    -- A nullable clinic_id is a hole: rows could land outside every tenant.
    SELECT string_agg(c.table_name, ', ') INTO nullable
      FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name
     WHERE c.table_schema = 'public'
       AND c.column_name = 'clinic_id'
       AND t.table_type = 'BASE TABLE'
       AND c.is_nullable = 'YES';

    IF nullable IS NOT NULL THEN
        RAISE EXCEPTION 'clinic_id must be NOT NULL, but is nullable on: %', nullable;
    END IF;

    -- Without an FK a tenant could be deleted out from under its data.
    SELECT string_agg(c.table_name, ', ') INTO missing
      FROM information_schema.columns c
      JOIN information_schema.tables tt
        ON tt.table_schema = c.table_schema AND tt.table_name = c.table_name
     WHERE c.table_schema = 'public'
       AND c.column_name = 'clinic_id'
       AND tt.table_type = 'BASE TABLE'
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint k
            WHERE k.contype = 'f'
              AND k.conrelid = format('public.%I', c.table_name)::regclass
              AND k.confrelid = 'public.clinic'::regclass
       );

    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'clinic_id without FK to clinic on: %', missing;
    END IF;

    -- Every tenant-scoped read filters on clinic_id, so it must lead an index.
    SELECT string_agg(c.table_name, ', ') INTO unindexed
      FROM information_schema.columns c
      JOIN information_schema.tables tt
        ON tt.table_schema = c.table_schema AND tt.table_name = c.table_name
     WHERE c.table_schema = 'public'
       AND c.column_name = 'clinic_id'
       AND tt.table_type = 'BASE TABLE'
       AND NOT EXISTS (
           SELECT 1
             FROM pg_index i
             JOIN pg_class t ON t.oid = i.indrelid
             JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = i.indkey[0]
            WHERE t.relname = c.table_name
              AND a.attname = 'clinic_id'
       );

    IF unindexed IS NOT NULL THEN
        RAISE EXCEPTION 'clinic_id is not the leading index column on: %', unindexed;
    END IF;

    SELECT string_agg(table_name, ', ') INTO leaked
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND column_name = 'clinic_id'
       AND table_name = ANY (shared_tables);

    IF leaked IS NOT NULL THEN
        RAISE EXCEPTION 'shared/reference tables must stay tenant-free, but got clinic_id on: %', leaked;
    END IF;
END
$structure$;

-- The count is pinned on purpose and catches BOTH directions: a new table that
-- forgot clinic_id, and an existing one that lost it. It moves only when the
-- change is deliberate — 36 → 39 on 01/08/2026, when visit_amendment,
-- patient_contact_channel and patient_next_of_kin were adopted from the
-- production schema (migration 20260801000003) and brought under tenancy.
DO $unique_keys$
DECLARE
    stale text;
    scoped integer;
BEGIN
    -- Human-meaningful codes collide across tenants unless the key carries one.
    SELECT string_agg(conname, ', ') INTO stale
      FROM pg_constraint
     WHERE contype = 'u'
       AND connamespace = 'public'::regnamespace
       AND conname IN (
           'booking_channel_code_key', 'clinic_location_code_key',
           'service_type_code_key', 'drug_catalog_name_raw_key',
           'patient_patient_code_key'
       );

    IF stale IS NOT NULL THEN
        RAISE EXCEPTION 'globally unique business codes still present: %', stale;
    END IF;

    SELECT count(*) INTO scoped
      FROM pg_constraint
     WHERE contype = 'u'
       AND connamespace = 'public'::regnamespace
       AND conname IN (
           'uq_booking_channel_clinic_code', 'uq_clinic_location_clinic_code',
           'uq_service_type_clinic_code', 'uq_drug_catalog_clinic_name_raw',
           'uq_patient_clinic_code'
       );

    IF scoped <> 5 THEN
        RAISE EXCEPTION 'expected 5 tenant-scoped code constraints, found %', scoped;
    END IF;

    SELECT count(*) INTO scoped
      FROM pg_indexes
     WHERE schemaname = 'public'
       AND indexname IN (
           'idx_patient_clinic_national_id_unique', 'uq_service_price_clinic_code_group',
           'uq_block_budget_key', 'uq_care_episode_live'
       )
       AND indexdef LIKE '%clinic_id%';

    IF scoped <> 4 THEN
        RAISE EXCEPTION 'expected 4 tenant-scoped unique indexes, found %', scoped;
    END IF;
END
$unique_keys$;

DO $helpers$
BEGIN
    -- Policies call these, so they must be SECURITY DEFINER (otherwise reading
    -- clinic_membership to decide access to clinic_membership recurses) and
    -- STABLE (otherwise the planner re-evaluates them per row).
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public' AND p.proname = 'current_staff_id'
           AND p.prosecdef AND p.provolatile = 's'
    ) THEN
        RAISE EXCEPTION 'current_staff_id must be STABLE SECURITY DEFINER';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public' AND p.proname = 'current_clinic_ids'
           AND p.prosecdef AND p.provolatile = 's'
    ) THEN
        RAISE EXCEPTION 'current_clinic_ids must be STABLE SECURITY DEFINER';
    END IF;
END
$helpers$;

-- Behaviour checks. Fixtures are transaction-local and rolled back.
INSERT INTO auth.users (id)
VALUES
    ('11111111-1111-4111-8111-111111111111'),
    ('22222222-2222-4222-8222-222222222222'),
    ('33333333-3333-4333-8333-333333333333');

DO $single_tenant_default$
BEGIN
    IF public.default_clinic_id() <> 'a0000000-0000-4000-8000-000000000001'::uuid THEN
        RAISE EXCEPTION 'default_clinic_id must resolve while exactly one clinic exists';
    END IF;
END
$single_tenant_default$;

INSERT INTO public.clinic (id, code, name)
VALUES ('b0000000-0000-4000-8000-000000000002', 'OTHER', 'Phòng khám khác');

DO $second_tenant_disables_default$
BEGIN
    -- The transitional default must stop guessing the moment guessing is wrong.
    IF public.default_clinic_id() IS NOT NULL THEN
        RAISE EXCEPTION 'default_clinic_id must be NULL once a second clinic exists';
    END IF;
END
$second_tenant_disables_default$;

INSERT INTO public.staff (id, full_name, primary_department, auth_user_id)
VALUES
    ('c0000000-0000-4000-8000-00000000000a', 'Tenant test A', 'DOCTOR',
     '11111111-1111-4111-8111-111111111111'),
    ('c0000000-0000-4000-8000-00000000000b', 'Tenant test B', 'DOCTOR',
     '22222222-2222-4222-8222-222222222222');

INSERT INTO public.clinic_membership (clinic_id, staff_id, role)
VALUES
    ('a0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-00000000000a', 'DOCTOR'),
    ('b0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-00000000000b', 'DOCTOR');

SET LOCAL ROLE authenticated;

SELECT set_config('request.jwt.claim.sub', '11111111-1111-4111-8111-111111111111', true);

DO $member_a$
BEGIN
    IF public.current_staff_id() <> 'c0000000-0000-4000-8000-00000000000a'::uuid THEN
        RAISE EXCEPTION 'current_staff_id did not resolve staff A from the JWT';
    END IF;

    IF (SELECT count(*) FROM public.clinic) <> 1
       OR (SELECT code FROM public.clinic) <> 'DR4WOMEN' THEN
        RAISE EXCEPTION 'staff A must see exactly their own clinic';
    END IF;

    -- Asserted as "nothing from clinic B", not "exactly one row": the count is
    -- whatever the database happens to hold, and tying the test to it made
    -- adding a staff fixture look like an RLS failure.
    IF EXISTS (
        SELECT 1 FROM public.clinic_membership
         WHERE clinic_id <> 'a0000000-0000-4000-8000-000000000001'::uuid
    ) THEN
        RAISE EXCEPTION 'staff A must not read another clinic''s membership';
    END IF;
END
$member_a$;

SELECT set_config('request.jwt.claim.sub', '22222222-2222-4222-8222-222222222222', true);

DO $member_b$
BEGIN
    IF (SELECT count(*) FROM public.clinic) <> 1
       OR (SELECT code FROM public.clinic) <> 'OTHER' THEN
        RAISE EXCEPTION 'staff B must see exactly their own clinic';
    END IF;
END
$member_b$;

SELECT set_config('request.jwt.claim.sub', '33333333-3333-4333-8333-333333333333', true);

DO $unlinked$
BEGIN
    IF (SELECT count(*) FROM public.clinic) <> 0 THEN
        RAISE EXCEPTION 'an authenticated user with no staff row must see no clinic';
    END IF;
END
$unlinked$;

RESET ROLE;
SET LOCAL ROLE service_role;

DO $service_role_sees_all$
BEGIN
    IF (SELECT count(*) FROM public.clinic) <> 2 THEN
        RAISE EXCEPTION 'service_role must retain full access for the backend';
    END IF;
END
$service_role_sees_all$;

RESET ROLE;

ROLLBACK;
