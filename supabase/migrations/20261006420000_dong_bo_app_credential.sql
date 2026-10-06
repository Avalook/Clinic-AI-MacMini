-- Mật khẩu GoTrue → app_credential: đồng bộ MỘT CHIỀU, GoTrue là nguồn sự thật.
--
-- VÌ SAO. Có hai kho mật khẩu: `auth.users` (GoTrue — mọi màn đăng nhập qua đây)
-- và `app_credential` (cửa /api/v1/auth/login của chính ứng dụng). "Tạo tài
-- khoản", "Đặt lại mật khẩu", "Đổi tên đăng nhập" và các script nhân sự chỉ ghi
-- GoTrue, nên app_credential thiếu dòng hoặc giữ mật khẩu CŨ (stack local 06/10:
-- 0 dòng / 13 người đã nối). Sau #345, "Tạo tài khoản" lại mở khoá với mật khẩu
-- cũ của lần trước.
--
-- CHUỖI BĂM CHÉP NGUYÊN. GoTrue băm bcrypt `$2a$10$…` (60 ký tự); pgcrypto
-- `extensions.crypt()` — thứ auth_service.py dùng để kiểm — đọc đúng định dạng
-- ấy. Đã thử 06/10 trên stack local: người dùng tạo qua API quản trị GoTrue,
-- mật khẩu đúng → khớp, sai → không. Không đổi thuật toán, không băm lại.
--
-- AI GỌI. TaiKhoanService ngay sau mỗi thao tác tài khoản (cùng giao dịch với
-- nhật ký) và vòng `su-kien` mỗi phút (bắt mọi lối khác: script, tự đổi mật khẩu
-- qua /reset-password, lời gọi hỏng giữa chừng).

-- ── Email duy nhất CHỈ giữa các dòng còn dùng ─────────────────────────────────
-- Dòng thu hồi giữ nguyên email cũ (khoá, không xoá). Quản lý gỡ "letan1" của
-- người A rồi đặt "letan1" cho người B là chuyện thường; chỉ mục cũ tính cả dòng
-- đã thu hồi nên B không bao giờ có dòng được. Đăng nhập chọn dòng còn dùng
-- trước (auth_service.py).
DROP INDEX IF EXISTS public.uq_app_credential_email;
CREATE UNIQUE INDEX uq_app_credential_email
    ON public.app_credential (lower(email))
    WHERE thu_hoi_luc IS NULL;

-- ── Hàm đồng bộ ───────────────────────────────────────────────────────────────
-- p_staff_id NULL = mọi nhân viên (vòng định kỳ); có giá trị = đúng một người.
-- p_mo_lai = true CHỈ từ "Tạo tài khoản" (nối lại có chủ ý): dòng đã thu hồi của
-- đúng p_staff_id được mở VÀ nhận mật khẩu MỚI. Mọi lối khác không mở dòng thu hồi.
--
-- Nguồn hợp lệ: staff có auth_user_id, người dùng GoTrue có email và chuỗi băm
-- dạng bcrypt (cùng ràng buộc app_credential_hash_looks_bcrypt). Nhân viên chưa
-- nối → không tạo dòng. Không bao giờ xoá dòng: gỡ nối thì đăng nhập ứng dụng đã
-- từ chối (auth_user_id NULL / thu_hoi_luc).
--
-- TRANH CHẤP ép ở đây, không ở Python:
--   * `FOR SHARE OF s`: chạy cùng lúc với "Gỡ tài khoản" (khoá staff FOR UPDATE)
--     thì chờ nó xong rồi đọc lại — staff đã gỡ nối rơi khỏi nguồn, không đẻ ra
--     dòng mới mở cho người vừa bị thu hồi.
--   * ON CONFLICT (staff_id) … WHERE thu_hoi_luc IS NULL: điều kiện xét trên bản
--     MỚI NHẤT của dòng sau khi khoá, nên dòng vừa bị thu hồi không bị ghi đè.
--   * Email đang thuộc dòng còn dùng của NHÂN VIÊN KHÁC → bỏ qua và đếm
--     (`trung_email`), không làm hỏng cả lượt vì chỉ mục duy nhất.
CREATE OR REPLACE FUNCTION public.dong_bo_app_credential(
    p_staff_id uuid DEFAULT NULL,
    p_mo_lai boolean DEFAULT false
)
RETURNS TABLE (them int, sua int, mo_lai int, trung_email int)
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_them int := 0;
    v_sua int := 0;
    v_mo_lai int := 0;
    v_trung int := 0;
