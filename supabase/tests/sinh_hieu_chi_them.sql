-- Sinh hiệu đã đo chỉ thêm (20260915000012).
--
-- Đo lại là một dòng mới; dòng cũ không sửa, không xoá.
--
-- Tự dựng dữ liệu, cuối file ROLLBACK.

BEGIN;

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('a1100000-0000-4000-8000-0000000005a1',
        'a0000000-0000-4000-8000-000000000001', 'TEST-SH1', 'Cơ sở SH (test)')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.staff (id, full_name, primary_department, primary_location_id)
VALUES ('a1300000-0000-4000-8000-0000000005a1', 'ĐD test SH', 'DOCTOR',
        'a1100000-0000-4000-8000-0000000005a1')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.patient (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000005a1', 'BN-TEST-SH1', 'BN test SH1',
        'a1100000-0000-4000-8000-0000000005a1')
ON CONFLICT (clinic_patient_id) DO NOTHING;

INSERT INTO public.visit (visit_id, clinic_id, clinic_patient_id, status)
VALUES ('aa000000-0000-4000-8000-0000000005a1',
        'a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000005a1', 'OPEN');

DO $sh$
DECLARE
    v_clinic constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_visit  constant uuid := 'aa000000-0000-4000-8000-0000000005a1';
    v_staff  constant uuid := 'a1300000-0000-4000-8000-0000000005a1';
    v_count  integer;
BEGIN
    INSERT INTO public.vital_measurement (clinic_id, visit_id, systolic, diastolic, recorded_by)
    VALUES (v_clinic, v_visit, 120, 80, v_staff);
    -- Đo lại: dòng thứ hai, dòng đầu còn nguyên.
    INSERT INTO public.vital_measurement (clinic_id, visit_id, systolic, diastolic, recorded_by)
    VALUES (v_clinic, v_visit, 135, 85, v_staff);

    BEGIN
        UPDATE public.vital_measurement SET systolic = 110 WHERE visit_id = v_visit;
        RAISE EXCEPTION 'vital_measurement: sửa số đã đo lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        DELETE FROM public.vital_measurement WHERE visit_id = v_visit;
        RAISE EXCEPTION 'vital_measurement: xoá số đã đo lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    SELECT count(*) INTO v_count FROM public.vital_measurement WHERE visit_id = v_visit;
    IF v_count <> 2 THEN
        RAISE EXCEPTION 'vital_measurement: mong 2 dòng lịch sử, có %', v_count;
    END IF;

END
$sh$;

ROLLBACK;
