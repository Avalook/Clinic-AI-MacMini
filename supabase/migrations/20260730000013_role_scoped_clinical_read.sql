-- ROLE-02 — reception and cashiers read zero rows from the doctor's note.
--
-- W3 (20260730000004) narrowed every read to the caller's clinic and said
-- plainly what it was not doing: narrowing by ROLE inside a clinic. It could
-- not, because /home read `clinical_record` through the caller's own session to
-- decide whether vitals had been taken, and reception opens /home. Tightening
-- the policy then would have blanked the screen rather than protected anything.
--
-- That read now goes through FastAPI (`GET /api/v1/visits/progress`), which
-- returns booleans — "vitals recorded", "which fees are paid" — and never the
-- note itself. So the policy can finally say what ADR-0004 wanted: being in the
-- clinic is not enough to read someone's medical record; you have to be doing
-- clinical work.
--
-- SCOPE, and why it stops here. This covers the two tables that ARE the note:
-- clinical_record (SOAP) and clinical_form_response (specialty exam forms).
-- Both are read by exactly one screen, the doctor's exam form.
--
-- lab_result, prescription, payment and service_log stay clinic-scoped on
-- purpose. Reception hands over lab request forms, the cashier charges for the
-- medicine on the prescription, the shift lead reconciles the day. Those roles
-- have an operational reason to see that a test or a drug exists, and cutting
-- it would break the front desk to no benefit. pregnancy and
-- patient_medical_profile are also left alone: /patients/[id] shows them to
-- CSKH and reception today, and whether that should continue is a clinic
-- decision, not a security bug to fix quietly in a migration.

-- ---------------------------------------------------------------------------
-- 1. Which clinics does the caller work in AS one of these roles?
-- ---------------------------------------------------------------------------
-- Same shape as current_clinic_ids(), one argument narrower. Kept as a function
-- rather than inlined into each policy so the role list has a single home.

CREATE OR REPLACE FUNCTION public.current_clinic_ids_for_roles(roles text[])
RETURNS SETOF uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $$
    SELECT m.clinic_id
    FROM public.clinic_membership m
    WHERE m.staff_id = public.current_staff_id()
      AND m.is_active
      AND m.role = ANY (roles)
$$;

COMMENT ON FUNCTION public.current_clinic_ids_for_roles(text[]) IS
  'Clinics where the caller holds an active membership in one of the given '
  'roles. The role-aware counterpart of current_clinic_ids().';

REVOKE ALL ON FUNCTION public.current_clinic_ids_for_roles(text[]) FROM public;
GRANT EXECUTE ON FUNCTION public.current_clinic_ids_for_roles(text[])
    TO authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 2. Who may read the note
-- ---------------------------------------------------------------------------
-- The same four roles the backend already calls CLINICAL_WRITE_ROLES
-- (clinicai.api.identity): whoever may write the note may read it. Keeping the
-- two lists identical means there is one answer to "who does clinical work",
-- not a database answer and an application answer that drift apart.
--
-- MANAGEMENT is deliberately NOT here. Per the role map (§7.8), running the
-- clinic does not come with reading medical records; if a manager needs a
-- record they are granted the clinical role explicitly. Reports read aggregates
-- through the backend, not rows through PostgREST.

CREATE OR REPLACE FUNCTION public.current_clinical_clinic_ids()
RETURNS SETOF uuid
LANGUAGE sql
STABLE
SET search_path TO 'public', 'pg_temp'
AS $$
    SELECT public.current_clinic_ids_for_roles(
        ARRAY['DOCTOR', 'ULTRASOUND_DOCTOR', 'TKYK', 'NURSE_ULTRASOUND']
    )
$$;

COMMENT ON FUNCTION public.current_clinical_clinic_ids() IS
  'Clinics where the caller does clinical work. Mirrors CLINICAL_WRITE_ROLES '
  'in clinicai.api.identity — change both together.';

GRANT EXECUTE ON FUNCTION public.current_clinical_clinic_ids()
    TO authenticated, service_role;

DROP POLICY IF EXISTS clinical_record_select_own_clinic ON public.clinical_record;
CREATE POLICY clinical_record_select_own_clinic ON public.clinical_record
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinical_clinic_ids()));

DROP POLICY IF EXISTS clinical_form_response_select_own_clinic
    ON public.clinical_form_response;
CREATE POLICY clinical_form_response_select_own_clinic
    ON public.clinical_form_response
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinical_clinic_ids()));

-- ultrasound_record got its SELECT policy one migration ago (20260730000012) so
-- the ultrasound page could stop using the service-role key. It is clinical
-- too, and the page behind it is already ULTRASOUND_DOCTOR-only, so it belongs
-- on the same footing rather than being readable by the whole clinic.
DROP POLICY IF EXISTS ultrasound_record_select ON public.ultrasound_record;
CREATE POLICY ultrasound_record_select ON public.ultrasound_record
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinical_clinic_ids()));

-- ---------------------------------------------------------------------------
-- 3. Refuse to lock the clinic out of its own records
-- ---------------------------------------------------------------------------
-- A clinic with no clinical role at all would have written notes nobody can
-- read. That is a misconfiguration, not a tightening, so say so now rather than
-- at the first exam of the day.

DO $must_have_a_clinician$
DECLARE
    orphaned text;
BEGIN
    SELECT string_agg(c.code, ', ')
      INTO orphaned
      FROM public.clinic c
     WHERE EXISTS (
             SELECT 1 FROM public.clinical_record r WHERE r.clinic_id = c.id
           )
       AND NOT EXISTS (
             SELECT 1 FROM public.clinic_membership m
              WHERE m.clinic_id = c.id
                AND m.is_active
                AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR', 'TKYK',
                               'NURSE_ULTRASOUND')
           );

    IF orphaned IS NOT NULL THEN
        RAISE EXCEPTION
            'these clinics have records but no active clinical staff to read '
            'them: % — give someone a clinical role first', orphaned;
    END IF;
END
$must_have_a_clinician$;
