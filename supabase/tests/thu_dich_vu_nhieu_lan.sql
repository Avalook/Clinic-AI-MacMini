-- Thu tiền dịch vụ nhiều lần (20260922000003).
--
-- Chỉ mục theo loại, chốt DB chống phủ trùng, và backfill lịch sử không còn
-- dựa vào chỉ mục cũ. Tự dựng dữ liệu, cuối file ROLLBACK.

BEGIN;

-- Dữ liệu dựng riêng cho file này (id 1e000000-…), không phải dữ liệu thật.
DO $fixture$
BEGIN
    INSERT INTO public.clinic_location (id, clinic_id, code, name)
    VALUES ('1e000000-0000-4000-8000-0000000001a1',
            'a0000000-0000-4000-8000-000000000001', 'TEST-TN1', 'Cơ sở TN (test)');

    INSERT INTO public.staff (id, primary_location_id, full_name, primary_department)
    VALUES ('1e000000-0000-4000-8000-0000000005f1',
            '1e000000-0000-4000-8000-0000000001a1', 'NV test TN', 'CASHIER');

    INSERT INTO public.patient (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
    VALUES ('a0000000-0000-4000-8000-000000000001',
            '1e000000-0000-4000-8000-0000000000b1', 'BN-TEST-TN1', 'BN test TN1',
            '1e000000-0000-4000-8000-0000000001a1');

    INSERT INTO public.visit (visit_id, clinic_id, clinic_patient_id, status)
    VALUES ('1e000000-0000-4000-8000-0000000000a1',
            'a0000000-0000-4000-8000-000000000001',
            '1e000000-0000-4000-8000-0000000000b1', 'IN_PROGRESS'),
           ('1e000000-0000-4000-8000-0000000000a2',
            'a0000000-0000-4000-8000-000000000001',
            '1e000000-0000-4000-8000-0000000000b1', 'IN_PROGRESS');
END
$fixture$;

-- ── Chỉ mục theo loại ──────────────────────────────────────────────────────
DO $chi_muc$
DECLARE
    v_clinic constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_visit  constant uuid := '1e000000-0000-4000-8000-0000000000a1';
    v_staff  constant uuid := '1e000000-0000-4000-8000-0000000005f1';
BEGIN
    IF to_regclass('public.uq_payment_cycle_mot_lan_song') IS NOT NULL THEN
        RAISE EXCEPTION 'chỉ mục cũ uq_payment_cycle_mot_lan_song phải đã bị bỏ';
    END IF;

    -- Nhiều lần PAID dịch vụ trên cùng lượt: hợp lệ.
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,
        amount, bill_revision, method, status, created_by, paid_at, confirmed_by)
    SELECT gen_random_uuid(), v_clinic, v_visit, 'dich_vu', 1000, 'r', 'CASH',
           'PAID', v_staff, now(), v_staff
      FROM generate_series(1, 3);

    -- Một lần chờ xác minh dịch vụ; lần chờ thứ hai bị chặn.
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,
        amount, bill_revision, method, status, created_by)
    VALUES (gen_random_uuid(), v_clinic, v_visit, 'dich_vu', 1000, 'r', 'QR',
            'PENDING_VERIFICATION', v_staff);
    BEGIN
        INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id,
            kind, amount, bill_revision, method, status, created_by)
        VALUES (gen_random_uuid(), v_clinic, v_visit, 'dich_vu', 1000, 'r', 'QR',
                'PENDING_VERIFICATION', v_staff);
        RAISE EXCEPTION 'dich_vu: hai lần chờ xác minh lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;

    -- Thuốc giữ luật cũ: tối đa một lần sống (chờ hoặc đã thu).
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,
        amount, bill_revision, method, status, created_by, paid_at, confirmed_by)
    VALUES (gen_random_uuid(), v_clinic, v_visit, 'thuoc', 1000, 'r', 'CASH',
            'PAID', v_staff, now(), v_staff);
    BEGIN
        INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id,
            kind, amount, bill_revision, method, status, created_by, paid_at,
            confirmed_by)
        VALUES (gen_random_uuid(), v_clinic, v_visit, 'thuoc', 1000, 'r', 'CASH',
                'PAID', v_staff, now(), v_staff);
        RAISE EXCEPTION 'thuoc: hai lần PAID lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id,
            kind, amount, bill_revision, method, status, created_by)
        VALUES (gen_random_uuid(), v_clinic, v_visit, 'thuoc', 1000, 'r', 'QR',
                'PENDING_VERIFICATION', v_staff);
        RAISE EXCEPTION 'thuoc: chờ xác minh khi đã có PAID lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
