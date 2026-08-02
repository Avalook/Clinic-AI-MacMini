-- Regression assertions for 20260730000004_tenant_scoped_rls.sql (W3).
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/tenant_scoped_rls.sql
--
-- The property under test: reading a row requires active membership of the
-- clinic that owns it. Everything else — the shared clinic-gate account, a
-- stolen anon key, a JWT from another tenant — reads nothing.

BEGIN;

DO $patient_summary_is_private_and_invoker_scoped$
DECLARE
    options text[];
BEGIN
    SELECT c.reloptions
      INTO options
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relname = 'patient_summary'
       AND c.relkind = 'v';

    IF options IS NULL
       OR NOT ('security_invoker=true' = ANY (options)) THEN
        RAISE EXCEPTION
            'patient_summary must use security_invoker so its base-table RLS applies';
    END IF;

    IF has_table_privilege('authenticated', 'public.patient_summary', 'SELECT') THEN
        RAISE EXCEPTION
            'authenticated must not read patient_summary directly';
    END IF;

    IF has_table_privilege('anon', 'public.patient_summary', 'SELECT') THEN
        RAISE EXCEPTION
            'anon must not read patient_summary directly';
    END IF;

    IF NOT has_table_privilege('service_role', 'public.patient_summary', 'SELECT') THEN
        RAISE EXCEPTION
            'service_role must retain patient_summary access for the backend';
    END IF;
END
$patient_summary_is_private_and_invoker_scoped$;

DO $no_blanket_reads$
DECLARE
    offenders text;
BEGIN
    -- province and ward are the national administrative lists: no patient data,
    -- identical for every tenant. Everything else must be scoped.
    SELECT string_agg(tablename || '.' || policyname, ', ')
      INTO offenders
      FROM pg_policies
     WHERE schemaname = 'public'
       AND coalesce(qual, '') IN ('true', '(true)')
       AND tablename NOT IN ('province', 'ward');

    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'blanket USING(true) read policies still present: %', offenders;
    END IF;
END
$no_blanket_reads$;

DO $every_tenant_table_is_scoped$
DECLARE
    unscoped text;
    scoped_count integer;
BEGIN
    -- A tenant table with clinic_id but no policy mentioning current_clinic_ids
    -- is either unreachable or unguarded; both are bugs worth failing on.
    SELECT string_agg(c.table_name, ', ')
      INTO unscoped
      FROM information_schema.columns c
     WHERE c.table_schema = 'public'
       AND c.column_name = 'clinic_id'
       AND c.table_name NOT IN ('clinic_membership')
       AND EXISTS (
           SELECT 1 FROM pg_policies p
            WHERE p.schemaname = 'public' AND p.tablename = c.table_name
       )
       AND NOT EXISTS (
           SELECT 1 FROM pg_policies p
            WHERE p.schemaname = 'public'
              AND p.tablename = c.table_name
              -- current_clinical_clinic_ids() is current_clinic_ids() narrowed
              -- to the clinical roles (ROLE-02, 20260730000013): still scoped by
              -- tenant, and additionally by role. Matching on the name alone
              -- would have read that tightening as a tenant leak.
              AND (coalesce(p.qual, '') LIKE '%current_clinic_ids%'
                OR coalesce(p.qual, '') LIKE '%current_clinical_clinic_ids%')
       );

    IF unscoped IS NOT NULL THEN
        RAISE EXCEPTION 'tables with a policy that ignores the tenant: %', unscoped;
    END IF;

    SELECT count(*) INTO scoped_count
      FROM pg_policies
     WHERE schemaname = 'public'
       AND policyname LIKE '%_select_own_clinic';

    -- 23 tenant tables + staff + 7 workflow-kernel tables (W4)
    -- + block_budget, which became client-readable in W5. clinical_record and
    -- clinical_form_response keep this name but a narrower rule (ROLE-02).
    -- 32 → 34 on 02/08/2026: drug_batch + inventory_txn (migration
    -- 20260802000001, kho thuốc theo lô).
    IF scoped_count <> 34 THEN
        RAISE EXCEPTION 'expected 34 tenant-scoped read policies, found %', scoped_count;
    END IF;
END
$every_tenant_table_is_scoped$;

DO $reads_only$
DECLARE
    writable text;
BEGIN
    -- ADR-0012: the backend owns every write, so no client-facing write policy
    -- may exist. A single INSERT policy would undo that guarantee silently.
    SELECT string_agg(tablename || '.' || policyname || ' (' || cmd || ')', ', ')
      INTO writable
      FROM pg_policies
     WHERE schemaname = 'public'
       AND cmd <> 'SELECT';

    IF writable IS NOT NULL THEN
        RAISE EXCEPTION 'client-facing write policies must not exist: %', writable;
    END IF;
END
$reads_only$;

