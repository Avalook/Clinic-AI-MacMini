-- Nháp chỉ định không mang trạng thái Selection (20260922000002).
--
-- Tự dựng dữ liệu, cuối file ROLLBACK.

BEGIN;

-- Dữ liệu dựng riêng cho file này (id 1d000000-…), không phải dữ liệu thật.
DO $fixture$
BEGIN
    INSERT INTO public.clinic_location (id, clinic_id, code, name)
    VALUES ('1d000000-0000-4000-8000-0000000001a1',
            'a0000000-0000-4000-8000-000000000001', 'TEST-DS1', 'Cơ sở DS (test)');

    INSERT INTO public.staff (id, primary_location_id, full_name, primary_department)
    VALUES ('1d000000-0000-4000-8000-0000000005f1',
            '1d000000-0000-4000-8000-0000000001a1', 'NV test DS', 'DOCTOR');

    INSERT INTO public.patient (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
    VALUES ('a0000000-0000-4000-8000-000000000001',
            '1d000000-0000-4000-8000-0000000000b1', 'BN-TEST-DS1', 'BN test DS1',
            '1d000000-0000-4000-8000-0000000001a1');

    INSERT INTO public.visit (visit_id, clinic_id, clinic_patient_id, status)
    VALUES ('1d000000-0000-4000-8000-0000000000a1',
            'a0000000-0000-4000-8000-000000000001',
            '1d000000-0000-4000-8000-0000000000b1', 'IN_PROGRESS');

    INSERT INTO public.consultation (id, clinic_id, visit_id, round_no, kind)
    VALUES ('1d000000-0000-4000-8000-0000000000c1',
            'a0000000-0000-4000-8000-000000000001',
            '1d000000-0000-4000-8000-0000000000a1', 1, 'PRIMARY');
END
$fixture$;

DO $ds$
DECLARE
    v_clinic  constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_visit   constant uuid := '1d000000-0000-4000-8000-0000000000a1';
    v_consult constant uuid := '1d000000-0000-4000-8000-0000000000c1';
    v_staff   constant uuid := '1d000000-0000-4000-8000-0000000005f1';
    v_draft   uuid;
    s         text;
BEGIN
    -- Nháp + NULL: được.
    INSERT INTO public.service_order (clinic_id, visit_id, consultation_id,
        service_code, service_name, node_code, exec_status, recorded_by)
    VALUES (v_clinic, v_visit, v_consult, 'SA', 'Siêu âm', 'DICHVU-SIEUAM',
        'draft', v_staff)
    RETURNING id INTO v_draft;

    -- Nháp + bất kỳ trạng thái Selection nào: bị chặn, cả INSERT lẫn UPDATE.
    FOREACH s IN ARRAY ARRAY['PENDING', 'SELECTED', 'NOT_SELECTED'] LOOP
        BEGIN
            UPDATE public.service_order SET selection_status = s WHERE id = v_draft;
            RAISE EXCEPTION 'draft: UPDATE selection_status=% lẽ ra bị chặn', s;
        EXCEPTION WHEN check_violation THEN NULL;
        END;
        BEGIN
            INSERT INTO public.service_order (clinic_id, visit_id, consultation_id,
                service_code, service_name, node_code, exec_status, recorded_by,
                selection_status)
            VALUES (v_clinic, v_visit, v_consult, 'SA', 'Siêu âm', 'DICHVU-SIEUAM',
                'draft', v_staff, s);
            RAISE EXCEPTION 'draft: INSERT selection_status=% lẽ ra bị chặn', s;
        EXCEPTION WHEN check_violation THEN NULL;
        END;
    END LOOP;

    -- Chỉ định chính thức kiểu cũ + NULL: vẫn được.
    INSERT INTO public.service_order (clinic_id, visit_id, consultation_id,
        service_code, service_name, node_code, exec_status, recorded_by,
        authorized_by, authorized_at)
    VALUES (v_clinic, v_visit, v_consult, 'SA', 'Siêu âm', 'DICHVU-SIEUAM',
        'authorized', v_staff, v_staff, now());

    -- Chỉ định chính thức lifecycle-v1 + PENDING: được.
    INSERT INTO public.service_order (clinic_id, visit_id, consultation_id,
        service_code, service_name, node_code, exec_status, recorded_by,
        authorized_by, authorized_at, selection_status)
    VALUES (v_clinic, v_visit, v_consult, 'SA', 'Siêu âm', 'DICHVU-SIEUAM',
        'authorized', v_staff, v_staff, now(), 'PENDING');

    -- Duyệt nháp đúng như authorize_orders: đổi exec_status và đặt PENDING
    -- trong CÙNG một câu lệnh — CHECK xét dòng sau khi đổi, nên được.
    UPDATE public.service_order
       SET exec_status = 'authorized', authorized_by = v_staff,
           authorized_at = now(), selection_status = 'PENDING'
     WHERE id = v_draft;
END
$ds$;

ROLLBACK;
