-- W3 — Replace every `USING (true)` read policy with a tenant-scoped one
-- (ADR-0004 accepted 2026-07-30, ADR-0009).
--
-- Until now any holder of the anon key plus any valid Supabase JWT could read
-- every clinical row in the database: 26 tables carried
-- `<table>_select_authenticated ... USING (true)`. With W2's `clinic_id` in
-- place we can finally say what the policy always should have said: you read a
-- row when you are an active member of the clinic that owns it.
--
-- Concretely this also closes the shared clinic-gate account
-- (app/(auth)/enter, CLINIC_SHARED_EMAIL): that account has no `staff` row, so
-- it now reads zero rows everywhere instead of everything.
--
-- WHAT THIS DOES NOT DO: restrict reads *by role* within a clinic. Today the
-- dashboard reads clinical tables through the caller's own session from screens
-- that reception and cashiers legitimately open — /tasks reads lab_result and
-- prescription, /home reads clinical_record and payment. Narrowing by role
-- before those reads move behind FastAPI (W5, ADR-0012) would simply blank the
-- screens. Role-level restriction belongs in W5, with `event_log` (MANAGEMENT
-- only) staying as the one already-narrow case.

-- ---------------------------------------------------------------------------
-- 0. Preconditions — fail before changing anything, not halfway through
-- ---------------------------------------------------------------------------
-- Every one of these policies resolves the caller through
-- auth.uid() -> staff.auth_user_id -> clinic_membership. An active staff member
-- who is not linked to an auth user would be locked out of the whole app the
-- moment this migration lands, so refuse to apply instead.

DO $precondition$
DECLARE
    unlinked integer;
    active_staff integer;
    sample text;
BEGIN
    SELECT count(*) FILTER (WHERE auth_user_id IS NULL), count(*)
      INTO unlinked, active_staff
      FROM public.staff
     WHERE COALESCE(is_active, true);

    IF unlinked > 0 THEN
        SELECT string_agg(full_name || ' (' || primary_department || ')', ', ')
          INTO sample
          FROM (
              SELECT full_name, primary_department
                FROM public.staff
               WHERE COALESCE(is_active, true) AND auth_user_id IS NULL
               ORDER BY full_name
               LIMIT 5
          ) s;

        RAISE EXCEPTION
            'W3 aborted: % of % active staff have no auth_user_id (%). Link every '
            'active staff member to a Supabase Auth user first — otherwise this '
            'migration locks them out of every screen.',
            unlinked, active_staff, sample
            USING HINT = 'SELECT id, full_name, primary_department FROM public.staff '
                         'WHERE COALESCE(is_active, true) AND auth_user_id IS NULL;';
    END IF;
END
$precondition$;

-- Staff created between W2 and W3 would have no membership and would therefore
-- read nothing. Top the backfill up; it is the same statement W2 ran.
INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
SELECT 'a0000000-0000-4000-8000-000000000001', s.id, s.primary_department,
       COALESCE(s.is_active, true)
FROM public.staff s
ON CONFLICT ON CONSTRAINT uq_clinic_membership DO NOTHING;

DO $membership_precondition$
DECLARE
    orphans integer;
BEGIN
    SELECT count(*) INTO orphans
      FROM public.staff s
     WHERE COALESCE(s.is_active, true)
       AND NOT EXISTS (
           SELECT 1 FROM public.clinic_membership m
            WHERE m.staff_id = s.id AND m.is_active
       );

    IF orphans > 0 THEN
        RAISE EXCEPTION
            'W3 aborted: % active staff have no active clinic_membership.', orphans;
    END IF;
END
$membership_precondition$;

-- ---------------------------------------------------------------------------
-- 1. The 23 tenant-owned tables
-- ---------------------------------------------------------------------------
-- Reads only, and only inside your own clinic. Writes stay service_role-only:
-- there is deliberately no INSERT/UPDATE/DELETE policy anywhere (ADR-0012 — the
-- backend owns every write, so the frontend does not have to be trusted).

