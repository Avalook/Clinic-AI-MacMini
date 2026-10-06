-- Thu hồi tài khoản phải khoá luôn mật khẩu của cửa đăng nhập ứng dụng.
--
-- VÌ SAO. Nút "Gỡ tài khoản" (/settings/tai-khoan → /api/admin/users, action
-- unlink) đặt staff.auth_user_id = NULL và xoá người dùng GoTrue, nhưng KHÔNG
-- đụng app_credential. Lúc "Tạo tài khoản" lại cho người ấy, auth_user_id có giá
-- trị trở lại và chuỗi băm CŨ trong app_credential mở cửa /api/v1/auth/login như
-- chưa từng bị thu hồi.
--
-- KHOÁ, KHÔNG XOÁ (QUY TRÌNH mục 7: mọi thao tác hoàn tác được). Hàng giữ
-- nguyên; hai cột dưới đánh dấu bị thu hồi lúc nào, bởi ai. Đăng nhập ứng dụng
-- từ chối hàng có thu_hoi_luc. "Tạo tài khoản" lại cho đúng nhân viên ấy (đường
-- nối duy nhất, /api/v1/staff/{id}/tai-khoan/noi) xoá dấu — đó là đường hoàn tác.
--
-- Cột thêm, cho phép NULL, không mặc định: code cũ không đọc nó và vẫn chạy.

ALTER TABLE public.app_credential
    ADD COLUMN IF NOT EXISTS thu_hoi_luc timestamptz,
    ADD COLUMN IF NOT EXISTS thu_hoi_boi uuid
        REFERENCES public.staff(id) ON DELETE SET NULL;

-- Có người thu hồi thì phải có lúc thu hồi. Ngược lại được (người thu hồi đã bị
-- xoá khỏi bảng staff → ON DELETE SET NULL).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'app_credential_thu_hoi_boi_can_luc'
    ) THEN
        ALTER TABLE public.app_credential
            ADD CONSTRAINT app_credential_thu_hoi_boi_can_luc
            CHECK (thu_hoi_boi IS NULL OR thu_hoi_luc IS NOT NULL);
    END IF;
END $$;

COMMENT ON COLUMN public.app_credential.thu_hoi_luc IS
    'Bị thu hồi lúc nào (nút Gỡ tài khoản). NULL = dùng được. Tạo tài khoản lại '
    'cho đúng nhân viên này thì xoá dấu.';
COMMENT ON COLUMN public.app_credential.thu_hoi_boi IS
    'Nhân viên đã bấm thu hồi.';
