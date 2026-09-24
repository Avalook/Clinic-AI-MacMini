-- Service Lifecycle v1 — Slice 1: nền schema (20260922000001).
--
-- Kiểm ràng buộc DB của ba trục selection / routing / execution,
-- service_selection_state, service_execution_attempt; và chỉ mục một-lần-thu
-- của payment_cycle theo loại.
--
-- Tự dựng dữ liệu, cuối file ROLLBACK.

BEGIN;

-- Dữ liệu dựng riêng cho file này (id 1c000000-…), không phải dữ liệu thật.
DO $fixture$
BEGIN
    INSERT INTO public.clinic (id, code, name)
    VALUES ('1c000000-0000-4000-8000-00000000000b', 'TEST-LC-B', 'PK B (test lifecycle)');

    INSERT INTO public.clinic_location (id, clinic_id, code, name)
    VALUES ('1c000000-0000-4000-8000-0000000001a1',
            'a0000000-0000-4000-8000-000000000001', 'TEST-LC1', 'Cơ sở LC (test)');

    INSERT INTO public.staff (id, primary_location_id, full_name, primary_department)
    VALUES ('1c000000-0000-4000-8000-0000000005f1',
            '1c000000-0000-4000-8000-0000000001a1', 'NV test LC', 'DOCTOR');

    INSERT INTO public.patient (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
    VALUES ('a0000000-0000-4000-8000-000000000001',
            '1c000000-0000-4000-8000-0000000000b1', 'BN-TEST-LC1', 'BN test LC1',
            '1c000000-0000-4000-8000-0000000001a1');

    INSERT INTO public.visit (visit_id, clinic_id, clinic_patient_id, status)
    VALUES ('1c000000-0000-4000-8000-0000000000a1',
            'a0000000-0000-4000-8000-000000000001',
            '1c000000-0000-4000-8000-0000000000b1', 'IN_PROGRESS');

    INSERT INTO public.consultation (id, clinic_id, visit_id, round_no, kind)
    VALUES ('1c000000-0000-4000-8000-0000000000c1',
            'a0000000-0000-4000-8000-000000000001',
            '1c000000-0000-4000-8000-0000000000a1', 1, 'PRIMARY');

    INSERT INTO public.clinic_room (id, clinic_id, location_id, code, name, node_code)
    VALUES ('1c000000-0000-4000-8000-0000000000e1',
            'a0000000-0000-4000-8000-000000000001',
            '1c000000-0000-4000-8000-0000000001a1', 'TEST-LC-SA1', 'SA1 (test)',
            'DICHVU-SIEUAM');
END
$fixture$;

DO $lc$
DECLARE
    v_clinic  constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_clinicb constant uuid := '1c000000-0000-4000-8000-00000000000b';
    v_visit   constant uuid := '1c000000-0000-4000-8000-0000000000a1';
    v_consult constant uuid := '1c000000-0000-4000-8000-0000000000c1';
    v_staff   constant uuid := '1c000000-0000-4000-8000-0000000005f1';
    v_room    constant uuid := '1c000000-0000-4000-8000-0000000000e1';
    v_legacy  uuid;
    v_order   uuid;
    v_attempt uuid;
    r         record;
BEGIN
    -- ── 2. Dòng ghi kiểu CŨ (không nhắc cột mới) không bị suy trục mới ──────
    INSERT INTO public.service_order (clinic_id, visit_id, consultation_id,
        service_code, service_name, node_code, exec_status, recorded_by,
        authorized_by, authorized_at, room_id, assigned_by, assigned_at)
    VALUES (v_clinic, v_visit, v_consult, 'SA', 'Siêu âm', 'DICHVU-SIEUAM',
        'assigned', v_staff, v_staff, now(), v_room, v_staff, now())
    RETURNING id INTO v_legacy;

    SELECT selection_status, routing_status, routing_revision,
           execution_status, execution_revision
      INTO r FROM public.service_order WHERE id = v_legacy;
    IF r.selection_status IS NOT NULL OR r.routing_status IS NOT NULL
       OR r.execution_status IS NOT NULL
       OR r.routing_revision <> 0 OR r.execution_revision <> 0 THEN
        RAISE EXCEPTION 'legacy: trục mới phải NULL/0, thấy %', r;
    END IF;

    -- Dòng draft: selection_status không có DEFAULT PENDING.
    INSERT INTO public.service_order (clinic_id, visit_id, consultation_id,
        service_code, service_name, node_code, exec_status, recorded_by)
    VALUES (v_clinic, v_visit, v_consult, 'XN', 'Xét nghiệm', 'DICHVU-SIEUAM',
        'draft', v_staff)
    RETURNING id INTO v_order;
    IF (SELECT selection_status FROM public.service_order WHERE id = v_order)
       IS NOT NULL THEN
        RAISE EXCEPTION 'draft: selection_status không được có DEFAULT';
    END IF;

    -- ── 3. selection_status ────────────────────────────────────────────────
    UPDATE public.service_order SET selection_status = 'PENDING' WHERE id = v_legacy;
    UPDATE public.service_order SET selection_status = 'SELECTED' WHERE id = v_legacy;
    UPDATE public.service_order SET selection_status = 'NOT_SELECTED' WHERE id = v_legacy;
    BEGIN
        UPDATE public.service_order SET selection_status = 'DECLINED' WHERE id = v_legacy;
        RAISE EXCEPTION 'selection: DECLINED lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- ── 4. routing_status + routing_revision ───────────────────────────────
    UPDATE public.service_order
       SET routing_status = 'ASSIGNED', routing_revision = 1 WHERE id = v_legacy;
    -- 20260922000005: mất hiệu lực thì không còn trỏ phòng (như
    -- InvalidateServiceRouting: hình chiếu cũ về 'authorized', room_id NULL).
    BEGIN
        UPDATE public.service_order
           SET routing_status = 'REASSIGNMENT_REQUIRED', routing_revision = 2
         WHERE id = v_legacy;
        RAISE EXCEPTION 'routing: REASSIGNMENT_REQUIRED còn phòng lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    UPDATE public.service_order
       SET routing_status = 'REASSIGNMENT_REQUIRED', routing_revision = 2,
           exec_status = 'authorized', room_id = NULL, assigned_by = NULL,
           assigned_at = NULL
     WHERE id = v_legacy;
    BEGIN
        UPDATE public.service_order SET routing_status = 'ASSIGNED' WHERE id = v_legacy;
        RAISE EXCEPTION 'routing: ASSIGNED không phòng lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    UPDATE public.service_order SET routing_status = 'UNASSIGNED' WHERE id = v_legacy;
    BEGIN
        UPDATE public.service_order SET routing_status = 'ROUTED' WHERE id = v_legacy;
        RAISE EXCEPTION 'routing: ROUTED lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_order SET routing_revision = -1 WHERE id = v_legacy;
        RAISE EXCEPTION 'routing: revision âm lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_order SET routing_revision = NULL WHERE id = v_legacy;
        RAISE EXCEPTION 'routing: revision NULL lẽ ra bị chặn';
    EXCEPTION WHEN not_null_violation THEN NULL;
    END;

    -- ── 5. execution_status: WAITING không bao giờ được lưu ────────────────
    FOR r IN SELECT unnest(ARRAY['PENDING', 'IN_PROGRESS', 'COMPLETED',
                                 'CANCELLED', 'NOT_PERFORMED', 'INTERRUPTED']) AS s
    LOOP
        UPDATE public.service_order SET execution_status = r.s WHERE id = v_legacy;
    END LOOP;
    BEGIN
        UPDATE public.service_order SET execution_status = 'WAITING' WHERE id = v_legacy;
        RAISE EXCEPTION 'execution: WAITING lẽ ra bị chặn (UPDATE)';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO public.service_order (clinic_id, visit_id, consultation_id,
            service_code, service_name, node_code, exec_status, recorded_by,
            authorized_by, authorized_at, execution_status)
        VALUES (v_clinic, v_visit, v_consult, 'SA', 'Siêu âm', 'DICHVU-SIEUAM',
            'authorized', v_staff, v_staff, now(), 'WAITING');
        RAISE EXCEPTION 'execution: WAITING lẽ ra bị chặn (INSERT)';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_order SET execution_revision = -1 WHERE id = v_legacy;
        RAISE EXCEPTION 'execution: revision âm lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- ── service_selection_state ────────────────────────────────────────────
    INSERT INTO public.service_selection_state
        (clinic_id, visit_id, revision, confirmed_by, confirmed_at)
    VALUES (v_clinic, v_visit, 1, v_staff, now());
    BEGIN
        INSERT INTO public.service_selection_state
            (clinic_id, visit_id, revision, confirmed_by, confirmed_at)
        VALUES (v_clinic, v_visit, 2, v_staff, now());
        RAISE EXCEPTION 'selection_state: hai dòng một lượt lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_selection_state SET revision = 0
         WHERE clinic_id = v_clinic AND visit_id = v_visit;
        RAISE EXCEPTION 'selection_state: revision 0 lẽ ra bị chặn (không dòng = 0)';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        -- Lượt của clinic A không được gắn dưới clinic B.
        INSERT INTO public.service_selection_state
            (clinic_id, visit_id, revision, confirmed_by, confirmed_at)
        VALUES (v_clinicb, v_visit, 1, v_staff, now());
        RAISE EXCEPTION 'selection_state: lệch clinic lẽ ra bị chặn';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    -- ── 6. attempt_no duy nhất trong order ─────────────────────────────────
    INSERT INTO public.service_execution_attempt (clinic_id, service_order_id,
        attempt_no, room_id_snapshot, routing_revision_snapshot, status,
        started_by, started_at, interrupted_by, interrupted_at,
        interruption_reason_code)
    VALUES (v_clinic, v_legacy, 1, v_room, 1, 'INTERRUPTED',
        v_staff, now() - interval '10 minutes', v_staff, now() - interval '5 minutes',
        'EQUIPMENT_FAILURE');
    BEGIN
        INSERT INTO public.service_execution_attempt (clinic_id, service_order_id,
            attempt_no, routing_revision_snapshot, status, started_by, started_at)
        VALUES (v_clinic, v_legacy, 1, 1, 'IN_PROGRESS', v_staff, now());
        RAISE EXCEPTION 'attempt: trùng attempt_no lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO public.service_execution_attempt (clinic_id, service_order_id,
            attempt_no, routing_revision_snapshot, status, started_by, started_at)
        VALUES (v_clinic, v_legacy, 0, 1, 'IN_PROGRESS', v_staff, now());
        RAISE EXCEPTION 'attempt: attempt_no 0 lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- ── 7. Tối đa một IN_PROGRESS mỗi order ────────────────────────────────
    INSERT INTO public.service_execution_attempt (clinic_id, service_order_id,
        attempt_no, room_id_snapshot, routing_revision_snapshot, status,
        started_by, started_at)
    VALUES (v_clinic, v_legacy, 2, v_room, 2, 'IN_PROGRESS', v_staff, now())
    RETURNING id INTO v_attempt;
    BEGIN
        INSERT INTO public.service_execution_attempt (clinic_id, service_order_id,
            attempt_no, routing_revision_snapshot, status, started_by, started_at)
        VALUES (v_clinic, v_legacy, 3, 2, 'IN_PROGRESS', v_staff, now());
        RAISE EXCEPTION 'attempt: hai IN_PROGRESS lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;

    -- ── 8. Trường hoàn thành / gián đoạn khớp trạng thái ───────────────────
    BEGIN
        UPDATE public.service_execution_attempt SET status = 'COMPLETED'
         WHERE id = v_attempt;
        RAISE EXCEPTION 'attempt: COMPLETED thiếu completed_* lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_execution_attempt
           SET completed_by = v_staff, completed_at = now() WHERE id = v_attempt;
        RAISE EXCEPTION 'attempt: IN_PROGRESS có completed_* lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_execution_attempt
           SET status = 'COMPLETED', completed_by = v_staff,
               completed_at = started_at - interval '1 minute'
         WHERE id = v_attempt;
        RAISE EXCEPTION 'attempt: completed_at trước started_at lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_execution_attempt
           SET status = 'INTERRUPTED', interrupted_by = v_staff,
               interrupted_at = now()
         WHERE id = v_attempt;
        RAISE EXCEPTION 'attempt: INTERRUPTED thiếu lý do lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_execution_attempt
           SET status = 'INTERRUPTED', interrupted_by = v_staff,
               interrupted_at = now(), interruption_reason_code = 'OTHER'
         WHERE id = v_attempt;
        RAISE EXCEPTION 'attempt: OTHER không ghi chú lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_execution_attempt
           SET status = 'INTERRUPTED', interrupted_by = v_staff,
               interrupted_at = now(), interruption_reason_code = 'BROKEN'
         WHERE id = v_attempt;
        RAISE EXCEPTION 'attempt: mã lý do lạ lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_execution_attempt
           SET interruption_reason_note = 'ghi chú lạc' WHERE id = v_attempt;
        RAISE EXCEPTION 'attempt: IN_PROGRESS có lý do gián đoạn lẽ ra bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE public.service_execution_attempt SET status = 'NOT_PERFORMED'
         WHERE id = v_attempt;
        RAISE EXCEPTION 'attempt: NOT_PERFORMED không phải trạng thái attempt';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    UPDATE public.service_execution_attempt
       SET status = 'COMPLETED', completed_by = v_staff, completed_at = now()
     WHERE id = v_attempt;
    -- Hết attempt đang chạy → được mở attempt mới.
    INSERT INTO public.service_execution_attempt (clinic_id, service_order_id,
        attempt_no, routing_revision_snapshot, status, started_by, started_at,
        interrupted_by, interrupted_at, interruption_reason_code,
        interruption_reason_note)
    VALUES (v_clinic, v_legacy, 3, 2, 'INTERRUPTED', v_staff, now(),
        v_staff, now(), 'OTHER', 'Khách cần về gấp');

    -- Tenant: attempt dưới clinic B trỏ order / phòng của clinic A.
    BEGIN
        INSERT INTO public.service_execution_attempt (clinic_id, service_order_id,
            attempt_no, routing_revision_snapshot, status, started_by, started_at)
        VALUES (v_clinicb, v_legacy, 9, 0, 'IN_PROGRESS', v_staff, now());
        RAISE EXCEPTION 'attempt: order khác clinic lẽ ra bị chặn';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO public.service_execution_attempt (clinic_id, service_order_id,
            attempt_no, room_id_snapshot, routing_revision_snapshot, status,
            started_by, started_at)
        VALUES (v_clinic, v_order, 1, '40ac2193-5996-4ee1-aab5-000000000000',
            0, 'IN_PROGRESS', v_staff, now());
        RAISE EXCEPTION 'attempt: phòng không tồn tại lẽ ra bị chặn';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    -- Attempt là lịch sử: không xoá order khi đã có attempt.
    BEGIN
        DELETE FROM public.service_order WHERE id = v_legacy;
        RAISE EXCEPTION 'attempt: xoá order có attempt lẽ ra bị chặn';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
