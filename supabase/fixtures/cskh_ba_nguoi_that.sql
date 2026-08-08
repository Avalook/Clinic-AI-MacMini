-- BA NGƯỜI CSKH THẬT, VÀ TÊN AI CŨNG ĐỌC RA CHỨC VỤ.
--
-- Quang chốt 09/08/2026, nguồn là Notion "[Master page] Nhân viên CSKH-Mar"
-- (lib 3 - danh sách nhân viên): ban CSKH có Diệu Hoa, Huyền Diệu, Kim Tiến —
-- "coi như có 3 người này là CSKH duy nhất".
--
-- VÌ SAO PHẢI LÀ NGƯỜI THẬT, KHÔNG PHẢI `cskh@dr4women.local` DÙNG CHUNG:
-- yêu cầu #12 của phòng khám là màn "Lịch sử thao tác… hiển thị AI làm gì, lúc
-- nào, dữ liệu trước/sau". Ba người cùng gõ vào một tài khoản thì mọi dòng sổ
-- đều mang một cái tên, và màn hình ấy trả lời sai câu hỏi duy nhất nó sinh ra
-- để trả lời. Bản dùng thử 15/08 là lúc câu trả lời đó bắt đầu có giá trị.
--
-- CÒN THIẾU, ĐÃ HỎI QUANG: Notion không có `Tên đầy đủ` cho cả ba người — chỉ
-- có tên gọi. `full_name` dưới đây vì thế là "CSKH · <tên gọi>". Có tên khai
-- sinh thì sửa đúng ba dòng trong bảng VALUES rồi chạy lại, không cần đụng gì
-- khác.
--
-- SAU KHI CHẠY FILE NÀY thì `cskh@dr4women.local` mới xoá được:
--   psql -f supabase/fixtures/xoa_tai_khoan_dung_chung.sql
-- File đó tự kiểm "bộ phận đã có người thật chưa" nên chạy trước là nó giữ lại,
-- không hỏng gì.
--
-- CHẠY:
--   psql -v mat_khau=12345678 -f supabase/fixtures/cskh_ba_nguoi_that.sql
--
-- IDEMPOTENT. Chạy lại chỉ cập nhật, không sinh người thứ tư.

\set ON_ERROR_STOP on

-- psql KHÔNG thay `:mat_khau` bên trong khối $$…$$. Đưa qua set_config rồi đọc
-- lại. Truyền `-v mat_khau=12345678`, KHÔNG kèm nháy.
SELECT '' AS dat_mat_khau FROM set_config('app.mat_khau', :'mat_khau', false);

DO $$
DECLARE
    v_clinic uuid;
    v_loc    uuid;
    pw       text := current_setting('app.mat_khau');
    ng       record;
    uid      uuid;
    sid      uuid;
    v_moi    int := 0;
BEGIN
    SELECT id INTO v_clinic FROM public.clinic ORDER BY created_at LIMIT 1;
    IF v_clinic IS NULL THEN
        RAISE EXCEPTION 'Chưa có phòng khám nào — nạp clinic_roster.sql trước.';
    END IF;

    -- Cơ sở đang mở. Hào Nam còn `is_active = false` (chưa khai trương), nên
    -- lấy cơ sở hoạt động đầu tiên chứ không ghim tên "Kim Ngưu" — ghim tên là
    -- file này chết ngày phòng khám đổi cách viết.
    SELECT id INTO v_loc
      FROM public.clinic_location
     WHERE clinic_id = v_clinic AND is_active
     ORDER BY created_at
     LIMIT 1;
    IF v_loc IS NULL THEN
        RAISE EXCEPTION 'Không có cơ sở nào đang hoạt động.';
    END IF;

    FOR ng IN
        SELECT * FROM (VALUES
            ('c5c40000-0000-4000-8000-000000000001'::uuid,
             'CSKH · Diệu Hoa',  'Diệu Hoa',  'cskhdieuhoa@dr4women.vn'),
            ('c5c40000-0000-4000-8000-000000000002'::uuid,
             'CSKH · Huyền Diệu','Huyền Diệu','cskhhuyendieu@dr4women.vn'),
            ('c5c40000-0000-4000-8000-000000000003'::uuid,
             'CSKH · Kim Tiến',  'Kim Tiến',  'cskhkimtien@dr4women.vn')
        ) AS t(id, ten, ngan, email)
    LOOP
        INSERT INTO public.staff (
            id, full_name, short_name, primary_department,
            primary_location_id, is_active
        ) VALUES (
            ng.id, ng.ten, ng.ngan, 'CSKH', v_loc, TRUE
        )
        ON CONFLICT (id) DO UPDATE SET
            full_name           = EXCLUDED.full_name,
            short_name          = EXCLUDED.short_name,
            primary_department  = EXCLUDED.primary_department,
            primary_location_id = EXCLUDED.primary_location_id,
            is_active           = TRUE,
            updated_at          = now()
        RETURNING id INTO sid;

        SELECT auth_user_id INTO uid FROM public.staff WHERE id = sid;

        IF uid IS NULL THEN
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

            -- GoTrue tra người dùng qua auth.identities khi đăng nhập bằng mật
            -- khẩu, KHÔNG tra thẳng auth.users. Thiếu dòng này là đăng nhập trả
            -- invalid_credentials y như gõ sai mật khẩu.
            INSERT INTO auth.identities (
                provider_id, user_id, identity_data, provider,
                created_at, updated_at
            ) VALUES (
                uid::text, uid,
                jsonb_build_object('sub', uid::text, 'email', ng.email,
                                   'email_verified', true,
                                   'phone_verified', false),
                'email', now(), now()
            )
            ON CONFLICT (provider_id, provider) DO UPDATE
                SET identity_data = EXCLUDED.identity_data, updated_at = now();

            UPDATE public.staff SET auth_user_id = uid, updated_at = now()
             WHERE id = sid;
            v_moi := v_moi + 1;
        END IF;

        -- Vai trong phòng khám phải khớp bộ phận, nếu không backend đọc ra một
        -- quyền còn giao diện đọc ra quyền khác.
        INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
        VALUES (v_clinic, sid, 'CSKH', TRUE)
        ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = TRUE;
    END LOOP;

    RAISE NOTICE 'CSKH: tạo mới % tài khoản (tổng 3 người).', v_moi;
