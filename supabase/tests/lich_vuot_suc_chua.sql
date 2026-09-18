-- Lịch vượt sức chứa sau khi công bố lịch trực → việc CSKH từng lịch
-- (20260915000014, Tuyền chốt 15/09/2026): trần online 2 mà có 3 lịch thì lịch
-- ĐẶT SAU CÙNG thành việc VUOT_SUC_CHUA; CSKH gọi chốt thì hết; tuần chưa công
-- bố thì không có việc nào.

BEGIN;

DO $$
DECLARE
    pk    uuid := 'a0000000-0000-4000-8000-000000000001';
    loc   uuid;
    sv    uuid;
    bs    uuid;
    nv    uuid;
    tran  integer;
    slot  timestamptz;
    tuan  date;
    ap    uuid;
    muon  uuid;
    bn    uuid;
BEGIN
    INSERT INTO public.clinic_location (clinic_id, code, name)
    VALUES (pk, 'VUOT-TRAN', 'CS vượt trần') RETURNING id INTO loc;
    INSERT INTO public.service_type (clinic_id, code, name, is_active)
    VALUES (pk, 'VUOT-TRAN', 'Khám vượt trần', true) RETURNING id INTO sv;
    INSERT INTO public.staff (primary_location_id, full_name, primary_department)
    VALUES (loc, 'BS vượt trần', 'DOCTOR') RETURNING id INTO bs;
    INSERT INTO public.staff (primary_location_id, full_name, primary_department)
    VALUES (loc, 'CSKH vượt trần', 'CSKH') RETURNING id INTO nv;

    -- Thứ Ba tuần sau nữa, 09:00 VN: chắc chắn tương lai và cả tuần chưa công bố.
    tuan := date_trunc('week', (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::date + 14;
    slot := ((tuan + 1) + time '09:00') AT TIME ZONE 'Asia/Ho_Chi_Minh';
    SELECT regular_cap INTO tran FROM public.resolve_effective_cap(pk, bs, slot);
    DELETE FROM public.roster_week WHERE clinic_id = pk AND week_start = tuan;

    -- Tuần chưa công bố: đặt vượt trần thoải mái.
    FOR i IN 1..(tran + 1) LOOP
        INSERT INTO public.patient (clinic_id, location_id, patient_code, full_name)
        VALUES (pk, loc, 'BN-VUOT-' || i, 'Khách vượt ' || i)
        RETURNING clinic_patient_id INTO bn;
        INSERT INTO public.appointment (clinic_id, location_id, clinic_patient_id,
            service_type_id, doctor_id, slot_start, slot_end, status,
            booking_channel, created_at)
        VALUES (pk, loc, bn, sv, bs, slot, slot + interval '15 minutes',
                'CONFIRMED', 'HOTLINE', now() - make_interval(hours => 10 - i))
        RETURNING id INTO ap;
        muon := ap;   -- vòng cuối = người đặt sau cùng
    END LOOP;

    IF EXISTS (SELECT 1 FROM public.v_viec_cskh WHERE trang_thai = 'VUOT_SUC_CHUA'
                AND appointment_id IN (SELECT id FROM public.appointment WHERE doctor_id = bs)) THEN
        RAISE EXCEPTION 'Tuần chưa công bố lịch trực không được sinh việc vượt sức chứa';
    END IF;

    -- Công bố lịch trực → đúng MỘT việc, cho người đặt sau cùng.
    INSERT INTO public.roster_week (clinic_id, week_start, applied_at)
    VALUES (pk, tuan, now() - interval '1 minute');
    IF (SELECT count(*) FROM public.v_viec_cskh WHERE trang_thai = 'VUOT_SUC_CHUA'
          AND appointment_id IN (SELECT id FROM public.appointment WHERE doctor_id = bs)) <> 1
       OR NOT EXISTS (SELECT 1 FROM public.v_viec_cskh
                       WHERE trang_thai = 'VUOT_SUC_CHUA' AND appointment_id = muon) THEN
        RAISE EXCEPTION 'Sau công bố phải có đúng một việc vượt sức chứa, cho lịch đặt sau cùng';
    END IF;

    -- CSKH gọi, khách chốt giữ lịch → việc hết.
    INSERT INTO public.tuong_tac_cskh (clinic_id, clinic_patient_id, appointment_id,
        loai, kenh, ket_qua, nhan_vien_staff_id, trang_thai_ma)
    SELECT pk, clinic_patient_id, id, 'XAC_NHAN_LICH', 'GOI', 'DA_LIEN_HE', nv, 'VUOT_SUC_CHUA'
      FROM public.appointment WHERE id = muon;
    IF EXISTS (SELECT 1 FROM public.v_viec_cskh
                WHERE trang_thai = 'VUOT_SUC_CHUA' AND appointment_id = muon) THEN
        RAISE EXCEPTION 'CSKH đã gọi chốt mà việc vượt sức chứa vẫn mở';
    END IF;
END $$;

ROLLBACK;