END
$lc$;

-- ── 10/11. payment_cycle theo loại (20260922000003 thay chỉ mục của Slice 1) ─
-- Hai loại đều chặn hai lần chờ xác minh. Thuốc còn chặn PAID khi đang chờ;
-- dịch vụ thì không — thu nhiều lần là hợp lệ (chi tiết: thu_dich_vu_nhieu_lan.sql).
DO $pc$
DECLARE
    v_clinic constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_visit  constant uuid := '1c000000-0000-4000-8000-0000000000a1';
    v_staff  constant uuid := '1c000000-0000-4000-8000-0000000005f1';
    k        text;
BEGIN
    FOREACH k IN ARRAY ARRAY['thuoc', 'dich_vu'] LOOP
        INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id,
            kind, amount, bill_revision, method, status, created_by)
        VALUES (gen_random_uuid(), v_clinic, v_visit, k, 100000, 'r1', 'QR',
            'PENDING_VERIFICATION', v_staff);
        BEGIN
            INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id,
                kind, amount, bill_revision, method, status, created_by)
            VALUES (gen_random_uuid(), v_clinic, v_visit, k, 100000, 'r2', 'QR',
                'PENDING_VERIFICATION', v_staff);
            RAISE EXCEPTION 'payment_cycle %: hai lần chờ xác minh lẽ ra bị chặn', k;
        EXCEPTION WHEN unique_violation THEN NULL;
        END;
    END LOOP;
    BEGIN
        INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id,
            kind, amount, bill_revision, method, status, created_by,
            paid_at, confirmed_by)
        VALUES (gen_random_uuid(), v_clinic, v_visit, 'thuoc', 100000, 'r3', 'CASH',
            'PAID', v_staff, now(), v_staff);
        RAISE EXCEPTION 'payment_cycle thuoc: PAID khi đang chờ lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id,
        kind, amount, bill_revision, method, status, created_by,
        paid_at, confirmed_by)
    VALUES (gen_random_uuid(), v_clinic, v_visit, 'dich_vu', 100000, 'r3', 'CASH',
        'PAID', v_staff, now(), v_staff);
END
$pc$;

ROLLBACK;