END $$;

-- ---------------------------------------------------------------------------
-- ĐỔI TÊN ĐĂNG NHẬP CỦA QUẢN LÝ
--
-- `ql@dr4women.local` quá tắt để đoán ra, và `.local` là miền giả. Quang chốt
-- 09/08: đổi thành `quanlyhethongdr4women@dr4women.vn`.
--
-- ĐỔI EMAIL, KHÔNG TẠO TÀI KHOẢN MỚI. Tạo mới là quản lý có hai đường vào, sổ
-- sự kiện tách làm đôi, và tài khoản cũ vẫn đăng nhập được. Đây cũng là vai DUY
-- NHẤT tạo lại được tài khoản cho người khác — mất nó là không ai sửa được nữa
-- (docs/DANG-LAM.md §2).
-- ---------------------------------------------------------------------------
DO $$
DECLARE v_uid uuid; v_email text := 'quanlyhethongdr4women@dr4women.vn';
BEGIN
    SELECT u.id INTO v_uid FROM auth.users u WHERE u.email = 'ql@dr4women.local';

    IF v_uid IS NULL THEN
        RAISE NOTICE 'Không thấy ql@dr4women.local — có thể đã đổi rồi. Bỏ qua.';
        RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM auth.users WHERE email = v_email) THEN
        RAISE NOTICE 'Đã có %, không đổi đè lên.', v_email;
        RETURN;
    END IF;

    UPDATE auth.users SET email = v_email, updated_at = now() WHERE id = v_uid;

    -- identity_data mang bản sao của email. Bỏ quên nó thì GoTrue vẫn cho đăng
    -- nhập nhưng token mang email cũ — hai nguồn sự thật cho cùng một người.
    UPDATE auth.identities
       SET identity_data = identity_data
             || jsonb_build_object('email', v_email),
           updated_at = now()
     WHERE user_id = v_uid AND provider = 'email';

    RAISE NOTICE 'Quản lý: ql@dr4women.local → %', v_email;
END $$;

-- ---------------------------------------------------------------------------
-- CHỨC VỤ ĐỨNG TRƯỚC TÊN
--
-- Quang 09/08: *"tên bác sĩ BS SA Bá Linh thì phải ghi rõ là Bác sĩ siêu âm Đào
-- Bá Linh, tương tự với các bác sĩ khác"* và *"Tiên = Nguyễn Thuỷ Tiên kèm chức
-- vụ ở đầu"*.
--
-- GIẢ ĐỊNH ĐÃ NÊU RÕ VỚI QUANG — dạng dùng ở đây là `<chức vụ> · <tên đã có>`,
-- tức GIỮ học hàm chứ không thay nó:
--     'Ths. Đào Bá Linh'        → 'Bác sĩ siêu âm · Ths. Đào Bá Linh'
--     'TS.BS. Phan Chí Thành'   → 'Bác sĩ · TS.BS. Phan Chí Thành'
-- Bản nguyên văn theo ví dụ của Quang sẽ là 'Bác sĩ siêu âm Đào Bá Linh' — bỏ
-- mất TS./Ths./BSNT. Với phòng khám thì học hàm là thông tin bệnh nhân đọc, và
-- xoá nó khỏi cơ sở dữ liệu thì không lấy lại được. Muốn đúng nguyên văn thì
-- đổi `' · ' || s.full_name` thành phần tên bỏ tiền tố học hàm.
--
-- KHỚP THEO short_name. full_name đổi sau mỗi lần chạy nên không dùng làm khoá;
-- short_name thì cố định và các fixture khác cũng tra theo nó.
-- CHẠY LẠI ĐƯỢC: điều kiện NOT LIKE chặn việc cộng tiền tố lần thứ hai.
-- ---------------------------------------------------------------------------
BEGIN;

