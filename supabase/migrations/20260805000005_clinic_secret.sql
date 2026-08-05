-- Bí mật của phòng khám không nằm chung chỗ với cấu hình của phòng khám.
--
-- `clinic.settings` là nơi docstring của `services/pos_config.py` đang dạy người
-- ta đặt `client_secret` KiotViet. Cùng lúc đó, `clinic` vẫn mang nguyên GRANT
-- mặc định của Supabase: `authenticated` VÀ `anon` đều có SELECT **mức bảng**.
-- Policy `clinic_select_own` lọc **dòng**, không lọc **cột** — nên bất kỳ nhân
-- sự nào đăng nhập cũng đọc trọn `settings` của phòng khám mình bằng anon key
-- có sẵn trong bundle trình duyệt, chỉ bằng một câu PostgREST. Không cần lỗi
-- nào xảy ra: đó là hành vi ĐÚNG của những gì đã cấp.
--
-- HÔM NAY CHƯA CÓ BÍ MẬT NÀO BỊ LỘ: `settings` trên prod chỉ có ba khoá
-- hours/booking/display, `pos_outbox` rỗng, `POS_ADAPTER=none`. Đây không phải
-- vá lỗ đang rỉ — đây là đóng cửa TRƯỚC khi có người bước vào. Cửa sổ nguy hiểm
-- không phải "bao giờ có kẻ tấn công" mà là "bao giờ có người cấu hình POS", và
-- người đó sẽ làm đúng theo docstring hiện hành.
--
-- Tách theo NGHĨA, không theo độ nhạy cảm: **dùng POS nào** là cấu hình, ở lại
-- `settings`; **đăng nhập POS bằng gì** là bí mật, sang `clinic_secret`. Nhờ
-- vậy provisioning phòng khám #2 vẫn ghi settings như thường, credential đi
-- đường riêng.
--
-- VÌ SAO BẢNG MỚI KHÔNG CÓ POLICY NÀO: `20260730000008_table_grants.sql` quét
-- pg_policy và tự cấp `SELECT` cho `authenticated` trên MỌI bảng có policy đọc.
-- Thêm một policy vào bảng này là tự mở lại đúng cái cửa vừa đóng. RLS bật + 0
-- policy = 0 dòng đọc được từ trình duyệt, kể cả khi ai đó lỡ tay GRANT sau
-- này. Cùng khuôn `idempotency_key` và `pos_outbox` (ADR-0012).
--
-- Bước sau (chưa làm ở đây): Supabase Vault hoặc pgcrypto để mã hoá at-rest.
-- Việc đó chỉ có nghĩa khi bí mật đã ra khỏi bảng ai-cũng-đọc-được.
--
-- SỐ HIỆU: 20260805000005, không phải 20260802000004 của nhánh gốc.
--
-- Ràng buộc thật của file này chỉ là "chạy SAU 20260730000008_table_grants.sql"
-- — file đó quét pg_policy rồi cấp lại SELECT mức bảng cho mọi bảng có policy
-- đọc, nên chạy trước nó là bị mở lại đúng cái cửa vừa đóng.
--
-- Lần đầu đặt 20260805000002 và `db push` từ chối: prod đã áp tới ...000004, mà
-- chèn một version thấp hơn vào sau lưng là out-of-order. Đổi số thay vì ép
-- `--include-all`, để thứ tự trên prod và thứ tự trong thư mục migrations nói
-- cùng một câu — người khôi phục từ bản lưu sau này đọc theo tên file.

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
    -- CASCADE, khác RESTRICT ở các bảng tenant khác: xoá tenant mà để lại
    -- credential của nó là loại rác nguy hiểm nhất. Và `clinic` vốn không xoá
    -- nổi chừng nào còn dữ liệu khám (các FK RESTRICT khác chặn trước), nên
    -- nhánh này chỉ chạy trong một cuộc dọn dẹp có chủ đích.
    CONSTRAINT clinic_secret_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic (id) ON DELETE CASCADE,
    CONSTRAINT uq_clinic_secret UNIQUE (clinic_id, scope),
    CONSTRAINT clinic_secret_scope_check CHECK (scope ~ '^[a-z][a-z0-9_]*$')
);

COMMENT ON TABLE public.clinic_secret IS
    'Credential theo phòng khám. Không policy, không grant cho anon/authenticated: '
    'chỉ backend (service_role) đọc. Cấu hình không nhạy cảm ở clinic.settings.';

