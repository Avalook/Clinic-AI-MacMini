-- Staff logins for the local end-to-end scripts (ADR-0009 identity model).
--
-- One Supabase login per staff member: auth.users → staff.auth_user_id →
-- clinic_membership. Both the dashboard (departmentToRole) and the backend
-- (identity.py) read the role from the same staff row, so a fixture with the
-- wrong department fails the same way in both.
--
-- The e2e scripts used to depend on two accounts created by hand on this Mac,
-- which meant nobody else could run them and a `db reset` silently deleted the
-- prerequisite. This file is idempotent — run it as often as you like:
--   psql "$DB" -f supabase/fixtures/staff_logins.sql
--
-- LOCAL/STAGING ONLY. Fake people, one shared weak password, fake @.local
-- addresses. Never run against a database holding real patient data.

\set ON_ERROR_STOP on

DO $$
DECLARE
    v_clinic uuid := 'a0000000-0000-4000-8000-000000000001';
    pw      text := 'clinic-test-pw-123';
    person  record;
    uid     uuid;
    sid     uuid;
    -- Cơ sở mặc định cho tài khoản thử.
    --
    -- VÌ SAO PHẢI CÓ. Không gán thì get_current_identity từ chối MỌI request
    -- bằng 403 "Tài khoản chưa được gán cơ sở khám" (identity.py:365) — nghĩa
    -- là dev-up.sh dựng xong cả stack, đăng nhập được, rồi mọi màn hình đều
    -- trống. Bước kiểm cuối của dev-up in ra "answers with err item(s)" đúng vì
    -- chuyện này. Cột này nullable nên INSERT không hề báo lỗi; nó chỉ hỏng ở
    -- tầng trên, một tầng mà fixture không chạm tới.
    v_loc   uuid;
BEGIN
    SELECT id INTO v_loc
      FROM public.clinic_location
     WHERE clinic_id = v_clinic AND is_active
     ORDER BY created_at, id
     LIMIT 1;
    IF v_loc IS NULL THEN
        RAISE EXCEPTION
            'clinic % chưa có cơ sở nào — nạp migration/seed trước', v_clinic;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.clinic WHERE id = v_clinic) THEN
        RAISE EXCEPTION 'clinic % missing — apply the migrations first', v_clinic;
    END IF;

    FOR person IN
        SELECT * FROM (VALUES
            ('bs.a@dr4women.local',     'BS A local',    'BS A',  'DOCTOR'),
            ('cskh@dr4women.local',     'CSKH local',    'CSKH',  'CSKH'),
            ('letan@dr4women.local',    'Le tan local',  'LT',    'RECEPTION'),
            ('bs.sa@dr4women.local',    'BS SA local',   'BS SA', 'ULTRASOUND_DOCTOR'),
            ('dd.sa@dr4women.local',    'DD SA local',   'DD SA', 'NURSE_ULTRASOUND'),
            ('thungan@dr4women.local',  'Thu ngan local','TN',    'CASHIER'),
            ('duocsi@dr4women.local',   'Duoc si local', 'DS',    'PHARMACIST'),
            ('ql@dr4women.local',       'Quan ly local', 'QL',    'MANAGEMENT')
            -- Cổng phòng khám. CỐ Ý không gắn với dòng staff nào: /enter đăng
            -- nhập bằng tài khoản này để qua cổng, rồi proxy thấy chưa có
            -- staff_id nên đẩy tiếp sang /login để hỏi "bạn là ai". Nếu gắn nó
            -- vào một nhân viên thì mọi người qua cổng đều thành nhân viên đó.
            ,('clinic@dr4women.local',  NULL,            NULL,    NULL)
        ) AS t(email, full_name, short_name, department)
    LOOP
        -- crypt() lives in the extensions schema on Supabase; auth.users is
        -- written directly because GoTrue's admin API needs a running server
        -- and this has to work from psql alone.
        -- The four token columns must be '' and not NULL. GoTrue reads them
        -- into non-nullable strings, so a NULL turns every login into
        -- "Database error querying schema" — which looks like a broken database
        -- rather than a malformed fixture row.
        -- Tài khoản cổng chỉ cần auth.users, không cần staff.
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

        -- Tài khoản cổng dừng ở đây: nó chỉ để qua /enter, không phải một
        -- con người. Không có dòng staff nào → proxy đẩy tiếp sang /login.
        IF person.full_name IS NULL THEN
            CONTINUE;
        END IF;

        -- staff itself carries no clinic_id: who someone works for lives in
        -- clinic_membership, so one person can be lent to a second clinic
        -- without duplicating their record (ADR-0009).
        INSERT INTO public.staff (
            full_name, short_name, primary_department, auth_user_id, is_active,
            primary_location_id
        )
        VALUES (
            person.full_name, person.short_name, person.department, uid, TRUE,
            v_loc
        )
        ON CONFLICT (auth_user_id) WHERE auth_user_id IS NOT NULL DO UPDATE SET
            primary_department  = EXCLUDED.primary_department,
            full_name           = EXCLUDED.full_name,
            is_active           = TRUE,
            -- Vá cả những hàng đã tạo trước khi fixture biết gán cơ sở.
            primary_location_id = COALESCE(
                public.staff.primary_location_id, EXCLUDED.primary_location_id
            )
        RETURNING id INTO sid;

        -- uq_clinic_membership is (clinic_id, staff_id, role), so a role change
        -- would add a second membership rather than move the person. Clear the
        -- others first: one active tenant role per fixture staff member.
        DELETE FROM public.clinic_membership
         WHERE staff_id = sid AND role <> person.department;

        INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
        VALUES (v_clinic, sid, person.department, TRUE)
        ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = TRUE;
    END LOOP;
END $$;

SELECT u.email, s.primary_department, m.role, s.is_active
  FROM public.staff s
  JOIN auth.users u ON u.id = s.auth_user_id
  JOIN public.clinic_membership m ON m.staff_id = s.id
 WHERE u.email LIKE '%@dr4women.local'
 ORDER BY 1;
