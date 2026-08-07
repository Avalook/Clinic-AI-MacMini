-- Lịch CHƯA PHÂN BÁC SĨ không chiếm ghế của ai (migration 20260808000002).
--
-- Hai vế, và vế thứ hai mới là vế dễ mất khi ai đó "dọn dẹp" hàm trigger:
--
--   1. Nhiều lịch chưa phân bác sĩ vào CÙNG một khung → KHÔNG bị trần chặn.
--      Khách gọi đặt trước cả tháng; lúc ấy chưa ai biết bác sĩ nào trực, và
--      từ chối họ vì "khung giờ đã đầy" trong khi cả bảy bác sĩ đều trống là
--      một lỗi chỉ lộ ra khi có tải thật.
--
--   2. Lúc GÁN bác sĩ thì trần PHẢI nổ. Ràng buộc không biến mất — nó chuyển
--      sang đúng thời điểm câu hỏi "ông này khám được mấy người lúc 18:00"
--      trở thành có nghĩa. Bỏ vế này là mở cửa cho nhồi vô hạn vào một khung.
--
-- Fixture dựng TẠI CHỖ: CI chỉ chạy migration, không nạp seed. Mượn dữ liệu có
-- sẵn thì bài chạy được trên máy dev và hỏng khó hiểu trên CI.
-- Mọi thứ rollback.

BEGIN;

INSERT INTO public.clinic (id, code, name)
VALUES ('c0000000-0000-4000-8000-0000000b0001', 'TEST-HCH', 'PK kiểm thử hàng chờ');

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('c0000000-0000-4000-8000-0000000b0002',
        'c0000000-0000-4000-8000-0000000b0001', 'CS1', 'Cơ sở 1');

INSERT INTO public.service_type (id, clinic_id, code, name, is_active)
VALUES ('c0000000-0000-4000-8000-0000000b0003',
        'c0000000-0000-4000-8000-0000000b0001', 'KT', 'Dịch vụ kiểm thử', true);

INSERT INTO public.staff (id, primary_location_id, full_name, primary_department)
VALUES ('c0000000-0000-4000-8000-0000000b0004',
        'c0000000-0000-4000-8000-0000000b0002', 'BS Kiểm Thử', 'DOCTOR');

DO $$
DECLARE
    pk   uuid := 'c0000000-0000-4000-8000-0000000b0001';
    loc  uuid := 'c0000000-0000-4000-8000-0000000b0002';
    sv   uuid := 'c0000000-0000-4000-8000-0000000b0003';
    bs   uuid := 'c0000000-0000-4000-8000-0000000b0004';
    bn   uuid;
    i    int;
    n    int;
    ok   boolean;
    -- Xa trong tương lai: chốt "không đặt vào quá khứ" nằm ở tầng ứng dụng,
    -- nhưng ngày cố định sẽ hết hạn, còn ngày tương đối thì không.
    t timestamptz := (current_date + 60) + time '18:00' AT TIME ZONE 'Asia/Ho_Chi_Minh';
BEGIN
    -- Trần mặc định của phòng khám mới là regular_cap = 2 (clinic.settings
    -- DEFAULT). Năm lịch vào cùng một khung là vượt xa nó.
    FOR i IN 1..5 LOOP
        INSERT INTO public.patient (clinic_id, location_id, patient_code,
                                    full_name, gender)
        VALUES (pk, loc, 'ZZTMP-' || i, 'ZZ Tạm ' || i, 'Nữ')
        RETURNING clinic_patient_id INTO bn;

        INSERT INTO public.appointment (clinic_id, location_id, clinic_patient_id,
                                        service_type_id, slot_start, slot_end,
                                        status, booking_channel)
        VALUES (pk, loc, bn, sv, t, t + interval '15 min', 'CONFIRMED', 'HOTLINE');
    END LOOP;

    SELECT count(*) INTO n FROM public.appointment
     WHERE clinic_id = pk AND slot_start = t AND doctor_id IS NULL;
    IF n <> 5 THEN
        RAISE EXCEPTION
            'Hàng chờ bị trần số chỗ chặn: chỉ vào được % / 5. Khách gọi đặt '
            'trước cả tháng sẽ bị từ chối trong khi mọi bác sĩ đều trống.', n;
    END IF;

    ok := false;
    BEGIN
        UPDATE public.appointment SET doctor_id = bs
         WHERE clinic_id = pk AND slot_start = t AND doctor_id IS NULL;
    EXCEPTION WHEN check_violation THEN
        ok := true;
    END;
    IF NOT ok THEN
        RAISE EXCEPTION
            'Gán bác sĩ cho cả 5 lịch mà trần số chỗ không nổ — ràng buộc đã '
            'biến mất thay vì chuyển sang lúc nó có nghĩa.';
    END IF;

    RAISE NOTICE 'hang_cho_xep_bac_si: cả hai vế đều đúng.';
END $$;

ROLLBACK;
