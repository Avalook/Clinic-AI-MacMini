-- Tài khoản CHỈ XEM kho thuốc để bấm thử vai không có quyền ghi (17/10/2026) — LOCAL ONLY.
--
-- Vì sao cần: mọi tài khoản mẫu có `pharmacy.view` đều có luôn `pharmacy.dispense` (hai khối
-- `xem_nha_thuoc` và `nha_thuoc` được cấp chung), nên không bấm thử được "người chỉ xem thấy gì,
-- lệnh ghi bị chặn ra sao" (màn Thuốc trả chờ kiểm, nhập lô…). Tài khoản này được cấp ĐÚNG khối
-- `xem_nha_thuoc`: xem được kho, mọi nút ghi ẩn, lệnh ghi trả 403.
--
--   email: kt.chixem@dr4women.local · mật khẩu: clinic-test-pw-123 (như mọi tài khoản mẫu local)
--
-- Chạy lại được: tạo hoặc đặt lại đúng người này, không đụng ai khác.
--   psql "$DB" -f supabase/fixtures/tai_khoan_chi_xem_kho.sql
-- Thu ngân CÓ CA hôm nay (để bấm Tạo bill không phải vai quản lý): dùng `danang@dr4women.local`
-- (lịch trực thử T1_THUNGAN, fixture tai_khoan_da_vai_hom_nay.sql).
-- Không chạy trên database có dữ liệu khách thật.

\set ON_ERROR_STOP on

DO $$
DECLARE
    v_clinic uuid := 'a0000000-0000-4000-8000-000000000001';
    v_email  text := 'kt.chixem@dr4women.local';
    pw       text := 'clinic-test-pw-123';
    uid      uuid;
    sid      uuid;
    v_loc    uuid;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.clinic WHERE id = v_clinic) THEN
        RAISE EXCEPTION 'clinic % missing — apply the migrations first', v_clinic;
    END IF;
    SELECT id INTO v_loc FROM public.clinic_location
     WHERE clinic_id = v_clinic AND is_active
     ORDER BY (code = 'MAIN') DESC, code LIMIT 1;
    IF v_loc IS NULL THEN
        RAISE EXCEPTION 'clinic % has no active location — apply supabase/seed.sql first', v_clinic;
    END IF;

    -- Đúng cách staff_logins.sql: bốn cột token phải là '' (không NULL), và phải có
    -- auth.identities thì GoTrue mới cho đăng nhập bằng mật khẩu.
    INSERT INTO auth.users (
        instance_id, id, aud, role, email, encrypted_password,
        email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
        confirmation_token, recovery_token, email_change_token_new,
        email_change, created_at, updated_at
    )
    VALUES (
        '00000000-0000-0000-0000-000000000000', gen_random_uuid(),
        'authenticated', 'authenticated', v_email,
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
        jsonb_build_object('sub', uid::text, 'email', v_email,
                           'email_verified', true, 'phone_verified', false),
        'email', now(), now()
    )
    ON CONFLICT (provider_id, provider) DO UPDATE SET
        identity_data = EXCLUDED.identity_data, updated_at = now();

    INSERT INTO public.staff (
        full_name, short_name, primary_department, primary_location_id,
        auth_user_id, is_active
    )
    VALUES ('KT chi xem kho', 'KT', 'PHARMACIST', v_loc, uid, TRUE)
    ON CONFLICT (auth_user_id) WHERE auth_user_id IS NOT NULL DO UPDATE SET
        full_name = EXCLUDED.full_name, is_active = TRUE
    RETURNING id INTO sid;

    DELETE FROM public.clinic_membership WHERE staff_id = sid AND role <> 'PHARMACIST';
    INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
    VALUES (v_clinic, sid, 'PHARMACIST', TRUE)
    ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = TRUE;

    -- Quyền THẬT của một người là `capability_grant` (vai chỉ là preset cấp nhanh): bỏ mọi
    -- quyền cũ của đúng người này rồi cấp ĐÚNG khối xem kho.
    DELETE FROM public.capability_grant WHERE clinic_id = v_clinic AND staff_id = sid;
    INSERT INTO public.capability_grant (clinic_id, staff_id, capability, scope_type, tu_khoi, ly_do)
    SELECT v_clinic, sid, c.ma, 'CLINIC', 'xem_nha_thuoc', 'Tài khoản thử chỉ-xem kho (fixture)'
      FROM public.capability c
     WHERE c.work_pack = 'xem_nha_thuoc';
END $$;
