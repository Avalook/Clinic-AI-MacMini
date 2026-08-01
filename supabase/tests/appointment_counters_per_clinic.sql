-- Every per-day counter on appointment is scoped to one clinic
-- (migrations 20260731000001 and 20260731000002).
--
-- Before the fix, check_in_appointment() took max(queue_number) across every
-- clinic for the day, so a second clinic's FIRST patient of the morning was
-- handed a number continuing the first clinic's sequence. This asserts the
-- number a receptionist actually calls out, not the shape of the SQL — a later
-- rewrite is free to change the query as long as clinic B still starts at 1.
--
-- Everything rolls back.

BEGIN;

-- Clinic A's fixtures are created here, not borrowed. CI applies migrations
-- ONLY — no seed.sql, no fixtures/local_data.sql — so the previous version of
-- this test, which subselected A's location and service type and used a patient
-- from the developer machine, passed locally and had never once run in CI.
-- Migrations create clinic A itself; everything under it is ours.
INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('a1100000-0000-4000-8000-000000000001',
        'a0000000-0000-4000-8000-000000000001', 'TEST-A', 'Cơ sở A (test)')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.service_type
    (id, clinic_id, code, name, default_duration_minutes)
VALUES ('a1200000-0000-4000-8000-000000000001',
        'a0000000-0000-4000-8000-000000000001', 'TEST-A1', 'Dịch vụ A (test)', 30)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.patient
    (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000f1', 'BN-TEST-A1', 'BN test A1',
        'a1100000-0000-4000-8000-000000000001')
ON CONFLICT (clinic_patient_id) DO NOTHING;

INSERT INTO public.clinic (id, code, name)
VALUES ('cb000000-0000-4000-8000-0000000000bb', 'QUEUEB', 'Phòng khám queue B')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('cb100000-0000-4000-8000-0000000000bb',
        'cb000000-0000-4000-8000-0000000000bb', 'QB', 'Cơ sở B')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.service_type
    (id, clinic_id, code, name, default_duration_minutes)