DO $backend_only_tables$
DECLARE
    exposed text;
    backend_only text[] := ARRAY[
        'idempotency_key',  -- stores replayed request/response bodies
        'mpi_merge_queue',  -- patient identifiers pending a merge decision
        'staff_capability', -- staffing config
        'pos_outbox'        -- pending pushes to an external till
        -- ultrasound_record was here while app/api/ultrasound read it with the
        -- service-role key. It now reads with the caller's own session, so the
        -- table has a tenant-scoped SELECT policy (20260730000012) and being
        -- policy-free would mean the page reads nothing.
    ];
BEGIN
    SELECT string_agg(c.relname, ', ')
      INTO exposed
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relname = ANY (backend_only)
       AND (
           NOT c.relrowsecurity
           OR EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid)
       );

    IF exposed IS NOT NULL THEN
        RAISE EXCEPTION 'these tables must stay service_role-only (RLS on, no policy): %', exposed;
    END IF;
END
$backend_only_tables$;

-- A new hire must not land in an app where every screen is silently empty, so
-- membership is created by the table itself rather than by whichever code path
-- happened to insert the staff row.
DO $membership_is_automatic$
DECLARE
    new_staff uuid;
BEGIN
    INSERT INTO public.staff (full_name, primary_department)
    VALUES ('Nhân viên mới', 'RECEPTION')
    RETURNING id INTO new_staff;

    IF NOT EXISTS (
        SELECT 1 FROM public.clinic_membership
         WHERE staff_id = new_staff
           AND clinic_id = 'a0000000-0000-4000-8000-000000000001'
           AND role = 'RECEPTION'
    ) THEN
        RAISE EXCEPTION 'inserting a staff row must create its clinic_membership';
    END IF;

    DELETE FROM public.clinic_membership WHERE staff_id = new_staff;
    DELETE FROM public.staff WHERE id = new_staff;
END
$membership_is_automatic$;

DO $policies_need_grants$
DECLARE
    ungranted text;
BEGIN
    -- A read policy only narrows a privilege the role already holds. The frozen
    -- baseline was dumped without ACLs, so on a fresh project every policy
    -- written in W1-W4 was unreachable and the app died on permission denied —
    -- invisible in production, fatal in a new environment. 20260730000008
    -- restores them; this makes sure they stay.
    --
    -- "Can read something", not "holds table-wide SELECT": since 20260802000004
    -- clinic is granted per column, so that settings — where the POS credentials
    -- used to live — is out of reach of a staff JWT while name and timezone stay
    -- readable. has_table_privilege() answers FALSE for a column-only grant, and
    -- reading that as "the policy is unreachable" would be the opposite of the
    -- truth.
    SELECT string_agg(DISTINCT c.relname, ', ')
      INTO ungranted
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_policy p ON p.polrelid = c.oid
     WHERE n.nspname = 'public'
       AND c.relkind = 'r'
       AND p.polcmd IN ('r', '*')
       AND NOT has_table_privilege('authenticated', c.oid, 'SELECT')
       AND NOT EXISTS (
           SELECT 1
             FROM pg_attribute a
            WHERE a.attrelid = c.oid
              AND a.attnum > 0
              AND NOT a.attisdropped
              AND has_column_privilege('authenticated', c.oid, a.attnum, 'SELECT'));

    IF ungranted IS NOT NULL THEN
        RAISE EXCEPTION
            'these tables have a read policy but authenticated cannot SELECT them: %',
            ungranted;
    END IF;
END
$policies_need_grants$;

-- --------------------------------------------------------------------------
-- Behaviour. Two clinics, one staff member each, one patient each.
-- --------------------------------------------------------------------------

INSERT INTO auth.users (id)
VALUES
    ('11111111-1111-4111-8111-111111111111'),  -- staff at Dr4Women
    ('22222222-2222-4222-8222-222222222222'),  -- staff at the other clinic
    ('99999999-9999-4999-8999-999999999999');  -- the shared clinic-gate account

INSERT INTO public.clinic (id, code, name)
VALUES ('b0000000-0000-4000-8000-000000000002', 'OTHER', 'Phòng khám khác');

INSERT INTO public.staff (id, full_name, primary_department, auth_user_id)
VALUES
    ('c0000000-0000-4000-8000-00000000000a', 'RLS test A', 'DOCTOR',
     '11111111-1111-4111-8111-111111111111'),
    ('c0000000-0000-4000-8000-00000000000b', 'RLS test B', 'DOCTOR',
     '22222222-2222-4222-8222-222222222222');

INSERT INTO public.clinic_membership (clinic_id, staff_id, role)
VALUES
    ('a0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-00000000000a', 'DOCTOR'),
    ('b0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-00000000000b', 'DOCTOR');

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES
    ('d0000000-0000-4000-8000-00000000000a', 'a0000000-0000-4000-8000-000000000001', 'CS1', 'Cơ sở A'),
    ('d0000000-0000-4000-8000-00000000000b', 'b0000000-0000-4000-8000-000000000002', 'CS1', 'Cơ sở B');

