-- Dữ liệu GIẢ để thử luồng khám lát 1 trên máy local.
--
-- CHẠY SAU staff_logins.sql. Thêm hai tài khoản mà fixture kia chưa có (thư ký y
-- khoa, trưởng ca) và bốn khách giả có lịch hẹn tối nay (từ 18:00) với BS A.
--
-- LOCAL/STAGING ONLY. Người giả, mật khẩu yếu dùng chung, địa chỉ @.local.
-- Không bao giờ chạy trên database có dữ liệu bệnh nhân thật.
--
-- Chạy lại bao nhiêu lần cũng được: tài khoản cập nhật tại chỗ, khách và lịch
-- chỉ tạo khi chưa có.
\set ON_ERROR_STOP on

DO $$
DECLARE
    v_clinic uuid := 'a0000000-0000-4000-8000-000000000001';
    pw       text := 'clinic-test-pw-123';
    v_loc    uuid;
    v_svc    uuid;
    v_bs     uuid;
    person   record;
    uid      uuid;
    sid      uuid;
    i        integer;
    v_pat    uuid;
    v_start  timestamptz;
    j        integer;
    v_xep    boolean;
    ten      text[] := ARRAY['Nguyễn Thị Lan', 'Trần Minh Thu', 'Lê Hồng Nhung', 'Phạm Ngọc Anh'];
BEGIN
    -- CÙNG cách chọn với staff_logins.sql (ưu tiên MAIN). Trước 15/09/2026 file
    -- này lấy cơ sở tạo sớm nhất (Kim Ngưu, 0 phòng trên local) trong khi tám tài
    -- khoản kia ở MAIN → bảng điều phối của trưởng ca rỗng, không phòng nào.
    SELECT id INTO v_loc FROM public.clinic_location
     WHERE clinic_id = v_clinic AND is_active
     ORDER BY (code = 'MAIN') DESC, code LIMIT 1;
    IF v_loc IS NULL THEN
        RAISE EXCEPTION 'chưa có cơ sở — nạp supabase/seed.sql trước';
    END IF;

    FOR person IN
        SELECT * FROM (VALUES
            ('thuky@dr4women.local',    'Thu ky local',    'TK', 'TKYK'),
            ('truongca@dr4women.local', 'Truong ca local', 'TC', 'TRUONG_CA')
        ) AS t(email, full_name, short_name, department)
    LOOP
        INSERT INTO auth.users (
            instance_id, id, aud, role, email, encrypted_password,
            email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
            confirmation_token, recovery_token, email_change_token_new,
            email_change, created_at, updated_at
        )
        VALUES (
            '00000000-0000-0000-0000-000000000000', gen_random_uuid(),
            'authenticated', 'authenticated', person.email,
            extensions.crypt(pw, extensions.gen_salt('bf')),
            now(), '{"provider": "email", "providers": ["email"]}'::jsonb,
            '{"email_verified": true}'::jsonb, '', '', '', '', now(), now()
        )
        ON CONFLICT (email) WHERE is_sso_user = false DO UPDATE SET
            encrypted_password     = EXCLUDED.encrypted_password,
            email_confirmed_at     = EXCLUDED.email_confirmed_at,
            confirmation_token     = '',
            recovery_token         = '',
            email_change_token_new = '',
            email_change           = '',
            updated_at             = now()
        RETURNING id INTO uid;

        INSERT INTO auth.identities (
            provider_id, user_id, identity_data, provider, created_at, updated_at
        )
        VALUES (
            uid::text, uid,
            jsonb_build_object('sub', uid::text, 'email', person.email,
                               'email_verified', true, 'phone_verified', false),
            'email', now(), now()
        )
        ON CONFLICT (provider_id, provider) DO UPDATE SET
            identity_data = EXCLUDED.identity_data,
            updated_at    = now();

        INSERT INTO public.staff (
            full_name, short_name, primary_department, primary_location_id,
            auth_user_id, is_active
        )
        VALUES (person.full_name, person.short_name, person.department, v_loc, uid, TRUE)
        ON CONFLICT (auth_user_id) WHERE auth_user_id IS NOT NULL DO UPDATE SET
            primary_department  = EXCLUDED.primary_department,
            primary_location_id = EXCLUDED.primary_location_id,
            full_name           = EXCLUDED.full_name,
            is_active          = TRUE
        RETURNING id INTO sid;

        DELETE FROM public.clinic_membership
         WHERE staff_id = sid AND role <> person.department;
        INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
        VALUES (v_clinic, sid, person.department, TRUE)
        ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = TRUE;
    END LOOP;

    SELECT s.id INTO v_bs
      FROM public.staff s JOIN auth.users u ON u.id = s.auth_user_id
     WHERE u.email = 'bs.a@dr4women.local';
    IF v_bs IS NULL THEN
        RAISE EXCEPTION 'chưa có bs.a@dr4women.local — chạy staff_logins.sql trước';
    END IF;

    SELECT id INTO v_svc FROM public.service_type
     WHERE clinic_id = v_clinic AND is_active ORDER BY created_at, id LIMIT 1;

    FOR i IN 1..4 LOOP
        SELECT clinic_patient_id INTO v_pat FROM public.patient
         WHERE clinic_id = v_clinic AND patient_code = 'LK-DEMO-0' || i;
        IF v_pat IS NULL THEN
            INSERT INTO public.patient
                (clinic_id, location_id, patient_code, full_name, gender, is_active)
            VALUES (v_clinic, v_loc, 'LK-DEMO-0' || i, ten[i], 'Nữ', true)
            RETURNING clinic_patient_id INTO v_pat;
        END IF;

        -- Khách đã có lịch hôm nay thì thôi: chạy lại không nhân đôi.
        IF NOT EXISTS (
            SELECT 1 FROM public.appointment
             WHERE clinic_id = v_clinic AND clinic_patient_id = v_pat
               AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
        ) THEN
            -- Từ 18:00 giờ Việt Nam, mỗi nấc 15 phút. Khung nào đã đầy (trigger
            -- enforce_slot_capacity; dữ liệu demo khác có thể đã xếp BS A vào
            -- đó) thì thử nấc sau, thay vì làm hỏng cả dev-up.
            v_xep := false;
            FOR j IN 0..15 LOOP
                v_start := ((now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                            + time '18:00' + j * interval '15 minutes')
                           AT TIME ZONE 'Asia/Ho_Chi_Minh';
                BEGIN
                    INSERT INTO public.appointment
                        (clinic_id, clinic_patient_id, location_id, service_type_id,
                         doctor_id, slot_start, slot_end, status, booking_channel,
                         is_walkin)
                    VALUES (v_clinic, v_pat, v_loc, v_svc, v_bs, v_start,
                            v_start + interval '15 minutes', 'CONFIRMED', 'ONLINE',
                            false);
                    v_xep := true;
                    EXIT;
                EXCEPTION WHEN check_violation THEN
                    NULL;
                END;
            END LOOP;
            IF NOT v_xep THEN
                RAISE EXCEPTION 'BS A không còn khung trống từ 18:00 đến 21:45 hôm nay';
            END IF;
        END IF;
    END LOOP;
END $$;

SELECT u.email, s.primary_department
  FROM public.staff s JOIN auth.users u ON u.id = s.auth_user_id
 WHERE u.email IN ('thuky@dr4women.local', 'truongca@dr4women.local')
 ORDER BY u.email;

-- Người vừa tạo phải làm được việc ngay: cấp quyền theo vai (migration
-- 20260923000016). Không có dòng này thì mọi tài khoản thử có 0 quyền.
SELECT public.cap_quyen_cho_moi_thanh_vien();
