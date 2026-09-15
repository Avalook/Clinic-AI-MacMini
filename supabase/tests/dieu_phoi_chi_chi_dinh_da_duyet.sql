-- Trưởng ca chỉ điều phối chỉ định bác sĩ đã duyệt (20260915000013).
--
-- move_visit_to_station: không tự sinh bước dịch vụ; rời bước dịch vụ không
-- đánh nó xong; nhà thuốc cần đơn thuốc; bước ga giữ hành vi cũ.
--
-- Tự dựng dữ liệu, cuối file ROLLBACK.

BEGIN;

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('a1100000-0000-4000-8000-0000000006a1',
        'a0000000-0000-4000-8000-000000000001', 'TEST-DP1', 'Cơ sở DP (test)')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.patient (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000006a1', 'BN-TEST-DP1', 'BN test DP1',
        'a1100000-0000-4000-8000-0000000006a1')
ON CONFLICT (clinic_patient_id) DO NOTHING;

INSERT INTO public.visit (visit_id, clinic_id, clinic_patient_id, status)
VALUES ('aa000000-0000-4000-8000-0000000006a1',
        'a0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-0000000006a1', 'IN_PROGRESS');

DO $dp$
DECLARE
    v_clinic constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_visit  constant uuid := 'aa000000-0000-4000-8000-0000000006a1';
    v_bn     constant uuid := 'e0000000-0000-4000-8000-0000000006a1';
    v_status text;
BEGIN
    -- Không chỉ định → không tạo được bước siêu âm.
    BEGIN
        PERFORM public.move_visit_to_station(v_clinic, v_visit, 'DICHVU-SIEUAM', NULL, NULL);
        RAISE EXCEPTION 'move: bước dịch vụ không chỉ định lẽ ra bị chặn';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE '%chưa có chỉ định%' THEN RAISE; END IF;
    END;
    IF EXISTS (SELECT 1 FROM public.work_item
                WHERE visit_id = v_visit AND node_code = 'DICHVU-SIEUAM') THEN
        RAISE EXCEPTION 'move: không được sinh work_item siêu âm';
    END IF;

    -- Có việc siêu âm (như order_services tạo) → điều phối được, vẫn PENDING.
    INSERT INTO public.work_item
        (clinic_id, node_code, node_version_id, clinic_patient_id, visit_id, status)
    SELECT v_clinic, n.code, nv.id, v_bn, v_visit, 'PENDING'
      FROM public.node_definition n
      JOIN public.node_definition_version nv
        ON nv.node_definition_id = n.id AND nv.version = n.current_version
     WHERE n.clinic_id = v_clinic AND n.code = 'DICHVU-SIEUAM';

    PERFORM public.move_visit_to_station(v_clinic, v_visit, 'DICHVU-SIEUAM', NULL, NULL);
    SELECT status INTO v_status FROM public.work_item
     WHERE visit_id = v_visit AND node_code = 'DICHVU-SIEUAM';
    IF v_status <> 'PENDING' THEN
        RAISE EXCEPTION 'move: điều phối không được tự bắt đầu dịch vụ, thấy %', v_status;
    END IF;

    -- Rời siêu âm sang bước ga → siêu âm vẫn chờ làm.
    PERFORM public.move_visit_to_station(v_clinic, v_visit, 'LUOTKHAM-14', NULL, NULL);
    SELECT status INTO v_status FROM public.work_item
     WHERE visit_id = v_visit AND node_code = 'DICHVU-SIEUAM';
    IF v_status <> 'PENDING' THEN
        RAISE EXCEPTION 'move: rời bước dịch vụ không được đánh xong, thấy %', v_status;
    END IF;

    -- Bước ga rời đi thì đóng như cũ.
    PERFORM public.move_visit_to_station(v_clinic, v_visit, 'LUOTKHAM-05', NULL, NULL);
    SELECT status INTO v_status FROM public.work_item
     WHERE visit_id = v_visit AND node_code = 'LUOTKHAM-14';
    IF v_status <> 'COMPLETED' THEN
        RAISE EXCEPTION 'move: bước ga rời đi phải COMPLETED, thấy %', v_status;
    END IF;

    -- Nhà thuốc cần đơn thuốc.
    BEGIN
        PERFORM public.move_visit_to_station(v_clinic, v_visit, 'THUOC-04', NULL, NULL);
        RAISE EXCEPTION 'move: sang nhà thuốc không đơn lẽ ra bị chặn';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE '%chưa có đơn thuốc%' THEN RAISE; END IF;
    END;
    INSERT INTO public.prescription (clinic_id, clinic_patient_id, visit_id, drug_name_raw, source_ref)
    VALUES (v_clinic, v_bn, v_visit, 'Paracetamol', 'test');
    PERFORM public.move_visit_to_station(v_clinic, v_visit, 'THUOC-04', NULL, NULL);
END
$dp$;

ROLLBACK;
