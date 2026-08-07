-- Luật đặt lịch là CẤU HÌNH của từng phòng khám, không phải hằng số trong code
-- (migration 20260803000001, plan C.3).
--
-- Trước đây "khung 15 phút, 2 chỗ hẹn + 1 chỗ vãng lai" được viết cứng ở ba
-- nơi: trigger enforce_slot_capacity, booking_service.py, và lưới giờ ở trình
-- duyệt. Phòng khám thứ hai chạy khung 30 phút thì không dùng được sản phẩm.
--
-- File này khẳng định HÀNH VI mà lễ tân nhìn thấy — lịch nào được nhận, lịch
-- nào bị từ chối — chứ không khẳng định hình dạng SQL. Viết lại truy vấn thoải
-- mái, miễn phòng khám khung 30 phút vẫn chỉ nhận đúng 1 lịch trong 09:00–09:30.
--
-- Mọi thứ rollback.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Người đọc luôn trả đúng MỘT hàng, kể cả khi không có phòng khám nào
-- ---------------------------------------------------------------------------
-- Một trigger im lặng bỏ qua vì `SELECT ... INTO` không tìm thấy hàng nào là
-- cách tệ nhất để mất hàng rào an toàn: lịch vẫn vào, chỉ là không ai đếm nữa.

DO $reader_always_returns_one_row$
DECLARE
    n integer;
    p record;
BEGIN
    SELECT count(*) INTO n
      FROM public.clinic_booking_policy(
          '00000000-0000-4000-8000-00000000dead');
    IF n <> 1 THEN
        RAISE EXCEPTION
            'clinic_booking_policy() trả % hàng cho phòng khám không tồn tại — '
            'trigger sẽ bỏ qua việc đếm chỗ mà không báo gì', n;
    END IF;

    SELECT * INTO p
      FROM public.clinic_booking_policy(
          '00000000-0000-4000-8000-00000000dead');
    IF (p.slot_minutes, p.regular_cap, p.walkin_cap) IS DISTINCT FROM (15, 2, 1)
    THEN
        RAISE EXCEPTION
            'mặc định là %/%/%, không khớp mặc định mà clinic_policy.py và '
            'cột clinic.settings cùng khai',
            p.slot_minutes, p.regular_cap, p.walkin_cap;
    END IF;
END
$reader_always_returns_one_row$;

-- Phòng khám đang chạy phải trả lời được "khung bao nhiêu phút" bằng một câu
-- SELECT, không phải bằng cách đọc mã nguồn ba service. Migration đã backfill.
DO $existing_clinics_state_their_rule$
DECLARE
    missing integer;
BEGIN
    SELECT count(*) INTO missing
      FROM public.clinic
     WHERE NOT (settings -> 'booking'
                ?& ARRAY['slot_minutes', 'regular_cap', 'walkin_cap']);
    IF missing > 0 THEN
        RAISE EXCEPTION
            '% phòng khám chưa ghi rõ luật đặt lịch trong settings — luật của '
            'họ chỉ tồn tại dưới dạng mặc định trong code', missing;
    END IF;
END
$existing_clinics_state_their_rule$;

-- ---------------------------------------------------------------------------
-- 2. Cấu hình sai bị chặn lúc GHI, không phải 8h sáng ngày khám
-- ---------------------------------------------------------------------------

INSERT INTO public.clinic (id, code, name, settings)
VALUES ('c3000000-0000-4000-8000-0000000000c3', 'C3TEST', 'Phòng khám khung 30',
        '{"booking": {"slot_minutes": 30, "regular_cap": 1, "walkin_cap": 0}}'::jsonb);

DO $bad_configurations_are_rejected$
DECLARE
    bad jsonb;
    accepted text[] := ARRAY[]::text[];
