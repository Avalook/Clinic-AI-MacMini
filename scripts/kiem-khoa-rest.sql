-- Kiểm khoá /rest/v1 ở tầng database — checklist mục 6 (ý 2, 3, 4) của
-- docs/ke-hoach/khoa-rest-v1-2210.md. CHỈ ĐỌC: một giao dịch READ ONLY, cuối
-- cùng ROLLBACK. Đóng vai đúng như PostgREST làm (SET ROLE + claim JWT) bằng
-- tài khoản THẬT có sẵn trong DB của từng vai, nên không cần mật khẩu ai.
--
--   docker exec -i clinicai_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
--     < scripts/kiem-khoa-rest.sql
--
-- In ra từng dòng ĐẠT / HỎNG / BỎ QUA; có HỎNG thì lệnh kết thúc bằng lỗi.

BEGIN READ ONLY;

DO $kiem$
DECLARE
    hong integer := 0;
    vai text;
    uid uuid;
    sid uuid;
    bang text;
    n bigint;
    bi_chan boolean;
    nhay_cam text[] := ARRAY['patient', 'appointment', 'payment', 'visit',
        'prescription', 'lab_result', 'capability_grant', 'payment_cycle',
        'clinic', 'clinical_record'];
BEGIN
    -- 0. Danh sách quyền (bài canh pytest giữ bản cố định).
    SELECT count(*) INTO n FROM information_schema.role_table_grants
     WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated', 'PUBLIC');
    IF n = 0 THEN RAISE NOTICE 'ĐẠT   quyền cả bảng của anon/authenticated: 0';
    ELSE RAISE NOTICE 'HỎNG  quyền cả bảng của anon/authenticated: %', n; hong := hong + 1; END IF;

    SELECT count(*) INTO n FROM information_schema.column_privileges
     WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated', 'PUBLIC')
       AND (table_name, column_name) NOT IN (
           ('staff', 'id'), ('staff', 'auth_user_id'), ('staff', 'is_active'),
           ('staff', 'primary_department'), ('clinic_membership', 'clinic_id'),
           ('clinic_membership', 'staff_id'), ('clinic_membership', 'role'),
           ('clinic_membership', 'is_active'));
    IF n = 0 THEN RAISE NOTICE 'ĐẠT   cột ngoài danh sách cho phép: 0';
    ELSE RAISE NOTICE 'HỎNG  cột ngoài danh sách cho phép: %', n; hong := hong + 1; END IF;

    SELECT count(*) INTO n FROM information_schema.routine_privileges
     WHERE routine_schema = 'public' AND grantee IN ('anon', 'authenticated', 'PUBLIC')
       AND routine_name NOT IN ('current_staff_id', 'current_clinic_ids',
           'current_clinic_ids_for_roles', 'current_clinical_clinic_ids',
           'thu_ky_duoc_xem_khach');
    IF n = 0 THEN RAISE NOTICE 'ĐẠT   hàm /rpc ngoài danh sách cho phép: 0';
    ELSE RAISE NOTICE 'HỎNG  hàm /rpc ngoài danh sách cho phép: %', n; hong := hong + 1; END IF;

    -- 1. Từng vai: lấy MỘT tài khoản thật đang hoạt động của vai đó.
    FOREACH vai IN ARRAY ARRAY['PARTNER', 'DISPLAY', 'RECEPTION', 'CASHIER', 'DOCTOR']
    LOOP
        SELECT s.auth_user_id, s.id INTO uid, sid
          FROM staff s JOIN clinic_membership m ON m.staff_id = s.id
         WHERE m.role = vai AND m.is_active AND s.is_active AND s.auth_user_id IS NOT NULL
         ORDER BY s.created_at LIMIT 1;
        IF uid IS NULL THEN
            RAISE NOTICE 'BỎ QUA vai % — không có tài khoản đang hoạt động', vai;
            CONTINUE;
        END IF;

        EXECUTE 'SET LOCAL ROLE authenticated';
        PERFORM set_config('request.jwt.claims',
            json_build_object('sub', uid, 'role', 'authenticated')::text, true);

        FOREACH bang IN ARRAY nhay_cam LOOP
            bi_chan := false;
            BEGIN
                EXECUTE format('SELECT count(*) FROM public.%I', bang) INTO n;
            EXCEPTION WHEN insufficient_privilege THEN bi_chan := true;
            END;
            IF bi_chan THEN RAISE NOTICE 'ĐẠT   % đọc % → bị từ chối', vai, bang;
            ELSE RAISE NOTICE 'HỎNG  % đọc % → % dòng', vai, bang, n; hong := hong + 1; END IF;
        END LOOP;

        bi_chan := false;
        BEGIN
            SELECT count(national_id_number) INTO n FROM public.staff;
        EXCEPTION WHEN insufficient_privilege THEN bi_chan := true;
        END;
        IF bi_chan THEN RAISE NOTICE 'ĐẠT   % đọc staff.national_id_number → bị từ chối', vai;
        ELSE RAISE NOTICE 'HỎNG  % đọc staff.national_id_number được', vai; hong := hong + 1; END IF;

        -- Đúng câu của proxy.ts / login: phải ra đúng hàng của mình.
        SELECT count(*) INTO n FROM public.staff WHERE id <> sid;
        IF n = 0 AND EXISTS (SELECT 1 FROM public.staff WHERE id = sid AND auth_user_id = uid) THEN
            RAISE NOTICE 'ĐẠT   % đọc staff?select=id → chỉ hàng của mình', vai;
        ELSE RAISE NOTICE 'HỎNG  % thấy % hàng staff của người khác (hoặc không thấy mình)', vai, n;
            hong := hong + 1; END IF;

        SELECT count(*) INTO n FROM public.clinic_membership WHERE staff_id <> sid;
        IF n = 0 AND EXISTS (SELECT 1 FROM public.clinic_membership WHERE staff_id = sid AND is_active) THEN
            RAISE NOTICE 'ĐẠT   % đọc clinic_membership → chỉ của mình', vai;
        ELSE RAISE NOTICE 'HỎNG  % clinic_membership: % hàng người khác (hoặc không thấy mình)', vai, n;
            hong := hong + 1; END IF;

        bi_chan := false;
        BEGIN
            PERFORM public.clinic_hours_for_date(gen_random_uuid(), current_date);
        EXCEPTION WHEN insufficient_privilege THEN bi_chan := true;
        END;
        IF bi_chan THEN RAISE NOTICE 'ĐẠT   % gọi /rpc/clinic_hours_for_date → bị từ chối', vai;
        ELSE RAISE NOTICE 'HỎNG  % gọi được /rpc/clinic_hours_for_date', vai; hong := hong + 1; END IF;

        EXECUTE 'RESET ROLE';
        uid := NULL;
    END LOOP;

    -- 2. Không đăng nhập (anon key có trong bundle trình duyệt).
    EXECUTE 'SET LOCAL ROLE anon';
    bi_chan := false;
    BEGIN
        SELECT count(*) INTO n FROM public.staff;
    EXCEPTION WHEN insufficient_privilege THEN bi_chan := true;
    END;
    EXECUTE 'RESET ROLE';
    IF bi_chan THEN RAISE NOTICE 'ĐẠT   anon đọc staff → bị từ chối';
    ELSE RAISE NOTICE 'HỎNG  anon đọc được staff'; hong := hong + 1; END IF;

    IF hong > 0 THEN
        RAISE EXCEPTION 'kiem-khoa-rest: % mục HỎNG — xem các dòng HỎNG ở trên', hong;
    END IF;
    RAISE NOTICE 'TẤT CẢ ĐẠT';
END
$kiem$;

ROLLBACK;
