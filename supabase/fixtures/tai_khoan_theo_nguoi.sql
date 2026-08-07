-- Mỗi nhân sự MỘT tài khoản, tên đăng nhập đọc ra là biết ai:
-- <chức vụ><tên>@dr4women.vn — bacsithanh, letanthu, dieuduonghavu…
--
-- Trước file này phòng khám dùng chung 8 tài khoản chức danh (bs.a@, letan@…)
-- trên miền .local. Dùng chung nghĩa là sổ sự kiện ghi "lễ tân đã sửa" chứ
-- không ghi được AI đã sửa — mà đó chính là thứ một hồ sơ bệnh án cần.
--
-- KHỚP THEO full_name. Tên bác sĩ vừa đổi sang dạng đầy đủ nên nó đã phân biệt
-- được từng người; short_name thì có cặp trùng nhau giữa các bộ phận ("Hằng" là
-- bác sĩ, "Hằng LT" là lễ tân) nên không dùng làm khoá ở đây.
--
-- IDEMPOTENT. Người đã có tài khoản thì chỉ ĐỔI email sang tên mới, không tạo
-- thêm — tạo thêm là người đó có hai đường vào và sổ sự kiện tách làm đôi.
--
--   psql -v mat_khau=12345678 -f tai_khoan_theo_nguoi.sql

\set ON_ERROR_STOP on

-- psql KHÔNG thay biến `:mat_khau` bên trong khối $$…$$ — nó coi cả khối là một
-- chuỗi. Nên đưa mật khẩu vào qua set_config rồi đọc lại bằng current_setting.
-- `:'mat_khau'` TỰ THÊM nháy đơn. Truyền vào -v mat_khau=12345678 (KHÔNG kèm
-- nháy) — kèm nháy là mật khẩu thật thành «'12345678'» và không ai đăng nhập
-- được, mà lỗi trả về vẫn chỉ là "Invalid login credentials".
-- SELECT ... FROM set_config(...) để không in mật khẩu ra màn hình.
SELECT '' AS dat_mat_khau FROM set_config('app.mat_khau', :'mat_khau', false);

DO $$
DECLARE
    v_clinic uuid;
    pw       text := current_setting('app.mat_khau');
    ng       record;
    uid      uuid;
    sid      uuid;
    v_moi    int := 0;
    v_doi    int := 0;