BEGIN
    FOREACH bad IN ARRAY ARRAY[
        -- 45' không chia hết 60': bucket floor theo epoch UTC sẽ trôi khỏi
        -- ranh giới giờ VN, lưới và trigger đếm hai khung khác nhau.
        '{"booking": {"slot_minutes": 45, "regular_cap": 2, "walkin_cap": 1}}',
        -- "15" là chuỗi. jsonb nhận, ::integer nhận, và luật im lặng đúng —
        -- cho tới cái ngày ai đó ghi "mười lăm".
        '{"booking": {"slot_minutes": "15", "regular_cap": 2, "walkin_cap": 1}}',
        '{"booking": {"slot_minutes": 15.5, "regular_cap": 2, "walkin_cap": 1}}',
        -- 0 chỗ kênh thường = phòng khám không nhận đặt hẹn được nữa.
        '{"booking": {"slot_minutes": 15, "regular_cap": 0, "walkin_cap": 1}}',
        '{"booking": {"slot_minutes": 15, "regular_cap": 2, "walkin_cap": -1}}',
        '{"booking": {"slot_minutes": 0, "regular_cap": 2, "walkin_cap": 1}}',
        '{"booking": "15 phút"}'
    ]::jsonb[]
    LOOP
        BEGIN
            UPDATE public.clinic
               SET settings = bad
             WHERE id = 'c3000000-0000-4000-8000-0000000000c3';
            accepted := accepted || bad::text;
        EXCEPTION WHEN check_violation THEN
            NULL;  -- đúng như mong đợi
        END;
    END LOOP;

    IF array_length(accepted, 1) IS NOT NULL THEN
        RAISE EXCEPTION
            'clinic.settings nhận cấu hình hỏng: % — lỗi này sẽ nổ ở lượt đặt '
            'lịch đầu tiên của ngày, không phải lúc ai đó gõ sai',
            array_to_string(accepted, ' | ');
    END IF;
END
$bad_configurations_are_rejected$;

-- 0 chỗ vãng lai LÀ hợp lệ: phòng khám chỉ nhận đặt trước.
UPDATE public.clinic
   SET settings = '{"booking": {"slot_minutes": 30, "regular_cap": 1, "walkin_cap": 0}}'::jsonb
 WHERE id = 'c3000000-0000-4000-8000-0000000000c3';

-- ---------------------------------------------------------------------------
-- 3. Trigger đếm theo khung của CHÍNH phòng khám đó
-- ---------------------------------------------------------------------------

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('c3100000-0000-4000-8000-0000000000c3',
        'c3000000-0000-4000-8000-0000000000c3', 'C3', 'Cơ sở C3');

INSERT INTO public.service_type
    (id, clinic_id, code, name, default_duration_minutes)
VALUES ('c3200000-0000-4000-8000-0000000000c3',
        'c3000000-0000-4000-8000-0000000000c3', 'C3S', 'Dịch vụ C3', 30);