DO $tenant_read$
DECLARE
    t text;
    tables text[] := ARRAY[
        'appointment', 'booking_channel', 'care_episode', 'clinic_location',
        'clinical_form_response', 'clinical_record', 'cskh_action', 'cskh_log',
        'drug_catalog', 'lab_result', 'patient', 'patient_medical_profile',
        'payment', 'pregnancy', 'prescription', 'service_log', 'service_price',
        'service_type', 'staff_task', 'visit', 'work_roster', 'work_session',
        'work_session_staff'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_select_authenticated', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_select_own_clinic', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated '
            'USING (clinic_id IN (SELECT public.current_clinic_ids()))',
            t || '_select_own_clinic', t
        );
    END LOOP;
END
$tenant_read$;

-- ---------------------------------------------------------------------------
-- 2. Tables that need something other than the plain tenant rule
-- ---------------------------------------------------------------------------

-- staff has no clinic_id on purpose (a doctor may work at several clinics), so
-- membership is the scope. The self-read arm guarantees a user can always
-- resolve their own row — without it a membership glitch would log everyone out.
DROP POLICY IF EXISTS staff_select_authenticated ON public.staff;
DROP POLICY IF EXISTS staff_select_own_clinic ON public.staff;
CREATE POLICY staff_select_own_clinic
    ON public.staff
    FOR SELECT
    TO authenticated
    USING (
        id = public.current_staff_id()
        OR EXISTS (
            SELECT 1
              FROM public.clinic_membership m
             WHERE m.staff_id = public.staff.id
               AND m.is_active
               AND m.clinic_id IN (SELECT public.current_clinic_ids())
        )
    );

-- event_log was already MANAGEMENT-only (20260717000001); keep that and add the
-- tenant bound, so a manager of clinic A cannot read clinic B's audit trail.
DROP POLICY IF EXISTS event_log_select_management ON public.event_log;
CREATE POLICY event_log_select_management
    ON public.event_log
    FOR SELECT
    TO authenticated
    USING (
        public.current_staff_department() = 'MANAGEMENT'
        AND clinic_id IN (SELECT public.current_clinic_ids())
    );

-- province and ward are the national administrative lists. They carry no
-- patient data and every clinic uses the same rows, so they stay readable by
-- any authenticated user — see 20260730000002.

-- ---------------------------------------------------------------------------
-- 3. idempotency_key had RLS switched off entirely
-- ---------------------------------------------------------------------------
-- It is the only table in public with `relrowsecurity = false`. It stores
-- request and response bodies for replayed calls — patient payloads included —
-- and Supabase grants `authenticated` SELECT on public tables by default, so it
-- was readable by any logged-in user. It is written and read exclusively by the
-- backend, so enable RLS and give it no policy at all.

ALTER TABLE public.idempotency_key ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.idempotency_key FROM anon, authenticated;

-- ---------------------------------------------------------------------------
-- 4. A staff row without membership can no longer read anything
-- ---------------------------------------------------------------------------
-- Staff rows are created from several places — StaffService.create_staff, the
-- admin UI's link flow, and plain SQL by hand — and none of them knows about
-- clinic_membership. Forgetting it now means a new hire logs in to empty
-- screens with no error anywhere. Enforce the invariant where every path meets:
-- the table itself.

CREATE OR REPLACE FUNCTION public.staff_ensure_default_membership()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    target_clinic uuid := public.default_clinic_id();
BEGIN
    -- While the deployment is single-tenant the clinic is not in doubt. Once a
    -- second one exists the answer genuinely depends on the caller, so do
    -- nothing and let them insert membership explicitly (W5 makes the backend
    -- do that, at which point this trigger is a permanent no-op).
    IF target_clinic IS NULL THEN
        RETURN NEW;
    END IF;

    INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
    VALUES (target_clinic, NEW.id, NEW.primary_department, COALESCE(NEW.is_active, true))
    ON CONFLICT ON CONSTRAINT uq_clinic_membership DO NOTHING;

    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS staff_ensure_default_membership ON public.staff;
CREATE TRIGGER staff_ensure_default_membership
    AFTER INSERT ON public.staff
    FOR EACH ROW
    EXECUTE FUNCTION public.staff_ensure_default_membership();
