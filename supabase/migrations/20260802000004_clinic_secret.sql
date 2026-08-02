-- Bí mật của phòng khám không nằm chung chỗ với cấu hình của phòng khám.
--
-- `clinic.settings -> 'pos'` đang giữ client_secret KiotViet, trong khi
-- 20260730000003 cấp `GRANT SELECT ON public.clinic TO authenticated`. Policy
-- `clinic_select_own` lọc **dòng**, không lọc **cột** — nên bất kỳ nhân sự nào
-- đăng nhập cũng đọc được toàn bộ settings của phòng khám mình bằng anon key,
-- chỉ cần một câu PostgREST. Không cần lỗi nào xảy ra: đó là hành vi đúng của
-- những gì đã cấp.
--
-- Docstring của services/pos_config.py còn viết credential "never in a column
-- that ends up in a client-readable view" — đúng ý định, ngược với thực tế.
--
-- Hai việc, cùng một lý do:
--
-- 1. Bảng `clinic_secret` **không có policy nào**, không cấp gì cho
--    authenticated — cùng khuôn với idempotency_key và pos_outbox (ADR-0012).
--    Không có policy nghĩa là không có đường đọc từ trình duyệt, kể cả khi ai
--    đó lỡ tay cấp GRANT: RLS bật + 0 policy = 0 dòng.
-- 2. `GRANT SELECT` trên `clinic` thu về **danh sách cột**. Cột nào chưa được
--    kể tên thì client không đọc được, kể cả cột thêm sau này — mặc định là
--    đóng thay vì mở.
--
-- Tách theo nghĩa, không theo độ nhạy cảm: **dùng POS nào** là cấu hình, ở lại
-- settings; **đăng nhập POS bằng gì** là bí mật, sang clinic_secret. Nhờ vậy
-- provisioning phòng khám #2 vẫn ghi settings như thường, còn credential đi
-- đường riêng.
--
-- Bước sau (chưa làm ở đây): Supabase Vault hoặc pgcrypto để mã hoá at-rest.
-- Việc đó chỉ có nghĩa khi bí mật đã ra khỏi bảng ai-cũng-đọc-được, tức là sau
-- migration này.

-- ---------------------------------------------------------------------------
-- 1. Bảng bí mật theo phòng khám
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.clinic_secret (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid NOT NULL,
    -- 'pos' hôm nay; 'zalo', 'sms' khi tới lượt. Không CHECK danh sách cứng —
    -- thêm kênh mới không nên cần một migration chỉ để sửa CHECK — nhưng ép
    -- dạng để 'POS' và 'pos' không thành hai dòng khác nhau.
    scope text NOT NULL,
    secret jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT clinic_secret_pkey PRIMARY KEY (id),
    -- CASCADE, khác với RESTRICT ở các bảng tenant khác: xoá tenant mà để lại
    -- credential của nó là kiểu rác nguy hiểm nhất. Và clinic vốn đã không xoá
    -- được chừng nào còn dữ liệu khám (các FK RESTRICT khác), nên nhánh này chỉ
    -- chạy trong một cuộc dọn dẹp có chủ đích.
    CONSTRAINT clinic_secret_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic (id) ON DELETE CASCADE,
    CONSTRAINT uq_clinic_secret UNIQUE (clinic_id, scope),
    CONSTRAINT clinic_secret_scope_check CHECK (scope ~ '^[a-z][a-z0-9_]*$')
);

COMMENT ON TABLE public.clinic_secret IS
    'Credential theo phòng khám. Không policy, không grant cho authenticated: '
    'chỉ backend (service_role) đọc. Cấu hình không nhạy cảm ở clinic.settings.';

CREATE INDEX IF NOT EXISTS idx_clinic_secret_clinic
    ON public.clinic_secret (clinic_id, scope);

DROP TRIGGER IF EXISTS clinic_secret_set_updated_at ON public.clinic_secret;
CREATE TRIGGER clinic_secret_set_updated_at
    BEFORE UPDATE ON public.clinic_secret
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- RLS bật và **cố ý không có policy nào**. Đây không phải thiếu sót: bảng nào
-- có policy đọc thì 20260730000008 sẽ tự cấp SELECT cho authenticated. Bảng này
-- không được phép có.
ALTER TABLE public.clinic_secret ENABLE ROW LEVEL SECURITY;

GRANT ALL ON public.clinic_secret TO service_role;
REVOKE ALL ON public.clinic_secret FROM anon, authenticated;

-- ---------------------------------------------------------------------------
-- 2. Chuyển credential POS đang nằm trong settings
-- ---------------------------------------------------------------------------

-- Chạy lại được: lần hai không còn khoá nào khớp nên WHERE loại hết. ON CONFLICT
-- gộp thay vì ghi đè, để một lần chạy lại không xoá bí mật đã được cập nhật
-- bằng đường khác.
INSERT INTO public.clinic_secret (clinic_id, scope, secret)
SELECT c.id,
       'pos',
       jsonb_strip_nulls(jsonb_build_object(
           'retailer',      c.settings -> 'pos' ->> 'retailer',
           'client_id',     c.settings -> 'pos' ->> 'client_id',
           'client_secret', c.settings -> 'pos' ->> 'client_secret',
           'branch_id',     c.settings -> 'pos' ->> 'branch_id'
       ))
  FROM public.clinic c
 WHERE c.settings -> 'pos' ?| ARRAY['retailer', 'client_id', 'client_secret', 'branch_id']
    ON CONFLICT (clinic_id, scope)
    DO UPDATE SET secret     = public.clinic_secret.secret || EXCLUDED.secret,
                  updated_at = now();

-- Chỉ bỏ 4 khoá credential; 'adapter' (dùng POS nào) là cấu hình nên ở lại.
UPDATE public.clinic
   SET settings = jsonb_set(
           settings,
           '{pos}',
           (settings -> 'pos') - 'retailer' - 'client_id'
                               - 'client_secret' - 'branch_id'
       ),
       updated_at = now()
 WHERE settings -> 'pos' ?| ARRAY['retailer', 'client_id', 'client_secret', 'branch_id'];

-- ---------------------------------------------------------------------------
-- 3. Thu hẹp quyền đọc clinic xuống danh sách cột
-- ---------------------------------------------------------------------------

-- Thứ tự quan trọng: REVOKE quyền mức bảng trước, rồi mới cấp mức cột. Nếu chỉ
-- GRANT thêm mức cột mà không REVOKE, quyền mức bảng cũ vẫn đọc được settings.
--
-- Lưu ý cho người đọc sau: 20260730000008 cấp SELECT mức bảng cho mọi bảng có
-- policy đọc, và clinic có policy. Chạy lại toàn bộ chain (restore drill,
-- db push retry) sẽ mở lại quyền đó — rồi migration này, chạy sau vì số lớn
-- hơn, thu lại. Trạng thái cuối luôn đúng vì thứ tự version, không vì may mắn.
-- supabase/tests/clinic_secret.sql khẳng định lại điều này sau khi áp một lượt.
REVOKE SELECT ON public.clinic FROM authenticated;
GRANT SELECT (id, code, name, timezone, is_active) ON public.clinic TO authenticated;

COMMENT ON COLUMN public.clinic.settings IS
    'Cấu hình vận hành của phòng khám (POS adapter, slot, brand). '
    'KHÔNG chứa credential — xem public.clinic_secret. authenticated không có '
    'quyền đọc cột này (20260802000004).';