INSERT INTO public.patient
    (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('c3000000-0000-4000-8000-0000000000c3',
        'c3300000-0000-4000-8000-0000000000c3', 'BN-C3', 'BN cua C3',
        'c3100000-0000-4000-8000-0000000000c3');

-- BÁC SĨ LÀ BẮT BUỘC TRONG FIXTURE NÀY, kể từ 08/08/2026.
--
-- Bài này nói về ĐỘ DÀI KHUNG GIỜ (slot_minutes), và trước đây nó để trống bác
-- sĩ chỉ vì tiện. Nhưng từ migration 20260808000002, "không có bác sĩ" mang một
-- nghĩa riêng: lịch đang chờ xếp người, chưa chiếm ghế của ai, nên trần số chỗ
-- không áp. Để trống ở đây thì mọi khẳng định bên dưới đều đúng một cách rỗng —
-- không có gì bị từ chối cả, và bài canh im lặng ngừng canh.
INSERT INTO public.staff (id, primary_location_id, full_name, primary_department)
VALUES ('c3400000-0000-4000-8000-0000000000c3',
        'c3100000-0000-4000-8000-0000000000c3', 'BS cua C3', 'DOCTOR');

-- Hàm đặt lịch cho phòng khám khung 30': trả về true nếu DB nhận.
CREATE FUNCTION pg_temp.book_c3(p_time time, p_channel text DEFAULT NULL)
RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO public.appointment
        (clinic_id, clinic_patient_id, location_id, service_type_id, doctor_id,
         slot_start, slot_end, status, booking_channel)
    VALUES ('c3000000-0000-4000-8000-0000000000c3',
            'c3300000-0000-4000-8000-0000000000c3',
            'c3100000-0000-4000-8000-0000000000c3',
            'c3200000-0000-4000-8000-0000000000c3',
            'c3400000-0000-4000-8000-0000000000c3',
            ((CURRENT_DATE + 30)::timestamp + p_time) AT TIME ZONE 'Asia/Ho_Chi_Minh',
            ((CURRENT_DATE + 30)::timestamp + p_time + interval '30 min')
                AT TIME ZONE 'Asia/Ho_Chi_Minh',
            'SCHEDULED', p_channel);
    RETURN true;
EXCEPTION WHEN sqlstate '23514' THEN
    RETURN false;
END;
$$;

DO $thirty_minute_clinic_gets_thirty_minute_buckets$
BEGIN
    -- 09:00 nhận (chỗ hẹn duy nhất của khung).
    IF NOT pg_temp.book_c3(time '09:00') THEN
        RAISE EXCEPTION 'lịch đầu tiên của khung 09:00–09:30 bị từ chối';
    END IF;

    -- 09:15 nằm CÙNG khung 30' → phải bị từ chối. Đây chính là chỗ luật cũ
    -- sai: với bucket 15' cứng, 09:15 là một khung khác và lịch này lọt.
    IF pg_temp.book_c3(time '09:15') THEN
        RAISE EXCEPTION
            '09:15 lọt qua — trigger vẫn đang chia khung 15 phút thay vì đọc '
            'slot_minutes của phòng khám';
    END IF;

    -- 09:30 mở khung mới → nhận.
    IF NOT pg_temp.book_c3(time '09:30') THEN
        RAISE EXCEPTION 'khung 09:30–10:00 phải là khung mới, còn trống';
    END IF;
END
$thirty_minute_clinic_gets_thirty_minute_buckets$;

-- walkin_cap = 0 nghĩa là KHÔNG nhận khách vãng lai, không phải "mặc định 1".
DO $zero_walkin_cap_means_zero$
BEGIN
    IF pg_temp.book_c3(time '11:00', 'WALK_IN') THEN
        RAISE EXCEPTION
            'phòng khám khai walkin_cap = 0 vẫn nhận khách vãng lai — số 0 bị '
            'coi là "chưa cấu hình" ở đâu đó';
    END IF;
END
$zero_walkin_cap_means_zero$;

-- ---------------------------------------------------------------------------
-- 4. Đổi luật = một lần ghi JSONB, KHÔNG deploy lại
-- ---------------------------------------------------------------------------
-- Tiêu chí ra của C.3 trong plan. Nếu bước này cần build lại image thì phòng
-- khám thứ 20 vẫn là một lần sửa code.

UPDATE public.clinic
   SET settings = jsonb_set(settings, '{booking,regular_cap}', to_jsonb(2))
 WHERE id = 'c3000000-0000-4000-8000-0000000000c3';

DO $raising_the_cap_takes_effect_immediately$
BEGIN
    IF NOT pg_temp.book_c3(time '09:15') THEN
        RAISE EXCEPTION
            'nâng regular_cap lên 2 rồi mà lịch thứ hai của khung vẫn bị từ '
            'chối — luật vẫn nằm ở đâu đó ngoài clinic.settings';
    END IF;
END
$raising_the_cap_takes_effect_immediately$;

-- ---------------------------------------------------------------------------
-- 5. Phòng khám mặc định KHÔNG bị ảnh hưởng bởi cấu hình của phòng khám khác
-- ---------------------------------------------------------------------------

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('c3110000-0000-4000-8000-0000000000a1',
        'a0000000-0000-4000-8000-000000000001', 'C3-A', 'Cơ sở A (C3 test)')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.service_type
    (id, clinic_id, code, name, default_duration_minutes)
VALUES ('c3210000-0000-4000-8000-0000000000a1',
        'a0000000-0000-4000-8000-000000000001', 'C3-AS', 'Dịch vụ A (C3 test)', 15)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.patient
    (clinic_id, clinic_patient_id, patient_code, full_name, location_id)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'c3310000-0000-4000-8000-0000000000a1', 'BN-C3-A', 'BN cua A (C3)',
        'c3110000-0000-4000-8000-0000000000a1')
ON CONFLICT (clinic_patient_id) DO NOTHING;

