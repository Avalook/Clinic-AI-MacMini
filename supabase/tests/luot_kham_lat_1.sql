-- Ràng buộc dữ liệu của luồng khám lát 1 (20260911000001).
--
-- Service là lớp chặn thứ nhất; các ràng buộc dưới đây là lớp chặn cho MỌI
-- đường ghi khác (một script, một migration sau, một người sửa tay). Mỗi khối
-- thử đúng một điều phải bị từ chối, và thử cả điều phải được cho qua.
--
-- Tự dựng dữ liệu, cuối file ROLLBACK — CI chỉ nạp migration, không seed.

BEGIN;

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('a1100000-0000-4000-8000-0000000000a1',
        'a0000000-0000-4000-8000-000000000001', 'TEST-LK1', 'Cơ sở LK (test)')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.staff (id, full_name, primary_department, primary_location_id)
VALUES ('a1300000-0000-4000-8000-0000000000a1', 'BS test LK', 'DOCTOR',
        'a1100000-0000-4000-8000-0000000000a1')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.patient (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000a1', 'BN-TEST-LK1', 'BN test LK1',
        'a1100000-0000-4000-8000-0000000000a1')
ON CONFLICT (clinic_patient_id) DO NOTHING;

INSERT INTO public.visit (visit_id, clinic_id, clinic_patient_id, status)
VALUES ('aa000000-0000-4000-8000-0000000000a1',
        'a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000000a1', 'OPEN');

INSERT INTO public.clinic (id, code, name)
VALUES ('b0000000-0000-4000-8000-0000000000a2', 'TEST-LK-2', 'Phòng khám test thứ hai')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.consultation (id, clinic_id, visit_id, round_no, kind)
VALUES ('cc000000-0000-4000-8000-0000000000a1', 'a0000000-0000-4000-8000-000000000001',
        'aa000000-0000-4000-8000-0000000000a1', 1, 'PRIMARY');

-- ---------------------------------------------------------------------------
DO $lk$
DECLARE
    v_clinic  constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_other   constant uuid := 'b0000000-0000-4000-8000-0000000000a2';
    v_visit   constant uuid := 'aa000000-0000-4000-8000-0000000000a1';
    v_consult constant uuid := 'cc000000-0000-4000-8000-0000000000a1';
    v_staff   constant uuid := 'a1300000-0000-4000-8000-0000000000a1';
    v_ok boolean;
    t text;
BEGIN
    -- Vòng 1 phải là khám ban đầu; vòng đọc phải từ vòng 2.
    BEGIN
        INSERT INTO public.consultation (clinic_id, visit_id, round_no, kind)
        VALUES (v_clinic, v_visit, 2, 'PRIMARY');
        RAISE EXCEPTION 'consultation: PRIMARY ở vòng 2 lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- Kết quả phải đúng loại phiên.
    BEGIN
        UPDATE public.consultation
           SET status = 'completed', outcome = 'DONE', completed_at = now()
         WHERE id = v_consult;
        RAISE EXCEPTION 'consultation: PRIMARY kết thúc bằng DONE lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- Khoá ghép: lượt khám của phòng khám này không dùng được với clinic_id khác.
    BEGIN
        INSERT INTO public.encounter_flow (clinic_id, visit_id) VALUES (v_other, v_visit);
        RAISE EXCEPTION 'encounter_flow: nối chéo phòng khám lẽ ra bị chặn';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    -- Qua khỏi nháp mà không có người duyệt → chặn.
    BEGIN
        INSERT INTO public.service_order
            (clinic_id, visit_id, consultation_id, service_code, service_name,
             node_code, exec_status, recorded_by)
        VALUES (v_clinic, v_visit, v_consult, 'X', 'X', 'DICHVU-SIEUAM',
                'authorized', v_staff);
        RAISE EXCEPTION 'service_order: authorized không người duyệt lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- Nháp thì được.
    INSERT INTO public.service_order
        (clinic_id, visit_id, consultation_id, service_code, service_name,
         node_code, exec_status, recorded_by)
    VALUES (v_clinic, v_visit, v_consult, 'X', 'X', 'DICHVU-SIEUAM', 'draft', v_staff);

    -- Một dòng sống mỗi việc.
    INSERT INTO public.queue_entry (clinic_id, visit_id, lane, reason, ref_id, status, eligible_at)
    VALUES (v_clinic, v_visit, 'DOCTOR', 'PRIMARY', v_consult, 'waiting', now());
    BEGIN
        INSERT INTO public.queue_entry (clinic_id, visit_id, lane, reason, ref_id, status, eligible_at)
        VALUES (v_clinic, v_visit, 'DOCTOR', 'PRIMARY', v_consult, 'waiting', now());
        RAISE EXCEPTION 'queue_entry: hai dòng sống cho một việc lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;

    -- Một người chỉ đang ở một chỗ.
    UPDATE public.queue_entry SET status = 'serving'
     WHERE visit_id = v_visit AND reason = 'PRIMARY';
    BEGIN
        INSERT INTO public.queue_entry (clinic_id, visit_id, lane, reason, ref_id, status, eligible_at)
        VALUES (v_clinic, v_visit, 'DOCTOR', 'REVIEW', gen_random_uuid(), 'serving', now());
        RAISE EXCEPTION 'queue_entry: hai chỗ đang phục vụ cùng lúc lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;

    -- Xong việc rồi thì mở dòng mới cho cùng việc được.
    UPDATE public.queue_entry SET status = 'done'
     WHERE visit_id = v_visit AND reason = 'PRIMARY';
    INSERT INTO public.queue_entry (clinic_id, visit_id, lane, reason, ref_id, status, eligible_at)
    VALUES (v_clinic, v_visit, 'DOCTOR', 'PRIMARY', v_consult, 'waiting', now());

    -- Hàng bác sĩ không nhận lý do dịch vụ.
    BEGIN
        INSERT INTO public.queue_entry (clinic_id, visit_id, lane, reason, ref_id, status)
        VALUES (v_clinic, v_visit, 'DOCTOR', 'SERVICE', gen_random_uuid(), 'blocked');
        RAISE EXCEPTION 'queue_entry: hàng DOCTOR mang lý do SERVICE lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- Huyết áp ngược chiều bị chặn.
    BEGIN
        INSERT INTO public.vital_measurement (clinic_id, visit_id, systolic, diastolic, recorded_by)
        VALUES (v_clinic, v_visit, 80, 120, v_staff);
        RAISE EXCEPTION 'vital_measurement: tâm thu < tâm trương lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- RLS bật trên mọi bảng mới.
    FOREACH t IN ARRAY ARRAY['encounter_flow', 'vital_measurement', 'consultation',
                             'consultation_note', 'service_order', 'review_round',
                             'round_requirement', 'queue_entry', 'command_receipt']
    LOOP
        SELECT c.relrowsecurity INTO v_ok
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relname = t;
        IF v_ok IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'RLS chưa bật trên %', t;
        END IF;
    END LOOP;
END
$lk$;

ROLLBACK;
