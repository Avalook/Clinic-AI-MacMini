-- Một ngày làm việc giả lập, đủ đông để nhìn ra vấn đề.
--
-- Fixture cũ có ĐÚNG MỘT bệnh nhân, nên mọi bảng đều là năm dòng "BN của
-- Dr4Women" giống hệt nhau. Không phân biệt được dòng nào với dòng nào thì
-- không test được thứ tự gọi, không thấy được hàng đợi dài trông ra sao, và
-- không ai phát hiện nổi một dòng bị lặp hay biến mất.
--
-- Dữ liệu ở đây là GIẢ HOÀN TOÀN: tên phổ biến, số điện thoại 09xx dải test,
-- không có số nào thật. Chỉ nạp vào database local hoặc staging.
--
--   psql "$LOCAL" -f supabase/fixtures/demo_clinic_day.sql
--
-- Chạy lại được: xoá sạch dữ liệu demo cũ (nhận diện bằng tiền tố mã BN) rồi
-- tạo lại, nên không đắp chồng qua mỗi lần chạy.

\set ON_ERROR_STOP on

DO $demo$
DECLARE
    v_clinic  uuid := 'a0000000-0000-4000-8000-000000000001';
    v_loc     uuid;
    v_svc     uuid;
    v_bs_a    uuid;
    v_bs_sa   uuid;
    v_letan   uuid;
    v_dd      uuid;
    v_pat     uuid;
    v_appt    uuid;
    v_visit   uuid;
    v_wi      uuid;
    i         integer;
    n_pat     constant integer := 40;
    n_today   constant integer := 26;
    ho        text[] := ARRAY['Nguyễn','Trần','Lê','Phạm','Hoàng','Vũ','Đặng','Bùi','Đỗ','Ngô'];
    dem       text[] := ARRAY['Thị','Thuý','Ngọc','Minh','Thanh','Kim','Phương','Hồng'];
    ten       text[] := ARRAY['Anh','Bình','Chi','Dung','Giang','Hà','Hằng','Hoa','Lan','Linh',
                              'Mai','Nga','Ngân','Nhung','Oanh','Quyên','Thảo','Trang','Tuyết','Yến'];