-- Index dẫn đầu bằng clinic_id: bất biến đa tenant, và cũng là hình dạng truy
-- vấn thật (pos_relay tra đúng một dòng theo clinic_id + scope).
CREATE INDEX IF NOT EXISTS idx_clinic_secret_clinic
    ON public.clinic_secret (clinic_id, scope);

DROP TRIGGER IF EXISTS clinic_secret_set_updated_at ON public.clinic_secret;
CREATE TRIGGER clinic_secret_set_updated_at
    BEFORE UPDATE ON public.clinic_secret
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.clinic_secret ENABLE ROW LEVEL SECURITY;

GRANT ALL ON public.clinic_secret TO service_role;
REVOKE ALL ON public.clinic_secret FROM anon, authenticated;

-- ---------------------------------------------------------------------------
-- 2. Chuyển credential POS đang nằm trong settings
-- ---------------------------------------------------------------------------

-- Trên prod hôm nay hai lệnh này là no-op (settings chỉ có hours/booking/display).
-- Giữ lại vì chúng là lưới cho staging, cho DB của lập trình viên, và cho bản
-- restore của một ngày nào đó đã kịp cấu hình POS theo docstring cũ. Xử lý dữ
-- liệu TRƯỚC khi siết quyền, trong cùng một file — nếu tách ra thì có một
-- khoảng thời gian credential vừa còn trong settings vừa mất đường đọc.
--
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
-- 3. Thu hẹp quyền trên clinic
-- ---------------------------------------------------------------------------

-- Thứ tự quan trọng: REVOKE mức bảng TRƯỚC, rồi mới GRANT mức cột. Nếu chỉ
-- GRANT thêm mức cột mà không REVOKE, quyền mức bảng cũ vẫn đọc được settings.
--
-- Chạy lại được tự nhiên: REVOKE/GRANT là khai báo trạng thái cuối, không phải
-- thao tác cộng dồn — lượt hai không đổi gì.
--
-- Lưu ý cho người đọc sau: 20260730000008 cấp SELECT mức bảng cho mọi bảng có
-- policy đọc, và clinic có policy. Chạy lại toàn chuỗi (restore drill, CI chạy
-- hai lượt, db push retry) sẽ mở lại quyền đó — rồi file này, chạy sau vì số
-- lớn hơn, thu lại. Trạng thái cuối đúng vì THỨ TỰ VERSION, không vì may mắn.

-- `anon` cũng đang cầm đủ 7 quyền mức bảng trên clinic (blanket default của
-- Supabase — bảng clinic sinh trước baseline nên 20260730000008 chưa bao giờ
-- chạm nó). Hôm nay chưa khai thác được vì RLS bật mà anon có 0 policy, nhưng
-- đó là hàng phòng thủ CUỐI, không phải hàng đầu. Bỏ policy mà để nguyên GRANT
-- chính là cái 20260804000016 đã phải đi dọn một lần.
REVOKE ALL ON public.clinic FROM anon;

-- authenticated không có việc gì phải ghi vào bảng tenant: mọi thay đổi cấu
-- hình phòng khám đi qua backend chạy service_role.
REVOKE ALL ON public.clinic FROM authenticated;

-- Năm cột này là HỢP ĐỒNG của hai chỗ trong frontend, không phải một:
--   · lib/current-staff.ts — embed `clinic!clinic_membership_clinic_id_fkey(name)`,
--     chạy trên MỌI trang, MỌI lần điều hướng (dòng danh tính "phòng khám · cơ sở").
--   · lib/feature-mode.ts  — sẽ chuyển sang gọi backend; xem ghi chú cuối file.
-- Bỏ `name` khỏi danh sách này là mất tên phòng khám trên toàn bộ giao diện, và
-- cả hai call-site đều NUỐT LỖI (try/catch, `if (error) return null`) nên hỏng
-- sẽ hoàn toàn im lặng.
GRANT SELECT (id, code, name, timezone, is_active) ON public.clinic TO authenticated;

COMMENT ON COLUMN public.clinic.settings IS
    'Cấu hình vận hành của phòng khám (POS adapter, giờ mở cửa, luật đặt lịch, '
    'brand). KHÔNG chứa credential — xem public.clinic_secret. anon và '
    'authenticated đều KHÔNG có quyền đọc cột này (20260805000002).';