BEGIN
    SELECT id INTO v_clinic FROM public.clinic ORDER BY created_at LIMIT 1;

    FOR ng IN
        SELECT * FROM (VALUES
            ('BS Đào', 'bacsidao@dr4women.vn'),
            ('Ths.BS. Phan Thu Hằng', 'bacsihang@dr4women.vn'),
            ('BSNT. Vũ Trọng Hùng', 'bacsihung@dr4women.vn'),
            ('BSNT. Nguyễn Khánh Linh', 'bacsilinh@dr4women.vn'),
            ('BSNT. Nguyễn Phương Nam', 'bacsinam@dr4women.vn'),
            ('BS. Phạm Văn Nghị', 'bacsinghi@dr4women.vn'),
            ('BSNT. Lê Thiệu Quyết', 'bacsiquyet@dr4women.vn'),
            ('Ths. Đào Bá Linh', 'bacsisieuambalinh@dr4women.vn'),
            ('BS. Nguyễn Thành Đạt', 'bacsisieuamdat@dr4women.vn'),
            ('BSNT. Nguyễn Hữu Giáp', 'bacsisieuamgiap@dr4women.vn'),
            ('Ths. Nguyễn Mạnh Minh Hoàng', 'bacsisieuamhoang@dr4women.vn'),
            ('BS. Phạm Ngọc Minh', 'bacsisieuamminh@dr4women.vn'),
            ('BS. Nguyễn Trung Tiến', 'bacsisieuamtien@dr4women.vn'),
            ('TS.BS. Phan Chí Thành', 'bacsithanh@dr4women.vn'),
            ('BSNT. Hoàng Đình Thiệp', 'bacsithiep@dr4women.vn'),
            ('ĐD Diễm Thúy', 'dieuduongdiemthuy@dr4women.vn'),
            ('ĐD Dương Trang', 'dieuduongduongtrang@dr4women.vn'),
            ('ĐD Hà Vũ', 'dieuduonghavu@dr4women.vn'),
            ('ĐD Hương Linh', 'dieuduonghuonglinh@dr4women.vn'),
            ('Kim Tiến', 'dieuduongkimtien@dr4women.vn'),
            ('ĐD Thanh Hải', 'dieuduongthanhhai@dr4women.vn'),
            ('ĐD Trang Lê', 'dieuduongtrangle@dr4women.vn'),
            ('ĐD Giầu', 'letangiau@dr4women.vn'),
            ('Hải Yến', 'letanhaiyen@dr4women.vn'),
            ('ĐD Hằng', 'letanhang@dr4women.vn'),
            ('ĐD Hà Phạm', 'letanhapham@dr4women.vn'),
            ('ĐD Phương Anh', 'letanphuonganh@dr4women.vn'),
            ('Quỳnh Anh', 'letanquynhanh@dr4women.vn'),
            ('ĐD Thanh An', 'letanthanhan@dr4women.vn'),
            ('ĐD Thư', 'letanthu@dr4women.vn'),
            ('ĐD Thủy Tiên', 'letanthuytien@dr4women.vn'),
            ('Màn hình phòng chờ', 'manhinhphongcho@dr4women.vn'),
            ('TL Duy Nam', 'thukyduynam@dr4women.vn'),
            ('ĐD Huế', 'thukyhue@dr4women.vn'),
            ('TL Thanh Phương', 'thukythanhphuong@dr4women.vn'),
            ('TL Vân Anh', 'thukyvananh@dr4women.vn')
        ) AS t(ten, email)
    LOOP
        SELECT id, auth_user_id INTO sid, uid
          FROM public.staff
         WHERE full_name = ng.ten AND is_active;

        IF sid IS NULL THEN
            RAISE NOTICE 'Bỏ qua: không có nhân sự tên "%"', ng.ten;
            CONTINUE;
        END IF;

        IF uid IS NOT NULL THEN
            -- Đã có đường vào: chỉ đổi tên đăng nhập cho dễ đọc.
            UPDATE auth.users
               SET email = ng.email, updated_at = now()
             WHERE id = uid AND email IS DISTINCT FROM ng.email;
            UPDATE auth.identities
               SET identity_data = identity_data
                     || jsonb_build_object('email', ng.email),
                   updated_at = now()
             WHERE user_id = uid;
            v_doi := v_doi + 1;
        ELSE
            -- Bốn cột token phải là CHUỖI RỖNG chứ không NULL: GoTrue đọc chúng
            -- vào kiểu chuỗi không-null, NULL biến mọi lần đăng nhập thành
            -- "Database error querying schema" — trông như database hỏng.
            INSERT INTO auth.users (
                instance_id, id, aud, role, email, encrypted_password,
                email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                confirmation_token, recovery_token, email_change_token_new,
                email_change, created_at, updated_at
            ) VALUES (
                '00000000-0000-0000-0000-000000000000', gen_random_uuid(),
                'authenticated', 'authenticated', ng.email,
                extensions.crypt(pw, extensions.gen_salt('bf')),
                now(), '{"provider": "email", "providers": ["email"]}'::jsonb,
                '{"email_verified": true}'::jsonb, '', '', '', '', now(), now()
            )
            ON CONFLICT (email) WHERE is_sso_user = false DO UPDATE
                SET updated_at = now()
            RETURNING id INTO uid;

            -- GoTrue KHÔNG tra người dùng thẳng từ auth.users khi đăng nhập
            -- bằng mật khẩu — nó đi qua auth.identities. Thiếu dòng này là mọi
            -- lần đăng nhập trả invalid_credentials, y như gõ sai mật khẩu.
            INSERT INTO auth.identities (
                provider_id, user_id, identity_data, provider, created_at, updated_at
            ) VALUES (
                uid::text, uid,
                jsonb_build_object('sub', uid::text, 'email', ng.email,
                                   'email_verified', true, 'phone_verified', false),
                'email', now(), now()
            )
            ON CONFLICT (provider_id, provider) DO UPDATE
                SET identity_data = EXCLUDED.identity_data, updated_at = now();

            UPDATE public.staff SET auth_user_id = uid, updated_at = now()
             WHERE id = sid;
            v_moi := v_moi + 1;
        END IF;

        -- Vai trong phòng khám phải khớp bộ phận, nếu không backend đọc ra một
        -- quyền và giao diện đọc ra quyền khác.
        INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
        SELECT v_clinic, sid, s.primary_department, TRUE
          FROM public.staff s WHERE s.id = sid
        ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = TRUE;
    END LOOP;

    RAISE NOTICE 'Tạo mới % tài khoản, đổi tên % tài khoản.', v_moi, v_doi;
END $$;
