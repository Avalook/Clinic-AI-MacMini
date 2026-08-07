-- Xoá tài khoản chức danh dùng chung — CHỈ những vai đã có người thật thay thế.
--
-- Bốn vai còn lại (Quản lý, Thu ngân, CSKH, Dược sĩ) chưa có một người thật nào
-- trong danh sách nhân sự, nên xoá tài khoản của họ là mất hẳn đường vào của
-- bốn bộ phận — kể cả Quản lý, chính là vai duy nhất tạo lại được tài khoản.
DO $$
DECLARE
    t record;
    v_that int;
    v_xoa  int := 0;
BEGIN
    FOR t IN
        SELECT s.id AS staff_id, s.auth_user_id, s.full_name, s.primary_department
          FROM public.staff s
         WHERE s.full_name LIKE '%(tài khoản thử)'
           AND s.auth_user_id IS NOT NULL
    LOOP
        SELECT count(*) INTO v_that
          FROM public.staff x
         WHERE x.primary_department = t.primary_department
           AND x.is_active
           AND x.auth_user_id IS NOT NULL
           AND x.full_name NOT LIKE '%(tài khoản thử)';

        IF v_that = 0 THEN
            RAISE NOTICE 'GIỮ %: bộ phận % chưa có người thật nào có tài khoản.',
                t.full_name, t.primary_department;
            CONTINUE;
        END IF;

        -- Gỡ liên kết trước rồi mới xoá, để không còn dòng nhân sự nào trỏ vào
        -- một tài khoản đã biến mất.
        UPDATE public.staff SET auth_user_id = NULL, is_active = FALSE,
                                updated_at = now()
         WHERE id = t.staff_id;
        UPDATE public.clinic_membership SET is_active = FALSE
         WHERE staff_id = t.staff_id;
        DELETE FROM auth.identities WHERE user_id = t.auth_user_id;
        DELETE FROM auth.users      WHERE id = t.auth_user_id;
        v_xoa := v_xoa + 1;
        RAISE NOTICE 'XOÁ %: bộ phận % đã có % người thật.',
            t.full_name, t.primary_department, v_that;
    END LOOP;
    RAISE NOTICE 'Đã xoá % tài khoản dùng chung.', v_xoa;
END $$;

SELECT u.email, coalesce(s.full_name, '(không gắn nhân sự)') AS nguoi
  FROM auth.users u LEFT JOIN public.staff s ON s.auth_user_id = u.id
 WHERE u.email LIKE '%.local' ORDER BY u.email;