END
$chi_muc$;

-- ── Chốt chống phủ trùng ────────────────────────────────────────────────────
DO $phu$
DECLARE
    v_clinic constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_visit  constant uuid := '1e000000-0000-4000-8000-0000000000a2';
    v_staff  constant uuid := '1e000000-0000-4000-8000-0000000005f1';
    v_nguon  constant text := '1e000000-0000-4000-8000-0000000000d1';
    c_huy uuid := gen_random_uuid();
    c_a   uuid := gen_random_uuid();
    c_b   uuid := gen_random_uuid();
    c_c   uuid := gen_random_uuid();
BEGIN
    -- Lần chờ đã huỷ, CHƯA từng nhận tiền: không giữ phủ.
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,
        amount, bill_revision, method, status, created_by, closed_at, closed_by,
        close_reason)
    VALUES (c_huy, v_clinic, v_visit, 'dich_vu', 1000, 'r', 'QR', 'CANCELLED',
            v_staff, now(), v_staff, 'Khách không chuyển');
    INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
        kind, source_type, source_id, name_snapshot, quantity, unit_price,
        line_total, billing_owner)
    VALUES (v_clinic, c_huy, v_visit, 'dich_vu', 'service_order', v_nguon, 'SA',
            1, 1000, 1000, 'CLINIC');

    -- Lần thu A phủ nguồn — được, vì lần huỷ không giữ phủ.
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,
        amount, bill_revision, method, status, created_by, paid_at, confirmed_by)
    VALUES (c_a, v_clinic, v_visit, 'dich_vu', 1000, 'r', 'CASH', 'PAID', v_staff,
            now(), v_staff);
    INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
        kind, source_type, source_id, name_snapshot, quantity, unit_price,
        line_total, billing_owner)
    VALUES (v_clinic, c_a, v_visit, 'dich_vu', 'service_order', v_nguon, 'SA', 1,
            1000, 1000, 'CLINIC'),
           (v_clinic, c_a, v_visit, 'dich_vu', 'exam', 'exam-' || v_visit, 'Khám',
            1, 1000, 1000, 'CLINIC');

    -- Lần thu B phủ lại cùng chỉ định / cùng tiền khám: bị chặn.
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,
        amount, bill_revision, method, status, created_by, paid_at, confirmed_by)
    VALUES (c_b, v_clinic, v_visit, 'dich_vu', 1000, 'r', 'CASH', 'PAID', v_staff,
            now(), v_staff);
    BEGIN
        INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
            kind, source_type, source_id, name_snapshot, quantity, unit_price,
            line_total, billing_owner)
        VALUES (v_clinic, c_b, v_visit, 'dich_vu', 'service_order', v_nguon, 'SA',
                1, 1000, 1000, 'CLINIC');
        RAISE EXCEPTION 'phủ trùng chỉ định lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
            kind, source_type, source_id, name_snapshot, quantity, unit_price,
            line_total, billing_owner)
        VALUES (v_clinic, c_b, v_visit, 'dich_vu', 'exam', 'exam-' || v_visit,
                'Khám', 1, 1000, 1000, 'CLINIC');
        RAISE EXCEPTION 'thu lại tiền khám lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    -- A đã HUỶ phiếu (thu nhầm) → B phủ lại ĐƯỢC (Tuyền chốt 24/09/2026,
    -- migration 20260925000001): phiếu huỷ chỉ còn để đối chiếu.
    UPDATE public.payment_cycle
       SET status = 'VOIDED', closed_at = now(), closed_by = v_staff,
           close_reason = 'Huỷ để kiểm thử'
     WHERE payment_cycle_id = c_a;
    INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
        kind, source_type, source_id, name_snapshot, quantity, unit_price,
        line_total, billing_owner)
    VALUES (v_clinic, c_b, v_visit, 'dich_vu', 'service_order', v_nguon, 'SA',
            1, 1000, 1000, 'CLINIC');
    -- Nhưng B đang PAID thì lần thu thứ ba vẫn KHÔNG phủ trùng được.
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,
        amount, bill_revision, method, status, created_by, paid_at, confirmed_by)
    VALUES (c_c, v_clinic, v_visit, 'dich_vu', 1000, 'r', 'CASH', 'PAID', v_staff,
            now(), v_staff);
    BEGIN
        INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
            kind, source_type, source_id, name_snapshot, quantity, unit_price,
            line_total, billing_owner)
        VALUES (v_clinic, c_c, v_visit, 'dich_vu', 'service_order', v_nguon, 'SA',
                1, 1000, 1000, 'CLINIC');
        RAISE EXCEPTION 'phủ trùng lần PAID mới lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    -- Dòng đối tác tự thu không phải phủ của phòng khám.
    INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
        kind, source_type, source_id, name_snapshot, quantity, billing_owner)
    VALUES (v_clinic, c_b, v_visit, 'dich_vu', 'service_order', v_nguon, 'SA', 1,
            'EXTERNAL_PARTNER');