INSERT INTO public.patient (clinic_patient_id, clinic_id, patient_code, full_name, location_id)
VALUES
    ('e0000000-0000-4000-8000-00000000000a', 'a0000000-0000-4000-8000-000000000001',
     'BN001', 'Bệnh nhân của A', 'd0000000-0000-4000-8000-00000000000a'),
    ('e0000000-0000-4000-8000-00000000000b', 'b0000000-0000-4000-8000-000000000002',
     'BN001', 'Bệnh nhân của B', 'd0000000-0000-4000-8000-00000000000b');

-- The product no longer grants this view to frontend callers.  Grant it only
-- inside the rolled-back test transaction to prove the second line of defence:
-- if somebody accidentally restores the grant later, SECURITY INVOKER still
-- makes the patient table's tenant RLS apply through the view.
GRANT SELECT ON public.patient_summary TO authenticated;

SET LOCAL ROLE authenticated;

SELECT set_config('request.jwt.claim.sub', '11111111-1111-4111-8111-111111111111', true);

DO $staff_a$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000a'
    ) OR EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000b'
    ) THEN
        RAISE EXCEPTION 'staff A must see their own patient and not clinic B''s';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.patient_summary
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000a'
    ) OR EXISTS (
        SELECT 1 FROM public.patient_summary
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000b'
    ) THEN
        RAISE EXCEPTION
            'patient_summary must inherit patient RLS and never cross tenants';
    END IF;

    -- Count only what this test inserted: seed.sql loads real clinic_location
    -- rows, so asserting on the whole table passes on an empty database and
    -- fails on a seeded one.
    IF EXISTS (
        SELECT 1 FROM public.clinic_location
         WHERE id = 'd0000000-0000-4000-8000-00000000000b'
    ) THEN
        RAISE EXCEPTION 'staff A must not see another clinic''s locations';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.clinic_location
         WHERE id = 'd0000000-0000-4000-8000-00000000000a'
    ) THEN
        RAISE EXCEPTION 'staff A must see their own clinic''s location';
    END IF;

    -- Self-read must work even before any colleague lookup.
    IF NOT EXISTS (
        SELECT 1 FROM public.staff WHERE id = 'c0000000-0000-4000-8000-00000000000a'
    ) THEN
        RAISE EXCEPTION 'staff must always be able to read their own row';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.staff WHERE id = 'c0000000-0000-4000-8000-00000000000b'
    ) THEN
        RAISE EXCEPTION 'staff A must not read staff of another clinic';
    END IF;
END
$staff_a$;

SELECT set_config('request.jwt.claim.sub', '22222222-2222-4222-8222-222222222222', true);

DO $staff_b$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000b'
    ) OR EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'e0000000-0000-4000-8000-00000000000a'
    ) THEN
        RAISE EXCEPTION 'staff B must see their own patient and not clinic A''s';
    END IF;
END
$staff_b$;

SELECT set_config('request.jwt.claim.sub', '99999999-9999-4999-8999-999999999999', true);

DO $shared_gate_account$
BEGIN
    -- app/(auth)/enter signs in as one shared account with no staff row. Under
    -- the old USING(true) policies that account could read every patient in the
    -- database; now it must read none.
    IF EXISTS (SELECT 1 FROM public.patient) THEN
        RAISE EXCEPTION 'an authenticated account with no staff row must read no patients';
    END IF;

    IF EXISTS (SELECT 1 FROM public.patient_summary) THEN
        RAISE EXCEPTION
            'an authenticated account with no staff row must read no patient summaries';
    END IF;

    IF (SELECT count(*) FROM public.staff) <> 0 THEN
        RAISE EXCEPTION 'an authenticated account with no staff row must read no staff';
    END IF;
END
$shared_gate_account$;

RESET ROLE;
SET LOCAL ROLE service_role;

DO $backend_unaffected$
BEGIN
    IF (SELECT count(*) FROM public.patient
         WHERE clinic_patient_id IN (
             'e0000000-0000-4000-8000-00000000000a',
             'e0000000-0000-4000-8000-00000000000b')) <> 2 THEN
        RAISE EXCEPTION 'service_role must still read across tenants for the backend';
    END IF;

    IF (SELECT count(*) FROM public.patient_summary
         WHERE clinic_patient_id IN (
             'e0000000-0000-4000-8000-00000000000a',
             'e0000000-0000-4000-8000-00000000000b')) <> 2 THEN
        RAISE EXCEPTION
            'service_role must retain patient_summary access for the backend';
    END IF;
END
$backend_unaffected$;

RESET ROLE;

ROLLBACK;
