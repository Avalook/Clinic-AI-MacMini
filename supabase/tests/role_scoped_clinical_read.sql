-- ROLE-02 — being in the clinic is not enough to read the doctor's note.
--
-- W3 proved you cannot read another clinic's rows. This proves the other half:
-- inside one clinic, reception and the cashier read zero rows from
-- clinical_record, while the people doing clinical work still read everything
-- they need. Both directions matter — a policy that hides the note from the
-- doctor too would pass a "reception sees nothing" test and break the clinic.
--
-- Everything here rolls back.

BEGIN;

-- ---------------------------------------------------------------------------
-- Fixture: one clinic, four staff, one note
-- ---------------------------------------------------------------------------
INSERT INTO public.clinic (id, code, name)
VALUES ('c1000000-0000-4000-8000-000000000001', 'ROLE02', 'Phòng khám ROLE-02')
ON CONFLICT (id) DO NOTHING;

-- Only `id`: this test runs in CI against the minimal auth fixture in
-- bootstrap_plain_postgres.sql, where auth.users has that one column. The
-- password columns belong to a real GoTrue and are irrelevant here — nothing
-- logs in, the JWT subject is set directly with set_config below.
INSERT INTO auth.users (id)
VALUES
    ('a1000000-0000-4000-8000-000000000001'),
    ('a1000000-0000-4000-8000-000000000002'),
    ('a1000000-0000-4000-8000-000000000003'),
    ('a1000000-0000-4000-8000-000000000004')
ON CONFLICT (id) DO NOTHING;

-- Phòng khám trong bài kiểm này có nhiều hơn một cơ sở, nên hệ thống KHÔNG
-- đoán hộ (trigger 20260804000015). Fixture phải chỉ rõ.
INSERT INTO public.staff
    (id, full_name, primary_department, auth_user_id, is_active,
     primary_location_id)
SELECT v.id, v.nm, v.dept, v.au, TRUE,
       (SELECT id FROM public.clinic_location WHERE is_active
      ORDER BY created_at, id LIMIT 1)
  FROM (VALUES
    ('b1000000-0000-4000-8000-000000000001'::uuid, 'ROLE02 BS', 'DOCTOR',
     'a1000000-0000-4000-8000-000000000001'::uuid),
    ('b1000000-0000-4000-8000-000000000002', 'ROLE02 Le tan', 'RECEPTION',
     'a1000000-0000-4000-8000-000000000002'),
    ('b1000000-0000-4000-8000-000000000003', 'ROLE02 Thu ngan', 'CASHIER',
     'a1000000-0000-4000-8000-000000000003'),
    ('b1000000-0000-4000-8000-000000000004', 'ROLE02 Quan ly', 'MANAGEMENT',
     'a1000000-0000-4000-8000-000000000004')
  ) AS v(id, nm, dept, au)
ON CONFLICT (id) DO NOTHING;

-- staff_ensure_default_membership may already have added these; force the role.
DELETE FROM public.clinic_membership
 WHERE staff_id IN ('b1000000-0000-4000-8000-000000000001',
                    'b1000000-0000-4000-8000-000000000002',
                    'b1000000-0000-4000-8000-000000000003',
                    'b1000000-0000-4000-8000-000000000004');

INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
VALUES
    ('c1000000-0000-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000001', 'DOCTOR', TRUE),
    ('c1000000-0000-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002', 'RECEPTION', TRUE),
    ('c1000000-0000-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000003', 'CASHIER', TRUE),
    ('c1000000-0000-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000004', 'MANAGEMENT', TRUE);

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('cc000000-0000-4000-8000-000000000001',
        'c1000000-0000-4000-8000-000000000001', 'R02', 'Cơ sở ROLE-02')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.patient (
    clinic_id, clinic_patient_id, patient_code, full_name, location_id
)
VALUES ('c1000000-0000-4000-8000-000000000001',
        'd1000000-0000-4000-8000-000000000001', 'BN-ROLE02', 'BN ROLE-02',
        'cc000000-0000-4000-8000-000000000001')
ON CONFLICT (clinic_patient_id) DO NOTHING;

INSERT INTO public.visit (clinic_id, visit_id, clinic_patient_id, status)
VALUES ('c1000000-0000-4000-8000-000000000001',
        'e1000000-0000-4000-8000-000000000001',
        'd1000000-0000-4000-8000-000000000001', 'IN_PROGRESS')
ON CONFLICT (visit_id) DO NOTHING;