BEGIN
    SELECT id INTO v_loc  FROM clinic_location WHERE clinic_id=v_clinic AND is_active ORDER BY code LIMIT 1;
    SELECT id INTO v_svc  FROM service_type    WHERE clinic_id=v_clinic AND is_active ORDER BY code LIMIT 1;
    SELECT id INTO v_bs_a FROM staff WHERE full_name='BS A local';
    SELECT id INTO v_bs_sa FROM staff WHERE full_name='BS SA local';
    SELECT id INTO v_letan FROM staff WHERE full_name='Le tan local';
    SELECT id INTO v_dd   FROM staff WHERE full_name='DD SA local';

    IF v_loc IS NULL OR v_svc IS NULL OR v_letan IS NULL THEN
        RAISE EXCEPTION 'thiếu fixture nền — chạy staff_logins.sql và local_data.sql trước';
    END IF;

    -- Dọn lần chạy trước. Thứ tự theo phụ thuộc, và chỉ đụng dữ liệu demo.
    DELETE FROM work_item_event WHERE work_item_id IN (
        SELECT w.id FROM work_item w JOIN patient p ON p.clinic_patient_id=w.clinic_patient_id
         WHERE p.patient_code LIKE 'DEMO-%');
    DELETE FROM work_item      WHERE clinic_patient_id IN (SELECT clinic_patient_id FROM patient WHERE patient_code LIKE 'DEMO-%');
    DELETE FROM visit          WHERE clinic_patient_id IN (SELECT clinic_patient_id FROM patient WHERE patient_code LIKE 'DEMO-%');
    DELETE FROM appointment    WHERE clinic_patient_id IN (SELECT clinic_patient_id FROM patient WHERE patient_code LIKE 'DEMO-%');
    DELETE FROM patient        WHERE patient_code LIKE 'DEMO-%';

    -- ---- 40 bệnh nhân, tên khác nhau, tuổi khác nhau ----------------------
    FOR i IN 1..n_pat LOOP
        INSERT INTO patient (
            clinic_id, location_id, patient_code, full_name, date_of_birth,
            gender, phone_primary, is_active
        )
        VALUES (
            v_clinic, v_loc,
            'DEMO-' || lpad(i::text, 3, '0'),
            ho[1 + (i * 7) % array_length(ho,1)] || ' ' ||
            dem[1 + (i * 3) % array_length(dem,1)] || ' ' ||
            ten[1 + (i * 11) % array_length(ten,1)],
            -- 18 đến 52 tuổi, rải đều
            (current_date - ((18 + (i * 13) % 35) * 365 + (i * 7) % 365) * interval '1 day')::date,
            'Nữ',
            '09' || lpad(((i * 1237) % 100000000)::text, 8, '0'),
            TRUE
        );
    END LOOP;

    -- ---- lịch hẹn hôm nay, rải từ 07:30 đến 16:30 -------------------------
    i := 0;
    FOR v_pat IN
        SELECT clinic_patient_id FROM patient
         WHERE patient_code LIKE 'DEMO-%' ORDER BY patient_code LIMIT n_today
    LOOP
        i := i + 1;
        v_appt := gen_random_uuid();

        INSERT INTO appointment (
            id, clinic_id, clinic_patient_id, location_id, service_type_id,
            doctor_id, slot_start, slot_end, status, booking_channel,
            is_priority_slot
        )
        VALUES (
            v_appt, v_clinic, v_pat, v_loc, v_svc,
            CASE WHEN i % 3 = 0 THEN v_bs_sa ELSE v_bs_a END,
            date_trunc('day', now()) + interval '7 hours 30 minutes' + ((i - 1) * interval '20 minutes'),
            date_trunc('day', now()) + interval '7 hours 50 minutes' + ((i - 1) * interval '20 minutes'),
            -- 18 người đã đến, 8 người còn chờ giờ hẹn
            CASE WHEN i <= 18 THEN 'CHECKED_IN' ELSE 'CONFIRMED' END,
            CASE WHEN i % 5 = 0 THEN 'WALK_IN' ELSE 'ONLINE' END,
            (i % 9 = 0)                        -- vài ca ưu tiên
        );

        CONTINUE WHEN i > 18;                  -- chưa đến thì chưa mở lượt khám

        INSERT INTO visit (clinic_id, clinic_patient_id, appointment_id,
                           attending_doctor_id, status, checked_in_at, checked_in_by)
        VALUES (v_clinic, v_pat, v_appt,
                CASE WHEN i % 3 = 0 THEN v_bs_sa ELSE v_bs_a END,
                'OPEN',
                now() - ((30 - i) * interval '4 minutes'),
                v_letan)
        RETURNING visit_id INTO v_visit;

        PERFORM public.instantiate_visit_workflow(v_clinic, v_visit, v_letan, 'RECEPTION');

        -- ---- đẩy từng lượt tới các giai đoạn khác nhau --------------------
        -- Không thì cả 18 người đứng cùng một chỗ và bảng nào cũng chỉ có một
        -- trạng thái duy nhất — đúng cái làm fixture cũ vô dụng.

        -- 12 người đã qua xác minh
        IF i <= 12 THEN
            SELECT id INTO v_wi FROM work_item
             WHERE visit_id=v_visit AND node_code='LUOTKHAM-02' AND status<>'CANCELLED';
            UPDATE work_item SET status='COMPLETED', started_at=now(), finished_at=now(),
                   version=version+1 WHERE id=v_wi;
            INSERT INTO work_item_event (clinic_id, work_item_id, command, to_status,
                                         actor_staff_id, actor_role)
            VALUES (v_clinic, v_wi, 'complete', 'COMPLETED', v_letan, 'RECEPTION');
        END IF;

        -- 7 người đã đo sinh hiệu → bác sĩ khám được
        IF i <= 7 THEN
            SELECT id INTO v_wi FROM work_item
             WHERE visit_id=v_visit AND node_code='LUOTKHAM-03' AND status<>'CANCELLED';
            UPDATE work_item SET status='COMPLETED', started_at=now(), finished_at=now(),
                   version=version+1 WHERE id=v_wi;
            INSERT INTO work_item_event (clinic_id, work_item_id, command, to_status,
                                         actor_staff_id, actor_role)
            VALUES (v_clinic, v_wi, 'complete', 'COMPLETED', v_dd, 'NURSE_ULTRASOUND');
        END IF;

        -- 3 người bác sĩ đang khám dở
        IF i <= 3 THEN
            SELECT id INTO v_wi FROM work_item
             WHERE visit_id=v_visit AND node_code='LUOTKHAM-05' AND status<>'CANCELLED';
            UPDATE work_item SET status='IN_PROGRESS', started_at=now(),
                   version=version+1 WHERE id=v_wi;
            INSERT INTO work_item_event (clinic_id, work_item_id, command, to_status,
                                         actor_staff_id, actor_role)
            VALUES (v_clinic, v_wi, 'start', 'IN_PROGRESS', v_bs_a, 'DOCTOR');
        END IF;

        -- 2 người đã có chỉ định dịch vụ → phòng siêu âm / lấy máu có việc
        IF i <= 2 THEN
            PERFORM public.order_services(
                v_clinic, v_visit,
                ARRAY['CLS_SIEU_AM_O_BUNG','CLS_SIEU_AM_VU','CLS_XET_NGHIEM_MAU'],
                v_bs_a, 'DOCTOR');
        END IF;
    END LOOP;

    RAISE NOTICE 'demo: % bệnh nhân, % lịch hôm nay, % việc đang mở',
        n_pat, n_today,
        (SELECT count(*) FROM work_item WHERE status IN ('PENDING','IN_PROGRESS'));
END
$demo$;
