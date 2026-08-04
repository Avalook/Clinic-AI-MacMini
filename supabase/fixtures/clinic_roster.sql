-- Danh sách nhân sự thật của Dr4Women — trích từ bản dữ liệu khách gửi.
--
-- Trước file này, database chỉ có 7 tài khoản giả của staff_logins.sql
-- ("BS A local", "BS SA local"...). Mọi màn hình có cột bác sĩ đều hiện tên
-- bịa, nên không ai nhìn ra được lịch của BS Thành khác lịch của BS Hằng chỗ
-- nào — mà chính cái khác nhau đó mới là thứ cần test (CAP-01, thứ tự gọi,
-- phân ca).
--
-- NGUỒN (thư mục "Data khách gửi", export từ Notion của phòng khám):
--   * LỊCH HẸN ....csv          — cột "Bác sĩ": 10.032 lượt hẹn → 8 bác sĩ khám
--   * Dịch vụ ....csv           — cột "//Người làm": 15.075 dịch vụ → 31 người,
--                                 tiền tố BS / BS SA / TL / ĐD cho biết vai trò
--   * BẢNG LÀM VIỆC 05.2026     — sheet "BCC 06 - 2026", cột "Bộ phận":
--                                 bộ phận chính + các việc kiêm nhiệm
--
-- KHÔNG chứa PII nhân sự: chỉ tên gọi trong công việc ("BS Thành", "ĐD Trang
-- Lê") — đúng thứ mà mọi bản ghi vận hành và mọi màn hình đang dùng. Họ tên
-- đầy đủ, ngày sinh, lương, hợp đồng ở bảng chấm công KHÔNG được đưa vào đây.
--
-- KHÔNG tạo tài khoản đăng nhập. staff.auth_user_id để NULL; gắn login là việc
-- riêng, cần email thật của từng người (xem staff_logins.sql + ADR-0009).
--
--   psql "$DB" -f supabase/fixtures/clinic_roster.sql
--
-- Chạy lại được: id cố định + ON CONFLICT, nên nạp bao nhiêu lần cũng ra một
-- kết quả. Sửa vai trò của ai thì sửa ở đây rồi chạy lại, đừng sửa tay trên
-- dashboard.

\set ON_ERROR_STOP on

DO $roster$
DECLARE
    v_clinic uuid := 'a0000000-0000-4000-8000-000000000001';
    v_loc    uuid;
    person   record;
    cap      text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.clinic WHERE id = v_clinic) THEN
        RAISE EXCEPTION 'clinic % missing — apply the migrations first', v_clinic;
    END IF;

    -- Gần như toàn bộ hoạt động ở Kim Ngưu (9.481/10.032 lượt hẹn); Hào Nam đã
    -- ngừng (is_active=false trong seed.sql).
    SELECT id INTO v_loc FROM public.clinic_location
     WHERE clinic_id = v_clinic AND code = 'KN';

    FOR person IN
        SELECT * FROM (VALUES
        -- id, tên gọi trong công việc, tên ngắn, bộ phận chính, kiêm nhiệm
        --
        -- BÁC SĨ KHÁM — thứ tự theo số lượt hẹn trong LỊCH HẸN.csv
        ('d0000000-0000-4000-8000-000000000001'::uuid, 'BS Thành',         'Thành',       'DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000002'::uuid, 'BS Hằng',          'Hằng',        'DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000003'::uuid, 'BS Nam',           'Nam',         'DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000004'::uuid, 'BS Hùng',          'Hùng',        'DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000005'::uuid, 'BS Thiệp',         'Thiệp',       'DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000006'::uuid, 'BS Quyết',         'Quyết',       'DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000007'::uuid, 'BS Linh Nam khoa', 'Linh NK',     'DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000008'::uuid, 'BS Đào',           'Đào',         'DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000009'::uuid, 'BS Nghị',          'Nghị',        'DOCTOR', '{}'::text[]),

        -- BÁC SĨ SIÊU ÂM — tiền tố "BS SA" trong cột //Người làm
        ('d0000000-0000-4000-8000-000000000011'::uuid, 'BS SA Minh',       'SA Minh',     'ULTRASOUND_DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000012'::uuid, 'BS SA Đạt',        'SA Đạt',      'ULTRASOUND_DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000013'::uuid, 'BS SA Tiến',       'SA Tiến',     'ULTRASOUND_DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000014'::uuid, 'BS SA Hoàng',      'SA Hoàng',    'ULTRASOUND_DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000015'::uuid, 'BS SA Giáp',       'SA Giáp',     'ULTRASOUND_DOCTOR', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000016'::uuid, 'BS SA Bá Linh',    'SA Bá Linh',  'ULTRASOUND_DOCTOR', '{}'::text[]),

        -- ĐIỀU DƯỠNG SIÊU ÂM — bộ phận "Điều dưỡng siêu âm" / "ALL" / "Full time".
        -- Ba người "ALL"/"Full time" chạy được cả lễ tân + thu ngân → ghi vào
        -- staff_capability, KHÔNG tạo thêm membership (identity.py từ chối
        -- người có 2 vai đang hoạt động trong cùng một phòng khám).
        ('d0000000-0000-4000-8000-000000000021'::uuid, 'ĐD Trang Lê',      'Trang Lê',    'NURSE_ULTRASOUND', '{RECEPTION,CASHIER}'::text[]),
        ('d0000000-0000-4000-8000-000000000022'::uuid, 'ĐD Dương Trang',   'Dương Trang', 'NURSE_ULTRASOUND', '{RECEPTION,CASHIER}'::text[]),
        ('d0000000-0000-4000-8000-000000000023'::uuid, 'ĐD Hà Vũ',         'Hà Vũ',       'NURSE_ULTRASOUND', '{RECEPTION,CASHIER}'::text[]),
        ('d0000000-0000-4000-8000-000000000024'::uuid, 'ĐD Thanh Hải',     'Thanh Hải',   'NURSE_ULTRASOUND', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000025'::uuid, 'ĐD Hương Linh',    'Hương Linh',  'NURSE_ULTRASOUND', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000026'::uuid, 'ĐD Diễm Thúy',     'Diễm Thúy',   'NURSE_ULTRASOUND', '{}'::text[]),
        -- "Kim Tiến" xuất hiện 860 lần nhưng KHÔNG có tiền tố chức danh, và
        -- không có trong bảng chấm công. Đứng cùng BS SA 149 lần (nhiều nhất)
        -- → suy ra là điều dưỡng siêu âm. Đây là SUY ĐOÁN duy nhất trong file;
        -- nếu sai thì sửa dòng này rồi chạy lại.
        ('d0000000-0000-4000-8000-000000000027'::uuid, 'Kim Tiến',         'Kim Tiến',    'NURSE_ULTRASOUND', '{}'::text[]),

        -- LỄ TÂN — bộ phận bắt đầu bằng "Lễ tân - Thu ngân". Ai cũng kiêm thu
        -- ngân; một số kiêm cả thu ngân thuốc và phụ siêu âm.
        ('d0000000-0000-4000-8000-000000000031'::uuid, 'ĐD Hằng',          'Hằng LT',     'RECEPTION', '{CASHIER,CASHIER_THUOC,NURSE_ULTRASOUND}'::text[]),
        ('d0000000-0000-4000-8000-000000000032'::uuid, 'ĐD Thư',           'Thư',         'RECEPTION', '{CASHIER,CASHIER_THUOC,NURSE_ULTRASOUND}'::text[]),
        ('d0000000-0000-4000-8000-000000000033'::uuid, 'ĐD Giầu',          'Giầu',        'RECEPTION', '{CASHIER,NURSE_ULTRASOUND}'::text[]),
        ('d0000000-0000-4000-8000-000000000034'::uuid, 'ĐD Thanh An',      'Thanh An',    'RECEPTION', '{CASHIER,NURSE_ULTRASOUND}'::text[]),
        ('d0000000-0000-4000-8000-000000000035'::uuid, 'ĐD Hà Phạm',       'Hà Phạm',     'RECEPTION', '{CASHIER,NURSE_ULTRASOUND}'::text[]),
        ('d0000000-0000-4000-8000-000000000036'::uuid, 'ĐD Thủy Tiên',     'Thủy Tiên',   'RECEPTION', '{CASHIER}'::text[]),
        ('d0000000-0000-4000-8000-000000000037'::uuid, 'ĐD Phương Anh',    'Phương Anh',  'RECEPTION', '{CASHIER}'::text[]),
        -- Hai người dưới đây CHỈ có trong bảng chấm công tháng 5–6/2026, chưa
        -- có bản ghi dịch vụ nào — vào sau, chưa kịp lên dữ liệu vận hành.
        ('d0000000-0000-4000-8000-000000000038'::uuid, 'Quỳnh Anh',        'Quỳnh Anh',   'RECEPTION', '{CASHIER}'::text[]),
        ('d0000000-0000-4000-8000-000000000039'::uuid, 'Hải Yến',          'Hải Yến',     'RECEPTION', '{NURSE_ULTRASOUND}'::text[]),

        -- TRỢ LÝ Y KHOA — bộ phận "Trợ lý y khoa" / "TLYK". Hai người đầu mang
        -- tiền tố "TL" trong dữ liệu dịch vụ; "ĐD Huế" mang tiền tố ĐD nhưng
        -- bảng chấm công xếp TLYK → lấy theo bảng chấm công (nguồn nhân sự).
        ('d0000000-0000-4000-8000-000000000041'::uuid, 'TL Vân Anh',       'Vân Anh',     'TKYK', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000042'::uuid, 'TL Duy Nam',       'Duy Nam',     'TKYK', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000043'::uuid, 'ĐD Huế',           'Huế',         'TKYK', '{}'::text[]),
        ('d0000000-0000-4000-8000-000000000044'::uuid, 'TL Thanh Phương',  'Thanh Phương','TKYK', '{}'::text[])
        ) AS t(id, full_name, short_name, department, extra_caps)
    LOOP
        INSERT INTO public.staff (
            id, full_name, short_name, primary_department,
            primary_location_id, is_active
        )
        VALUES (
            person.id, person.full_name, person.short_name, person.department,
            v_loc, TRUE
        )
        ON CONFLICT (id) DO UPDATE SET
            full_name           = EXCLUDED.full_name,
            short_name          = EXCLUDED.short_name,
            primary_department  = EXCLUDED.primary_department,
            primary_location_id = EXCLUDED.primary_location_id,
            is_active           = TRUE,
            updated_at          = now();

        -- Đúng MỘT membership đang hoạt động cho mỗi người: identity.py trả 500
        -- "ambiguous_clinic_membership" nếu tìm thấy hai vai trong cùng phòng
        -- khám. Vai cũ (nếu đổi bộ phận) bị tắt chứ không xoá, để lịch sử phân
        -- quyền còn dấu vết.
        UPDATE public.clinic_membership
           SET is_active = FALSE, updated_at = now()
         WHERE clinic_id = v_clinic
           AND staff_id  = person.id
           AND role     <> person.department
           AND is_active;

        INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active)
        VALUES (v_clinic, person.id, person.department, TRUE)
        ON CONFLICT ON CONSTRAINT uq_clinic_membership DO UPDATE SET
            is_active  = TRUE,
            updated_at = now();

        -- Kiêm nhiệm: mã vai trò dùng luôn làm mã năng lực, để đọc bảng
        -- staff_capability là biết người này còn đứng được chỗ nào.
        FOREACH cap IN ARRAY person.extra_caps LOOP
            INSERT INTO public.staff_capability (staff_id, capability, proficiency_level)
            VALUES (person.id, cap, 'COMPETENT')
            ON CONFLICT (staff_id, capability) DO NOTHING;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'roster: % nhân sự đang hoạt động',
        (SELECT count(*) FROM public.clinic_membership
          WHERE clinic_id = v_clinic AND is_active);
END
$roster$;