-- Bác sĩ bắt buộc, cùng lý do như fixture C3 ở trên: từ 20260808000002, lịch
-- không có bác sĩ là lịch ĐANG CHỜ XẾP và được miễn trần số chỗ.
INSERT INTO public.staff (id, primary_location_id, full_name, primary_department)
VALUES ('c3410000-0000-4000-8000-0000000000a1',
        'c3110000-0000-4000-8000-0000000000a1', 'BS cua A (C3)', 'DOCTOR')
ON CONFLICT (id) DO NOTHING;

CREATE FUNCTION pg_temp.book_a(p_time time, p_channel text DEFAULT NULL)
RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    -- `is_walkin` PHẢI đặt cùng `booking_channel`.
    --
    -- CHECK `appointment_walkin_channel_agree` đòi hai cột này khớp nhau, và
    -- `is_walkin` mặc định false. Bỏ trống thì dòng WALK_IN bị từ chối vì SAI
    -- RÀNG BUỘC — mà mã lỗi cũng là 23514, y hệt "hết chỗ". Khối EXCEPTION bên
    -- dưới nuốt cả hai, nên test báo "chỗ vãng lai bị chỗ hẹn ăn mất" trong khi
    -- luật sức chứa hoàn toàn đúng. Một bài test chỉ bắt mã lỗi mà không phân
    -- biệt nguyên nhân sẽ chỉ sai chỗ như vậy.
    INSERT INTO public.appointment
        (clinic_id, clinic_patient_id, location_id, service_type_id, doctor_id,
         slot_start, slot_end, status, booking_channel, is_walkin)
    VALUES ('a0000000-0000-4000-8000-000000000001',
            'c3310000-0000-4000-8000-0000000000a1',
            'c3110000-0000-4000-8000-0000000000a1',
            'c3210000-0000-4000-8000-0000000000a1',
            'c3410000-0000-4000-8000-0000000000a1',
            ((CURRENT_DATE + 31)::timestamp + p_time) AT TIME ZONE 'Asia/Ho_Chi_Minh',
            ((CURRENT_DATE + 31)::timestamp + p_time + interval '15 min')
                AT TIME ZONE 'Asia/Ho_Chi_Minh',
            'SCHEDULED', p_channel,
            upper(coalesce(p_channel, '')) = 'WALK_IN');
    RETURN true;
EXCEPTION WHEN sqlstate '23514' THEN
    -- Chỉ nuốt lỗi ĐÚNG của luật sức chứa. Mọi check_violation khác là hỏng
    -- thật và phải nổ ra, thay vì bị đọc nhầm thành "khung đã đầy".
    IF sqlerrm NOT ILIKE '%khung%' AND sqlerrm NOT ILIKE '%đầy%'
       AND sqlerrm NOT ILIKE '%chỗ%' THEN
        RAISE;
    END IF;
    RETURN false;
END;
$$;

DO $default_clinic_still_runs_two_plus_one$
BEGIN
    IF NOT pg_temp.book_a(time '14:00') THEN
        RAISE EXCEPTION 'chỗ hẹn thứ nhất của khung 14:00 bị từ chối';
    END IF;
    IF NOT pg_temp.book_a(time '14:05') THEN
        RAISE EXCEPTION 'chỗ hẹn thứ hai của khung 14:00–14:15 bị từ chối';
    END IF;
    IF pg_temp.book_a(time '14:10') THEN
        RAISE EXCEPTION
            'khung 14:00–14:15 nhận chỗ hẹn thứ ba — phòng khám mặc định không '
            'còn chạy luật của chính nó';
    END IF;

    -- Chỗ vãng lai là một hồ RIÊNG: khung đã kín chỗ hẹn vẫn còn 1 chỗ ưu tiên.
    IF NOT pg_temp.book_a(time '14:10', 'WALK_IN') THEN
        RAISE EXCEPTION
            'chỗ vãng lai bị chỗ hẹn ăn mất — hai loại chỗ phải đếm riêng';
    END IF;
    IF pg_temp.book_a(time '14:12', 'WALK_IN') THEN
        RAISE EXCEPTION 'khung nhận khách vãng lai thứ hai dù walkin_cap = 1';
    END IF;
END
$default_clinic_still_runs_two_plus_one$;

ROLLBACK;