INSERT INTO public.clinical_record (clinic_id, visit_id, soap_subjective)
VALUES ('c1000000-0000-4000-8000-000000000001',
        'e1000000-0000-4000-8000-000000000001', '"đau bụng dưới"'::jsonb);

INSERT INTO public.clinical_form_response
    (clinic_id, visit_id, service_code, form_data)
VALUES ('c1000000-0000-4000-8000-000000000001',
        'e1000000-0000-4000-8000-000000000001', 'PK', '{"a":1}'::jsonb);

SET LOCAL ROLE authenticated;

-- ---------------------------------------------------------------------------
-- The doctor reads the note
-- ---------------------------------------------------------------------------
SELECT set_config('request.jwt.claim.sub',
                  'a1000000-0000-4000-8000-000000000001', true);

DO $doctor_reads$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.clinical_record
         WHERE visit_id = 'e1000000-0000-4000-8000-000000000001'
    ) THEN
        RAISE EXCEPTION 'the doctor must still read the note they wrote';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.clinical_form_response
         WHERE visit_id = 'e1000000-0000-4000-8000-000000000001'
    ) THEN
        RAISE EXCEPTION 'the doctor must still read the exam form';
    END IF;
END
$doctor_reads$;

-- ---------------------------------------------------------------------------
-- Reception and the cashier read nothing — the DOD
-- ---------------------------------------------------------------------------
SELECT set_config('request.jwt.claim.sub',
                  'a1000000-0000-4000-8000-000000000002', true);

DO $reception_blind$
BEGIN
    IF (SELECT count(*) FROM public.clinical_record) <> 0 THEN
        RAISE EXCEPTION 'RECEPTION must read 0 rows from clinical_record (ROLE-02)';
    END IF;
    IF (SELECT count(*) FROM public.clinical_form_response) <> 0 THEN
        RAISE EXCEPTION 'RECEPTION must read 0 rows from clinical_form_response';
    END IF;

    -- …but still does its job: the patient and the appointment are not clinical
    -- data, and hiding those would just break the front desk.
    IF NOT EXISTS (
        SELECT 1 FROM public.patient
         WHERE clinic_patient_id = 'd1000000-0000-4000-8000-000000000001'
    ) THEN
        RAISE EXCEPTION 'RECEPTION must still read the patient record';
    END IF;
END
$reception_blind$;

SELECT set_config('request.jwt.claim.sub',
                  'a1000000-0000-4000-8000-000000000003', true);

DO $cashier_blind$
BEGIN
    IF (SELECT count(*) FROM public.clinical_record) <> 0 THEN
        RAISE EXCEPTION 'CASHIER must read 0 rows from clinical_record (ROLE-02)';
    END IF;
END
$cashier_blind$;

-- ---------------------------------------------------------------------------
-- MANAGEMENT too: running the clinic is not a clinical role (§7.8)
-- ---------------------------------------------------------------------------
SELECT set_config('request.jwt.claim.sub',
                  'a1000000-0000-4000-8000-000000000004', true);

DO $management_blind$
BEGIN
    IF (SELECT count(*) FROM public.clinical_record) <> 0 THEN
        RAISE EXCEPTION
            'MANAGEMENT reads clinical_record — §7.8 says a manager is granted '
            'a clinical role explicitly, it does not come with the job';
    END IF;
END
$management_blind$;

-- ---------------------------------------------------------------------------
-- The operational tables stay open, deliberately
-- ---------------------------------------------------------------------------
-- The cashier charges for what is on the prescription and reception hands over
-- lab forms. If a later change narrows these too, it should be a decision with
-- a screen behind it, not a side effect — so state the expectation here.

SELECT set_config('request.jwt.claim.sub',
                  'a1000000-0000-4000-8000-000000000003', true);

DO $cashier_still_works$
DECLARE
    narrowed text;
BEGIN
    SELECT string_agg(p.tablename, ', ')
      INTO narrowed
      FROM pg_policies p
     WHERE p.schemaname = 'public'
       AND p.tablename IN ('prescription', 'lab_result', 'payment', 'service_log')
       AND p.cmd = 'SELECT'
       AND p.qual LIKE '%current_clinical_clinic_ids%';

    IF narrowed IS NOT NULL THEN
        RAISE EXCEPTION
            'these are operational, not the note — narrowing them breaks the '
            'front desk: %', narrowed;
    END IF;
END
$cashier_still_works$;

RESET ROLE;

ROLLBACK;
