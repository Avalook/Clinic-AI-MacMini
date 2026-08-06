-- Kho mật khẩu của chính ứng dụng, thay chỗ auth.users của GoTrue.
--
-- VÌ SAO. GoTrue tự dựng schema `auth` và tự tạo các role Postgres lúc khởi
-- động — cần CREATEROLE. Database cho thuê không cấp (đo trên Viettel IDC
-- 06/08/2026: không tạo được vai nào, và cả bảy vai Supabase đều chưa có).
-- Chừng nào đăng nhập còn nằm ở GoTrue thì hệ thống còn chỉ chạy được trên
-- database mình tự cài và tự cấp quyền cho mình.
--
-- KHÔNG AI PHẢI ĐỔI MẬT KHẨU. auth.users lưu bcrypt (`$2a$06$…`, 60 ký tự) và
-- pgcrypto `crypt()` kiểm đúng định dạng ấy — đã thử trên VPS. Nên bảng này
-- chép nguyên chuỗi băm sang, không đụng tới mật khẩu của ai.
--
-- BẢNG NÀY LÀ CỬA VÀO BỆNH ÁN. Ba điều dưới đây không phải trang trí:
--   * RLS bật và KHÔNG có policy nào → mọi client qua PostgREST đều thấy rỗng.
--     Chỉ chủ sở hữu bảng (tài khoản backend chạy migration) đọc được.
--   * Không có cột nào chứa mật khẩu thô, và cũng không có đường nào ghi được
--     mật khẩu thô vào — chỉ nhận chuỗi đã băm.
--   * Đếm lần sai + khoá tạm nằm NGAY TRONG BẢNG, không ở bộ nhớ tiến trình:
--     bộ nhớ mất khi khởi động lại, và kẻ dò mật khẩu chỉ cần chờ một lần
--     deploy là đếm lại từ đầu.

CREATE TABLE IF NOT EXISTS public.app_credential (
    staff_id       uuid PRIMARY KEY
                        REFERENCES public.staff(id) ON DELETE CASCADE,
    email          text NOT NULL,
    --: bcrypt do pgcrypto sinh. KHÔNG BAO GIỜ chứa mật khẩu thô.
    password_hash  text NOT NULL,
    --: Đếm lần đăng nhập sai liên tiếp; về 0 khi vào được.
    failed_attempts int NOT NULL DEFAULT 0,
    --: Khoá tới thời điểm này. NULL = không khoá.
    locked_until   timestamptz,
    last_login_at  timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT app_credential_email_not_blank CHECK (btrim(email) <> ''),
    -- Chuỗi băm bcrypt luôn 60 ký tự và mở đầu bằng $2. Ràng buộc này chặn
    -- đúng một tai nạn: ai đó ghi thẳng mật khẩu thô vào cột này.
    CONSTRAINT app_credential_hash_looks_bcrypt
        CHECK (password_hash LIKE '$2%' AND length(password_hash) = 60)
);

-- Email là thứ người dùng gõ, nên so KHÔNG phân biệt hoa thường. Chỉ mục trên
-- lower() vừa ép duy nhất vừa cho tra cứu nhanh — không cần citext (extension
-- ấy không nằm trong danh sách được cài trên database thuê).
CREATE UNIQUE INDEX IF NOT EXISTS uq_app_credential_email
    ON public.app_credential (lower(email));

ALTER TABLE public.app_credential ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.app_credential IS
    'Mật khẩu ứng dụng (bcrypt), thay auth.users của GoTrue. RLS bật và KHÔNG '
    'có policy nào: chỉ chủ sở hữu bảng đọc được, mọi client qua PostgREST '
    'thấy rỗng.';

-- Chép sang từ auth.users, cho những tài khoản ĐÃ gắn với một nhân viên.
-- Tài khoản không gắn nhân viên thì không đăng nhập được vào ứng dụng dù có
-- mật khẩu đúng (identity.py từ chối), nên chép sang cũng vô nghĩa.
--
-- Bọc trong kiểm tra tồn tại: trên database KHÔNG có GoTrue (Viettel), schema
-- `auth` không tồn tại và migration vẫn phải chạy trót lọt.
-- HỎI CÓ ĐỦ CỘT, KHÔNG PHẢI CÓ BẢNG.
--
-- Bản đầu chỉ kiểm `auth.users` có tồn tại không. CI có bảng ấy — nhưng là bản
-- RÚT GỌN dựng trong bootstrap_plain_postgres.sql, đúng một cột `id`, đủ để
-- `auth.uid()` chạy cho các bài kiểm RLS. Không có `email`, không có
-- `encrypted_password`. Nên migration chạy lọt phép kiểm rồi chết ở dòng
-- SELECT: "column u.email does not exist".
--
-- Trên máy có GoTrue thật thì bảng đầy đủ nên không lộ ra; chỉ CI mới thấy.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'auth' AND table_name = 'users'
           AND column_name = 'email'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'auth' AND table_name = 'users'
           AND column_name = 'encrypted_password'
    ) THEN
        INSERT INTO public.app_credential (staff_id, email, password_hash)
        SELECT s.id, u.email, u.encrypted_password
          FROM auth.users u
          JOIN public.staff s ON s.auth_user_id = u.id
         WHERE u.encrypted_password IS NOT NULL
           AND u.encrypted_password LIKE '$2%'
           AND length(u.encrypted_password) = 60
        ON CONFLICT (staff_id) DO NOTHING;
        RAISE NOTICE 'da chep % tai khoan tu auth.users', (
            SELECT count(*) FROM public.app_credential);
    ELSE
        RAISE NOTICE 'auth.users khong co / thieu cot — bo qua buoc chep';
    END IF;
END $$;