END
$phu$;

-- ── Trùng nguồn TRONG CÙNG một lần thu (20260922000004) ────────────────────
DO $cung_lan$
DECLARE
    v_clinic constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_visit  constant uuid := '1e000000-0000-4000-8000-0000000000a1';
    v_staff  constant uuid := '1e000000-0000-4000-8000-0000000005f1';
    v_x      constant text := '1e000000-0000-4000-8000-0000000000e1';
    v_y      constant text := '1e000000-0000-4000-8000-0000000000e2';
    v_exam   constant text := 'exam-1e000000-0000-4000-8000-0000000000c9';
    c        uuid := gen_random_uuid();
BEGIN
    INSERT INTO public.payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,
        amount, bill_revision, method, status, created_by, paid_at, confirmed_by)
    VALUES (c, v_clinic, v_visit, 'dich_vu', 1000, 'r', 'CASH', 'PAID', v_staff,
            now(), v_staff);
    -- Lần đầu: chỉ định X, tiền khám, và nguồn Y khác — cùng một lần thu: được.
    INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
        kind, source_type, source_id, name_snapshot, quantity, unit_price,
        line_total, billing_owner)
    VALUES (v_clinic, c, v_visit, 'dich_vu', 'service_order', v_x, 'SA', 1, 1000,
            1000, 'CLINIC'),
           (v_clinic, c, v_visit, 'dich_vu', 'service_order', v_y, 'XN', 1, 1000,
            1000, 'CLINIC'),
           (v_clinic, c, v_visit, 'dich_vu', 'exam', v_exam, 'Khám', 1, 1000,
            1000, 'CLINIC');
    -- X lần hai trong CHÍNH lần thu ấy: bị chặn.
    BEGIN
        INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id,
            visit_id, kind, source_type, source_id, name_snapshot, quantity,
            unit_price, line_total, billing_owner)
        VALUES (v_clinic, c, v_visit, 'dich_vu', 'service_order', v_x, 'SA', 1,
                1000, 1000, 'CLINIC');
        RAISE EXCEPTION 'chỉ định trùng trong cùng lần thu lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    -- Tiền khám lần hai trong chính lần thu ấy: bị chặn.
    BEGIN
        INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id,
            visit_id, kind, source_type, source_id, name_snapshot, quantity,
            unit_price, line_total, billing_owner)
        VALUES (v_clinic, c, v_visit, 'dich_vu', 'exam', v_exam, 'Khám', 1, 1000,
                1000, 'CLINIC');
        RAISE EXCEPTION 'tiền khám trùng trong cùng lần thu lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    -- Trùng trong CÙNG MỘT câu lệnh cũng bị chặn.
    BEGIN
        INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id,
            visit_id, kind, source_type, source_id, name_snapshot, quantity,
            unit_price, line_total, billing_owner)
        SELECT v_clinic, c, v_visit, 'dich_vu', 'service_order',
               '1e000000-0000-4000-8000-0000000000e3', 'SA', 1, 1000, 1000,
               'CLINIC'
          FROM generate_series(1, 2);
        RAISE EXCEPTION 'hai dòng trùng trong một câu lệnh lẽ ra bị chặn';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    -- Dòng đối tác cùng nguồn X không phải phủ của phòng khám: vẫn chèn được.
    INSERT INTO public.payment_bill_line (clinic_id, payment_cycle_id, visit_id,
        kind, source_type, source_id, name_snapshot, quantity, billing_owner)
    VALUES (v_clinic, c, v_visit, 'dich_vu', 'service_order', v_x, 'SA', 1,
            'EXTERNAL_PARTNER'),
           (v_clinic, c, v_visit, 'dich_vu', 'service_order', v_x, 'SA', 1,
            'EXTERNAL_PARTNER');