-- ---------------------------------------------------------------------------
-- 4. Tự kiểm
-- ---------------------------------------------------------------------------

-- Migration này thay đổi QUYỀN, thứ không hiện ra trong bất kỳ `\d` nào và
-- không làm hỏng gì ngay lập tức nếu sai. Nên nó phải tự khẳng định lại kết
-- quả, ngay tại đây, thay vì trông vào việc ai đó nhớ chạy test.
DO $verify$
DECLARE
    missing text;
BEGIN
    -- 4.1 Bảng tồn tại, RLS bật, và KHÔNG có policy nào.
    IF to_regclass('public.clinic_secret') IS NULL THEN
        RAISE EXCEPTION 'clinic_secret chưa được tạo';
    END IF;

    IF NOT (SELECT relrowsecurity FROM pg_class
             WHERE oid = 'public.clinic_secret'::regclass) THEN
        RAISE EXCEPTION 'clinic_secret phải bật RLS';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_policy
                WHERE polrelid = 'public.clinic_secret'::regclass) THEN
        RAISE EXCEPTION
            'clinic_secret KHÔNG được có policy: có policy thì 20260730000008 '
            'sẽ tự cấp SELECT cho authenticated ở lần replay sau';
    END IF;

    -- 4.2 Bất biến đa tenant: clinic_id NOT NULL + FK + index dẫn đầu clinic_id.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'clinic_secret'
           AND column_name = 'clinic_id' AND is_nullable = 'YES'
    ) THEN
        RAISE EXCEPTION 'clinic_secret.clinic_id phải NOT NULL';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.clinic_secret'::regclass
           AND contype = 'f' AND confrelid = 'public.clinic'::regclass
    ) THEN
        RAISE EXCEPTION 'clinic_secret.clinic_id phải có FK tới clinic';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_index i
         WHERE i.indrelid = 'public.clinic_secret'::regclass
           AND i.indkey[0] = (
               SELECT attnum FROM pg_attribute
                WHERE attrelid = 'public.clinic_secret'::regclass
                  AND attname = 'clinic_id')
    ) THEN
        RAISE EXCEPTION 'clinic_secret phải có index dẫn đầu bằng clinic_id';
    END IF;

    -- 4.3 Không role client nào chạm được clinic_secret.
    SELECT string_agg(r, ', ') INTO missing
      FROM unnest(ARRAY['anon', 'authenticated']) AS r
     WHERE has_table_privilege(r, 'public.clinic_secret', 'SELECT')
        OR has_table_privilege(r, 'public.clinic_secret', 'INSERT')
        OR has_table_privilege(r, 'public.clinic_secret', 'UPDATE')
        OR has_table_privilege(r, 'public.clinic_secret', 'DELETE');
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'các role này vẫn chạm được clinic_secret: %', missing;
    END IF;

    IF NOT has_table_privilege('service_role', 'public.clinic_secret', 'SELECT') THEN
        RAISE EXCEPTION 'service_role phải đọc được clinic_secret, nếu không pos_relay chết câm';
    END IF;

    -- 4.4 Không ai còn đọc được clinic.settings từ trình duyệt.
    SELECT string_agg(r, ', ') INTO missing
      FROM unnest(ARRAY['anon', 'authenticated']) AS r
     WHERE has_column_privilege(r, 'public.clinic', 'settings', 'SELECT');
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'các role này vẫn đọc được clinic.settings: %', missing;
    END IF;

    -- 4.5 …nhưng năm cột danh tính thì phải còn, nếu không giao diện mất tên
    -- phòng khám mà không có một dòng log nào giải thích.
    SELECT string_agg(col, ', ') INTO missing
      FROM unnest(ARRAY['id', 'code', 'name', 'timezone', 'is_active']) AS col
     WHERE NOT has_column_privilege('authenticated', 'public.clinic', col, 'SELECT');
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION
            'authenticated mất quyền đọc các cột danh tính của clinic: % '
            '(current-staff.ts sẽ im lặng trả null trên mọi trang)', missing;
    END IF;

    -- 4.6 Không còn credential nào sót lại trong settings.
    IF EXISTS (
        SELECT 1 FROM public.clinic
         WHERE settings -> 'pos'
               ?| ARRAY['retailer', 'client_id', 'client_secret', 'branch_id']
    ) THEN
        RAISE EXCEPTION 'vẫn còn credential POS trong clinic.settings';
    END IF;
END
$verify$;
