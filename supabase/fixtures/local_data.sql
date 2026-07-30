-- Clinic-side fixtures the local end-to-end scripts need.
--
-- The companion to staff_logins.sql: that one creates the people, this
-- one creates the things they work on. Both exist for the same reason — the
-- scripts used to depend on rows somebody typed into this Mac once, so nobody
-- else could run them and `supabase db reset` silently removed the
-- prerequisites. seed.sql provides the catalogues (service_type, wards,
-- channels); what was missing is a patient to book, a session to book into and
-- an episode to close.
--
-- Idempotent: fixed uuids, ON CONFLICT DO NOTHING. Note that `patient` is
-- append-only (prevent_hard_delete), so re-running must not try to delete.
--
-- LOCAL/STAGING ONLY — invented people. Never run against real patient data.

\set ON_ERROR_STOP on

DO $$
DECLARE
    v_clinic   uuid := 'a0000000-0000-4000-8000-000000000001';
    v_patient  uuid := 'e0000000-0000-4000-8000-0000000000f1';
    v_location uuid;
    v_service  uuid;
    v_doctor   uuid;
BEGIN
    SELECT id INTO v_location
      FROM public.clinic_location
     WHERE clinic_id = v_clinic AND is_active ORDER BY code LIMIT 1;
    SELECT id INTO v_service
      FROM public.service_type WHERE clinic_id = v_clinic ORDER BY code LIMIT 1;
    SELECT id INTO v_doctor
      FROM public.staff WHERE full_name = 'BS A local';

    IF v_location IS NULL OR v_service IS NULL THEN
        RAISE EXCEPTION 'clinic_location/service_type missing — apply seed.sql first';
    END IF;
    IF v_doctor IS NULL THEN
        RAISE EXCEPTION 'staff missing — run supabase/fixtures/staff_logins.sql first';
    END IF;

    INSERT INTO public.patient (
        clinic_id, clinic_patient_id, patient_code, full_name, phone_primary,
        location_id
    )
    VALUES (
        v_clinic, v_patient, 'BN-LOCAL-1', 'BN của Dr4Women', '0900000001',
        v_location
    )
    ON CONFLICT (clinic_patient_id) DO NOTHING;

    -- find_work_sessions only knows EVENING / WEEKEND_* sessions, and wants one
    -- for *today* — the scheduling graph asks for today's date.
    INSERT INTO public.work_session (
        clinic_id, location_id, session_date, session_type, start_time, end_time
    )
    VALUES (
        v_clinic, v_location, CURRENT_DATE, 'EVENING', '17:00', '20:00'
    )
    ON CONFLICT DO NOTHING;

    -- One OPEN episode, so a script that needs "an episode to act on" finds one.
    -- The dashboard check closes a PENDING_CLOSE episode and expects a 409 for
    -- an OPEN one, which is exactly what this row is for.
    INSERT INTO public.care_episode (clinic_id, clinic_patient_id, service_type_id)
    SELECT v_clinic, v_patient, v_service
     WHERE NOT EXISTS (
        SELECT 1 FROM public.care_episode WHERE clinic_patient_id = v_patient
     );
END $$;

SELECT (SELECT count(*) FROM public.patient)      AS patients,
       (SELECT count(*) FROM public.work_session) AS work_sessions,
       (SELECT count(*) FROM public.care_episode) AS episodes;