END
$cung_lan$;

-- ── Backfill: chạy lại sạch; nhóm mâu thuẫn không chọn hộ ────────────────
DO $backfill$
DECLARE
    v_clinic constant uuid := 'a0000000-0000-4000-8000-000000000001';
    v_vid    uuid;
    v_pid    constant uuid := '1e000000-0000-4000-8000-0000000000b1';
    a uuid := gen_random_uuid();
    b uuid := gen_random_uuid();
    kq record;
BEGIN
    INSERT INTO public.visit (clinic_id, clinic_patient_id, status)
    VALUES (v_clinic, v_pid, 'IN_PROGRESS') RETURNING visit_id INTO v_vid;
    -- Hai lần "đã thu" cũ cùng (lượt, loại), không có "đã huỷ" và không có dòng
    -- payment: mâu thuẫn — không lần nào được dựng lại.
    INSERT INTO public.event_log (clinic_id, event_type, aggregate_type,
        aggregate_id, payload, source, occurred_at)
    SELECT v_clinic, 'payment.recorded', 'payment', x.cid,
           jsonb_build_object('payment_cycle_id', x.cid, 'visit_id', v_vid,
                              'kind', 'dich_vu', 'amount', 50000),
           'test', now() - x.lui
      FROM (VALUES (a, interval '2 hours'), (b, interval '1 hour')) AS x(cid, lui);

    SELECT * INTO kq FROM public.payment_cycle_backfill_legacy();
    IF EXISTS (SELECT 1 FROM public.payment_cycle
                WHERE payment_cycle_id IN (a, b)) THEN
        RAISE EXCEPTION 'backfill: nhóm mâu thuẫn không được chọn lần thu nào';
    END IF;
    IF kq.su_kien_bo_qua < 2 THEN
        RAISE EXCEPTION 'backfill: phải đếm cả hai sự kiện bị bỏ qua, thấy %',
            kq.su_kien_bo_qua;
    END IF;
    -- Chạy lại: sạch, không lỗi, không thêm gì.
    SELECT * INTO kq FROM public.payment_cycle_backfill_legacy();
    IF kq.tu_payment <> 0 OR kq.tu_su_kien <> 0 THEN
        RAISE EXCEPTION 'backfill chạy lại phải không thêm gì, thấy %', kq;
    END IF;
END
$backfill$;

ROLLBACK;
