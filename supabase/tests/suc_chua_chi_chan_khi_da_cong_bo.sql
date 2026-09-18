-- Trần sức chứa chỉ CHẶN khi tuần lịch trực ĐÃ CÔNG BỐ (20260915000001).
--
-- CONTEXT v1.0: đặt trước khi công bố thì nhận (đối soát lúc công bố); sau
-- công bố khung đầy thì chặn; khách vãng lai luôn bị trần walkin_cap.

BEGIN;

INSERT INTO public.clinic (id, code, name, settings)
VALUES ('c4000000-0000-4000-8000-0000000000c4', 'C4CONGBO', 'PK kiểm công bố',
        '{"booking": {"slot_minutes": 15, "regular_cap": 1, "walkin_cap": 1}}'::jsonb);
INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('c4000000-0000-4000-8000-0000000000a1',
        'c4000000-0000-4000-8000-0000000000c4', 'C4-A', 'Cơ sở C4');
INSERT INTO public.service_type (id, clinic_id, code, name, is_active)
VALUES ('c4000000-0000-4000-8000-0000000000b1',
        'c4000000-0000-4000-8000-0000000000c4', 'C4SV', 'Dịch vụ C4', true);
INSERT INTO public.staff (id, primary_location_id, full_name, primary_department)
VALUES ('c4000000-0000-4000-8000-0000000000d1',
        'c4000000-0000-4000-8000-0000000000a1', 'BS Công Bố', 'DOCTOR');

DO $$
DECLARE
    pk   uuid := 'c4000000-0000-4000-8000-0000000000c4';
    loc  uuid := 'c4000000-0000-4000-8000-0000000000a1';
    sv   uuid := 'c4000000-0000-4000-8000-0000000000b1';
    bs   uuid := 'c4000000-0000-4000-8000-0000000000d1';
    -- Hai tuần xa trong tương lai, 09:00 giờ VN thứ Ba.
    t_chua timestamptz := (date_trunc('week', now() + interval '300 days')::date
                           + 1 + time '09:00') AT TIME ZONE 'Asia/Ho_Chi_Minh';
    t_da   timestamptz := (date_trunc('week', now() + interval '307 days')::date
                           + 1 + time '09:00') AT TIME ZONE 'Asia/Ho_Chi_Minh';
    bn     uuid;
    i      int;
BEGIN
    INSERT INTO public.roster_week (clinic_id, week_start)
    VALUES (pk, date_trunc('week', (t_da AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::date);

    IF public.tuan_lich_truc_da_cong_bo(pk, t_chua)
       OR NOT public.tuan_lich_truc_da_cong_bo(pk, t_da) THEN
        RAISE EXCEPTION 'tuan_lich_truc_da_cong_bo trả sai tuần';
    END IF;

    -- 1. Tuần CHƯA công bố: trần 1 mà đặt được 3 lịch hẹn cùng khung.
    FOR i IN 1..3 LOOP
        INSERT INTO public.patient (clinic_id, location_id, patient_code, full_name)
        VALUES (pk, loc, 'BN-C4-CHUA-' || i, 'Khách chưa công bố ' || i)
        RETURNING clinic_patient_id INTO bn;
        INSERT INTO public.appointment (clinic_id, location_id, clinic_patient_id,
            service_type_id, doctor_id, slot_start, slot_end, status, booking_channel)
        VALUES (pk, loc, bn, sv, bs, t_chua, t_chua + interval '15 minutes',
                'SCHEDULED', 'HOTLINE');
    END LOOP;

    -- 2. Tuần ĐÃ công bố: lịch thứ hai cùng khung phải bị chặn.
    INSERT INTO public.patient (clinic_id, location_id, patient_code, full_name)
    VALUES (pk, loc, 'BN-C4-DA-1', 'Khách đã công bố 1')
    RETURNING clinic_patient_id INTO bn;
    INSERT INTO public.appointment (clinic_id, location_id, clinic_patient_id,
        service_type_id, doctor_id, slot_start, slot_end, status, booking_channel)
    VALUES (pk, loc, bn, sv, bs, t_da, t_da + interval '15 minutes',
            'SCHEDULED', 'HOTLINE');
    INSERT INTO public.patient (clinic_id, location_id, patient_code, full_name)
    VALUES (pk, loc, 'BN-C4-DA-2', 'Khách đã công bố 2')
    RETURNING clinic_patient_id INTO bn;
    BEGIN
        INSERT INTO public.appointment (clinic_id, location_id, clinic_patient_id,
            service_type_id, doctor_id, slot_start, slot_end, status, booking_channel)
        VALUES (pk, loc, bn, sv, bs, t_da, t_da + interval '15 minutes',
                'SCHEDULED', 'HOTLINE');
        RAISE EXCEPTION 'Tuần đã công bố mà khung đầy vẫn nhận lịch thứ hai';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    -- 2b. Công bố tuần của t_chua: đối soát thấy đúng khung 3 > 1, không
    --     huỷ lịch nào.
    INSERT INTO public.roster_week (clinic_id, week_start)
    VALUES (pk, date_trunc('week', (t_chua AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::date);
    IF (SELECT count(*) FROM public.khung_vuot_tran_trong_tuan(
            pk, date_trunc('week', (t_chua AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::date)
         WHERE doctor_id = bs AND bat_dau = t_chua AND tran = 1 AND da_dung = 3) <> 1 THEN
        RAISE EXCEPTION 'Đối soát lúc công bố không thấy khung vượt trần 3/1';
    END IF;
    IF (SELECT count(*) FROM public.khung_vuot_tran_trong_tuan(
            pk, date_trunc('week', (t_da AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::date)) <> 0 THEN
        RAISE EXCEPTION 'Tuần đủ trần mà đối soát báo vượt';
    END IF;
    IF (SELECT count(*) FROM public.appointment
         WHERE clinic_id = pk AND status = 'CANCELLED') <> 0 THEN
        RAISE EXCEPTION 'Đối soát không được huỷ lịch nào';
    END IF;
    -- Tuần giờ đã công bố: vãng lai bên dưới dùng khung khác, không ảnh hưởng.
    DELETE FROM public.roster_week
     WHERE clinic_id = pk
       AND week_start = date_trunc('week', (t_chua AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::date;

    -- 3. Vãng lai tuần chưa công bố: trần walkin_cap vẫn giữ.
    FOR i IN 1..2 LOOP
        INSERT INTO public.patient (clinic_id, location_id, patient_code, full_name)
        VALUES (pk, loc, 'BN-C4-VL-' || i, 'Vãng lai ' || i)
        RETURNING clinic_patient_id INTO bn;
        BEGIN
            INSERT INTO public.appointment (clinic_id, location_id, clinic_patient_id,
                service_type_id, slot_start, slot_end, status, booking_channel,
                is_walkin)
            VALUES (pk, loc, bn, sv, t_chua + interval '1 hour',
                    t_chua + interval '75 minutes', 'SCHEDULED', 'WALK_IN', TRUE);
            IF i = 2 THEN
                RAISE EXCEPTION 'Vãng lai vượt walkin_cap mà không bị chặn';
            END IF;
        EXCEPTION WHEN check_violation THEN
            IF i = 1 THEN RAISE; END IF;
        END;
    END LOOP;
END
$$;

ROLLBACK;