UPDATE public.staff AS s
   SET full_name = m.chuc_vu || ' · ' || s.full_name, updated_at = now()
  FROM (VALUES
    -- Bác sĩ siêu âm
    ('SA Bá Linh', 'Bác sĩ siêu âm'),
    ('SA Đạt',     'Bác sĩ siêu âm'),
    ('SA Minh',    'Bác sĩ siêu âm'),
    ('SA Hoàng',   'Bác sĩ siêu âm'),
    ('SA Tiến',    'Bác sĩ siêu âm'),
    ('SA Giáp',    'Bác sĩ siêu âm'),
    -- Bác sĩ khám
    ('Thành',      'Bác sĩ'),
    ('Hằng',       'Bác sĩ'),
    ('Linh NK',    'Bác sĩ'),
    ('Nam',        'Bác sĩ'),
    ('Hùng',       'Bác sĩ'),
    ('Thiệp',      'Bác sĩ'),
    ('Quyết',      'Bác sĩ'),
    ('Nghị',       'Bác sĩ')
  ) AS m(ngan, chuc_vu)
 WHERE s.short_name = m.ngan
   AND s.primary_department IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
   AND s.full_name NOT LIKE '%· %';

-- Tiên — một trong hai cái tên mà docs/DANG-LAM.md §3 câu 4 chưa ghép được ai.
-- Notion "lib 3 - danh sách nhân viên" có 'ĐD Thủy Tiên' = 'Nguyễn Thuỷ Tiên'.
-- QUANG ĐÃ XÁC NHẬN 09/08.
--
-- CHỨC VỤ LẤY TỪ CHÍNH BỘ PHẬN TRONG HỆ THỐNG, KHÔNG GÕ TAY.
-- Bản đầu tôi ghi cứng "Điều dưỡng" theo tên gọi bên Notion. Chạy thử trên
-- staging mới thấy `primary_department` của chị ấy là RECEPTION — tức hệ thống
-- xếp Lễ tân. Ghi cứng "Điều dưỡng" là để hai nguồn nói hai điều khác nhau về
-- cùng một người, đúng loại lỗi mà màn "Lịch sử thao tác" không cứu được.
--
-- ĐÃ BÁO QUANG: Notion ghi "ĐD Thủy Tiên" và `Vị trí nhân sự` của chị có CẢ
-- "Lễ tân - Thu ngân" LẪN "Điều dưỡng sản" — chị làm hai việc. Ở đây lấy theo
-- bộ phận chính trong hệ thống; muốn đổi thì đổi `primary_department`, đừng đổi
-- mỗi chữ hiển thị.
--
-- Gán TUYỆT ĐỐI (không nối thêm) nên chạy lại bao nhiêu lần cũng ra một kết quả.
UPDATE public.staff
   SET full_name = CASE primary_department
                     WHEN 'RECEPTION'         THEN 'Lễ tân'
                     WHEN 'NURSE_ULTRASOUND'  THEN 'Điều dưỡng siêu âm'
                     WHEN 'CASHIER'           THEN 'Thu ngân'
                     ELSE 'Điều dưỡng'
                   END || ' · Nguyễn Thuỷ Tiên',
       updated_at = now()
 WHERE short_name IN ('Thủy Tiên', 'Tiên');

-- 'Đào' KHÔNG PHẢI 'SA Bá Linh' — tôi đã đoán nhầm và đây là chỗ đính chính.
-- Hai dòng nhân sự khác nhau: `Đào` là DOCTOR (bàn khám), còn `SA Bá Linh` =
-- 'Ths. Đào Bá Linh' là ULTRASOUND_DOCTOR. Trùng chữ "Đào" mà khác người.
-- Nên câu hỏi cũ của docs/DANG-LAM.md §3 ("tên đầy đủ của BS Đào") VẪN CÒN MỞ:
-- không đặt tiền tố chức vụ cho dòng này, vì làm vậy chỉ khiến một cái tên chưa
-- ai xác minh trông như đã xác minh.
DO $$
DECLARE v_ten text;
BEGIN
    SELECT full_name INTO v_ten
      FROM public.staff
     WHERE short_name = 'Đào' AND is_active;
    IF v_ten IS NOT NULL THEN
        -- plpgsql chỉ hiểu `%`; viết `%s` là chữ "s" rơi thẳng ra thông báo
        -- ("BS Đàos"). Đã trả giá một lần trên staging.
        RAISE NOTICE 'CÒN THIẾU: bác sĩ "%" chưa có tên đầy đủ — hỏi phòng khám.', v_ten;
    END IF;
END $$;

COMMIT;

-- Nói ra kết quả để người chạy nhìn được, đừng để lặng lẽ.
SELECT primary_department AS bo_phan, short_name AS ten_goi, full_name AS hien_thi
  FROM public.staff
 WHERE is_active
   AND (primary_department IN ('DOCTOR', 'ULTRASOUND_DOCTOR', 'CSKH')
        OR short_name IN ('Thủy Tiên', 'Tiên'))
 ORDER BY primary_department, short_name;