VALUES ('cb200000-0000-4000-8000-0000000000bb',
        'cb000000-0000-4000-8000-0000000000bb', 'QB1', 'Dịch vụ B', 30)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.patient
    (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('cb000000-0000-4000-8000-0000000000bb',
        'cb300000-0000-4000-8000-0000000000bb', 'BN-QUEUEB', 'BN cua B',
        'cb100000-0000-4000-8000-0000000000bb')
ON CONFLICT (clinic_patient_id) DO NOTHING;

-- Clinic A is already deep into its morning.
INSERT INTO public.appointment
    (id, clinic_id, clinic_patient_id, location_id, service_type_id,
     slot_start, slot_end, status, queue_number)
VALUES ('cb400000-0000-4000-8000-0000000000aa',
        'a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000f1',
        'a1100000-0000-4000-8000-000000000001',
        'a1200000-0000-4000-8000-000000000001',
        ((CURRENT_DATE + 30)::timestamp + time '08:00') AT TIME ZONE 'Asia/Ho_Chi_Minh',
        ((CURRENT_DATE + 30)::timestamp + time '08:30') AT TIME ZONE 'Asia/Ho_Chi_Minh',
        'CHECKED_IN', '46');

-- Clinic B's first patient of the same day.
INSERT INTO public.appointment
    (id, clinic_id, clinic_patient_id, location_id, service_type_id,
     slot_start, slot_end, status)
VALUES ('cb500000-0000-4000-8000-0000000000bb',
        'cb000000-0000-4000-8000-0000000000bb',
        'cb300000-0000-4000-8000-0000000000bb',
        'cb100000-0000-4000-8000-0000000000bb',
        'cb200000-0000-4000-8000-0000000000bb',
        ((CURRENT_DATE + 30)::timestamp + time '09:00') AT TIME ZONE 'Asia/Ho_Chi_Minh',
        ((CURRENT_DATE + 30)::timestamp + time '09:30') AT TIME ZONE 'Asia/Ho_Chi_Minh',
        'SCHEDULED');

DO $first_patient_starts_at_one$
DECLARE
    assigned text;
BEGIN
    SELECT queue_number INTO assigned
      FROM public.check_in_appointment(
          'cb500000-0000-4000-8000-0000000000bb', ARRAY['SCHEDULED']);

    IF assigned IS DISTINCT FROM '1' THEN
        RAISE EXCEPTION
            'clinic B''s first patient of the day got queue number % — the '
            'number must be per clinic, not shared across the database',
            coalesce(assigned, '<none>');
    END IF;
END
$first_patient_starts_at_one$;

-- …and clinic A keeps counting from where it was.
INSERT INTO public.appointment
    (id, clinic_id, clinic_patient_id, location_id, service_type_id,
     slot_start, slot_end, status)
VALUES ('cb600000-0000-4000-8000-0000000000aa',
        'a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000f1',
        'a1100000-0000-4000-8000-000000000001',
        'a1200000-0000-4000-8000-000000000001',
        ((CURRENT_DATE + 30)::timestamp + time '10:00') AT TIME ZONE 'Asia/Ho_Chi_Minh',
        ((CURRENT_DATE + 30)::timestamp + time '10:30') AT TIME ZONE 'Asia/Ho_Chi_Minh',
        'SCHEDULED');

DO $clinic_a_is_unaffected$
DECLARE
    assigned text;
BEGIN
    SELECT queue_number INTO assigned
      FROM public.check_in_appointment(
          'cb600000-0000-4000-8000-0000000000aa', ARRAY['SCHEDULED']);

    IF assigned IS DISTINCT FROM '47' THEN
        RAISE EXCEPTION
            'clinic A''s next patient got % instead of 47 — scoping the number '
            'per clinic must not restart the clinic that was already counting',
            coalesce(assigned, '<none>');
    END IF;
END
$clinic_a_is_unaffected$;

-- ---------------------------------------------------------------------------
-- CAP-01 capacity is per clinic too (20260731000002)
-- ---------------------------------------------------------------------------
-- enforce_slot_capacity() matched on doctor_id alone, and a NULL doctor
-- collapses to one sentinel — so every clinic's unassigned bookings shared a
-- single 15-minute bucket. Clinic A taking its two 09:00 slots told clinic B
-- "khung giờ đã đầy" for a doctor clinic B has never heard of.

DO $capacity_is_per_clinic$
DECLARE
    slot_a timestamptz := ((CURRENT_DATE + 40)::timestamp + time '09:00')
                          AT TIME ZONE 'Asia/Ho_Chi_Minh';
    slot_b timestamptz := ((CURRENT_DATE + 40)::timestamp + time '09:30')
                          AT TIME ZONE 'Asia/Ho_Chi_Minh';
    loc_a uuid := 'a1100000-0000-4000-8000-000000000001';
    svc_a uuid := 'a1200000-0000-4000-8000-000000000001';
BEGIN

    -- Clinic A fills the bucket (cap is 2 for booked appointments).
    INSERT INTO public.appointment
        (clinic_id, clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, status)
    SELECT 'a0000000-0000-4000-8000-000000000001',
           'e0000000-0000-4000-8000-0000000000f1', loc_a, svc_a,
           slot_a, slot_b, 'SCHEDULED'
      FROM generate_series(1, 2);

    -- Clinic B must still be able to book its own 09:00.
    INSERT INTO public.appointment
        (clinic_id, clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, status)
    VALUES ('cb000000-0000-4000-8000-0000000000bb',
            'cb300000-0000-4000-8000-0000000000bb',
            'cb100000-0000-4000-8000-0000000000bb',
            'cb200000-0000-4000-8000-0000000000bb',
            slot_a, slot_b, 'SCHEDULED');
EXCEPTION WHEN check_violation THEN
    RAISE EXCEPTION
        'clinic B was refused its own 09:00 because clinic A filled that '
        'bucket — CAP-01 must count per clinic';
END
$capacity_is_per_clinic$;

ROLLBACK;