BEGIN
    -- Database không có GoTrue (hoặc bảng rút gọn của CI, chỉ cột id): không có
    -- nguồn thì không làm gì — giống migration 20260806000002.
    IF (SELECT count(*) FROM information_schema.columns
         WHERE table_schema = 'auth' AND table_name = 'users'
           AND column_name IN ('email', 'encrypted_password')) < 2 THEN
        RETURN QUERY SELECT 0, 0, 0, 0;
        RETURN;
    END IF;

    -- Nối lại có chủ ý: mở dòng thu hồi + mật khẩu mới, xoá đếm sai.
    IF p_mo_lai AND p_staff_id IS NOT NULL THEN
        UPDATE app_credential c
           SET email = n.email, password_hash = n.password_hash,
               thu_hoi_luc = NULL, thu_hoi_boi = NULL,
               failed_attempts = 0, locked_until = NULL, updated_at = now()
          FROM (
              SELECT s.id AS staff_id, u.email::text AS email,
                     u.encrypted_password::text AS password_hash
                FROM staff s
                JOIN auth.users u ON u.id = s.auth_user_id
               WHERE s.id = p_staff_id
                 AND btrim(coalesce(u.email, '')) <> ''
                 AND u.encrypted_password LIKE '$2%'
                 AND length(u.encrypted_password) = 60
                 FOR SHARE OF s
          ) n
         WHERE c.staff_id = n.staff_id
           AND c.thu_hoi_luc IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM app_credential k
                WHERE lower(k.email) = lower(n.email)
                  AND k.staff_id <> n.staff_id AND k.thu_hoi_luc IS NULL);
        GET DIAGNOSTICS v_mo_lai = ROW_COUNT;
    END IF;

    WITH nguon AS (
        SELECT s.id AS staff_id, u.email::text AS email,
               u.encrypted_password::text AS password_hash
          FROM staff s
          JOIN auth.users u ON u.id = s.auth_user_id
         WHERE (p_staff_id IS NULL OR s.id = p_staff_id)
           AND btrim(coalesce(u.email, '')) <> ''
           AND u.encrypted_password LIKE '$2%'
           AND length(u.encrypted_password) = 60
           FOR SHARE OF s
    ), xet AS (
        SELECT n.*,
               EXISTS (
                   SELECT 1 FROM app_credential k
                    WHERE lower(k.email) = lower(n.email)
                      AND k.staff_id <> n.staff_id AND k.thu_hoi_luc IS NULL
               ) AS trung,
               c.staff_id IS NOT NULL AS co_dong,
               c.thu_hoi_luc IS NOT NULL AS da_thu_hoi,
               (c.email IS DISTINCT FROM n.email
                OR c.password_hash IS DISTINCT FROM n.password_hash) AS lech
          FROM nguon n
          LEFT JOIN app_credential c ON c.staff_id = n.staff_id
    ), ghi AS (
        INSERT INTO app_credential AS c (staff_id, email, password_hash)
        SELECT staff_id, email, password_hash FROM xet
         WHERE NOT trung AND NOT da_thu_hoi AND (NOT co_dong OR lech)
        ON CONFLICT (staff_id) DO UPDATE
           SET email = EXCLUDED.email,
               password_hash = EXCLUDED.password_hash,
               -- Mật khẩu mới thì đếm sai của mật khẩu cũ không còn nghĩa.
               failed_attempts = CASE
                   WHEN c.password_hash = EXCLUDED.password_hash
                   THEN c.failed_attempts ELSE 0 END,
               locked_until = CASE
                   WHEN c.password_hash = EXCLUDED.password_hash
                   THEN c.locked_until END,
               updated_at = now()
         WHERE c.thu_hoi_luc IS NULL
           AND (c.email IS DISTINCT FROM EXCLUDED.email
                OR c.password_hash IS DISTINCT FROM EXCLUDED.password_hash)
        RETURNING (xmax = 0) AS la_moi
    )
    SELECT (SELECT count(*) FILTER (WHERE la_moi) FROM ghi),
           (SELECT count(*) FILTER (WHERE NOT la_moi) FROM ghi),
           (SELECT count(*) FROM xet
             WHERE trung AND NOT da_thu_hoi AND (NOT co_dong OR lech))
      INTO v_them, v_sua, v_trung;

    RETURN QUERY SELECT v_them, v_sua, v_mo_lai, v_trung;
END
$fn$;

COMMENT ON FUNCTION public.dong_bo_app_credential(uuid, boolean) IS
    'Chép mật khẩu (bcrypt) + email từ auth.users sang app_credential, một '
    'chiều, idempotent. Không mở dòng thu hồi trừ p_mo_lai cho đúng p_staff_id '
    '(Tạo tài khoản lại). Trả số dòng thêm / sửa / mở lại / bỏ qua vì trùng email.';

-- Hàm ở schema public thì PostgREST bày ra /rest/v1/rpc. Chỉ backend (chủ sở
-- hữu) được gọi.
DO $$
DECLARE
    v text;
BEGIN
    REVOKE ALL ON FUNCTION public.dong_bo_app_credential(uuid, boolean) FROM PUBLIC;
    FOREACH v IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v) THEN
            EXECUTE format(
                'REVOKE ALL ON FUNCTION public.dong_bo_app_credential(uuid, boolean) FROM %I',
                v);
        END IF;
    END LOOP;
END $$;

-- Lấp chỗ lệch hiện có ngay khi áp (idempotent; không có GoTrue thì 0 0 0 0).
SELECT * FROM public.dong_bo_app_credential();
