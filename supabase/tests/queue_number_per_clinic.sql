-- The daily queue number is per clinic (20260731000001).
--
-- Before the fix, check_in_appointment() took max(queue_number) across every
-- clinic for the day, so a second clinic's FIRST patient of the morning was
-- handed a number continuing the first clinic's sequence. This asserts the
-- number a receptionist actually calls out, not the shape of the SQL — a later
-- rewrite is free to change the query as long as clinic B still starts at 1.
--
-- Everything rolls back.

BEGIN;

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
SELECT 'cb400000-0000-4000-8000-0000000000aa',
       'a0000000-0000-4000-8000-000000000001',
       'e0000000-0000-4000-8000-0000000000f1',
       (SELECT id FROM public.clinic_location
         WHERE clinic_id = 'a0000000-0000-4000-8000-000000000001'
           AND is_active ORDER BY code LIMIT 1),
       (SELECT id FROM public.service_type
         WHERE clinic_id = 'a0000000-0000-4000-8000-000000000001'
           AND is_active ORDER BY code LIMIT 1),
       ((CURRENT_DATE + 30)::timestamp + time '08:00') AT TIME ZONE 'Asia/Ho_Chi_Minh',
       ((CURRENT_DATE + 30)::timestamp + time '08:30') AT TIME ZONE 'Asia/Ho_Chi_Minh',
       'CHECKED_IN', '46';

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
SELECT 'cb600000-0000-4000-8000-0000000000aa',
       'a0000000-0000-4000-8000-000000000001',
       'e0000000-0000-4000-8000-0000000000f1',
       (SELECT id FROM public.clinic_location
         WHERE clinic_id = 'a0000000-0000-4000-8000-000000000001'
           AND is_active ORDER BY code LIMIT 1),
       (SELECT id FROM public.service_type
         WHERE clinic_id = 'a0000000-0000-4000-8000-000000000001'
           AND is_active ORDER BY code LIMIT 1),
       ((CURRENT_DATE + 30)::timestamp + time '10:00') AT TIME ZONE 'Asia/Ho_Chi_Minh',
       ((CURRENT_DATE + 30)::timestamp + time '10:30') AT TIME ZONE 'Asia/Ho_Chi_Minh',
       'SCHEDULED';

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

ROLLBACK;
