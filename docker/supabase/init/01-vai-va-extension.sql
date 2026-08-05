-- Nền của một Postgres "kiểu Supabase" — chạy MỘT LẦN khi volume còn trống.
--
-- Supabase cloud không phải Postgres trần: nó dựng sẵn một bộ vai, schema và
-- hàm mà toàn bộ RLS của dự án đang đứng lên trên. Tự dựng thì phải tự khai,
-- và khai THIẾU thì lỗi hiện ra ở chỗ xa nhất — một policy im lặng cho qua.
--
-- Ba nhóm, theo đúng thứ tự phụ thuộc:
--   1. vai      anon / authenticated / service_role / authenticator
--   2. schema   auth · extensions · realtime  (GoTrue sẽ tự tạo BẢNG trong auth)
--   3. hàm      auth.uid() · auth.role() · auth.jwt()
--
-- Cái thứ 3 là chỗ dễ quên nhất: nó KHÔNG đến từ GoTrue. GoTrue chỉ quản lý
-- bảng người dùng; `auth.uid()` là hàm SQL của Supabase đọc claim trong JWT mà
-- PostgREST đặt vào phiên. Thiếu nó thì `current_staff_id()` đổ, và mọi policy
-- gọi nó cũng đổ.

-- ---------------------------------------------------------------------------
-- 1. Vai
-- ---------------------------------------------------------------------------
-- NOLOGIN cho ba vai đầu: chúng không phải tài khoản đăng nhập mà là DANH TÍNH
-- mà `authenticator` chuyển sang sau khi đọc JWT. Đây là mô hình của PostgREST.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
    -- BYPASSRLS: backend chạy bằng vai này và tự mang clinic_id trong MỌI câu
    -- SQL. Đó là giao kèo mà `scripts/tests/tenant-scope-audit.py` canh giữ —
    -- bỏ qua RLS mà quên bộ lọc là đọc chéo phòng khám.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
    END IF;
    -- Vai DUY NHẤT thật sự đăng nhập được. PostgREST nối bằng nó rồi
    -- `SET LOCAL ROLE` sang một trong ba vai trên tuỳ claim trong JWT.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator') THEN
        CREATE ROLE authenticator LOGIN NOINHERIT PASSWORD 'thay-o-buoc-sau';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_auth_admin') THEN
        CREATE ROLE supabase_auth_admin LOGIN NOINHERIT CREATEROLE
            PASSWORD 'thay-o-buoc-sau';
    END IF;
    -- Realtime nối bằng vai NÀY, không phải `postgres`. Cần REPLICATION vì nó
    -- đọc WAL qua logical replication — thiếu quyền ấy thì nó nối được nhưng
    -- không nhận sự kiện nào, hỏng im lặng.
    --
    -- Quên tạo hẳn thì triệu chứng là websocket trả 502 và log ghi
    -- "password authentication failed for user supabase_admin". Đã gặp thật.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_admin') THEN
        CREATE ROLE supabase_admin LOGIN NOINHERIT CREATEROLE CREATEDB
            REPLICATION BYPASSRLS PASSWORD 'thay-o-buoc-sau';
    END IF;
END
$$;

GRANT anon, authenticated, service_role TO authenticator;

-- ---------------------------------------------------------------------------
-- 2. Schema
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION supabase_auth_admin;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS realtime;

GRANT USAGE ON SCHEMA public     TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA extensions TO anon, authenticated, service_role;
-- `auth` mở USAGE để `auth.uid()` gọi được từ policy, nhưng KHÔNG cấp quyền
-- trên bảng: không ai đọc được danh sách người dùng qua PostgREST.
GRANT USAGE ON SCHEMA auth       TO anon, authenticated, service_role;

-- Realtime tự tạo bảng của nó trong schema `realtime`, nên phải làm chủ schema.
ALTER SCHEMA realtime OWNER TO supabase_admin;
GRANT ALL   ON SCHEMA realtime TO supabase_admin;
GRANT USAGE ON SCHEMA public   TO supabase_admin;

-- ---------------------------------------------------------------------------
-- 3. Extension
-- ---------------------------------------------------------------------------
-- CHỖ ĐẶT KHÁC PROD, CÓ CHỦ Ý VÀ ĐÃ ĐO. Trên Supabase cloud, pgcrypto và
-- uuid-ossp nằm ở schema `extensions`; chuỗi migration của dự án lại tạo chúng
-- ở `public`. Bản đo drift (Giai đoạn 0) đếm ra 35 "hàm thiếu" chỉ vì khác chỗ
-- đặt này, không phải thiếu thật.
--
-- Ở đây tạo TRƯỚC ở `extensions` để khớp thói quen Supabase, và `search_path`
-- bên dưới làm cho cả hai cách gọi đều chạy. Migration sau đó dùng
-- `CREATE EXTENSION IF NOT EXISTS` nên sẽ bỏ qua, không tạo bản thứ hai.
CREATE EXTENSION IF NOT EXISTS pgcrypto    WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;
-- Ba cái này chuỗi migration đặt ở `public` và code gọi không kèm schema —
-- giữ nguyên chỗ đó.
CREATE EXTENSION IF NOT EXISTS pg_trgm    WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS unaccent   WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;

-- Để `gen_random_uuid()` và `digest()` gọi được mà không cần viết
-- `extensions.` ở mọi nơi — đúng như trên Supabase cloud.
ALTER DATABASE postgres SET search_path TO "$user", public, extensions;

-- ---------------------------------------------------------------------------
-- 4. auth.jwt() — và VÌ SAO KHÔNG tạo auth.uid() / auth.role() ở đây
-- ---------------------------------------------------------------------------
-- GoTrue TỰ TẠO `auth.uid()` và `auth.role()` trong migration đầu tiên của nó,
-- bằng vai `supabase_auth_admin`. Tạo trước bằng `postgres` thì hai hàm ấy
-- thuộc sở hữu của postgres, và GoTrue không `CREATE OR REPLACE` đè được:
--
--     fatal: running db migrations: ... ERROR: must be owner of function uid
--
-- Nó lặp vô hạn, container khởi động lại mãi. Đã gặp thật khi dựng bộ này.
--
-- Nên để GoTrue tạo trước, rồi bước nạp schema (`scripts/supabase-local-nap.sh`)
-- sẽ thay thân hàm bằng bản đọc được CẢ HAI dạng claim. Superuser thay được mà
-- không đổi chủ sở hữu, nên lần nâng cấp GoTrue sau vẫn chạy.
--
-- `auth.jwt()` thì GoTrue KHÔNG tạo — không ai tranh chấp, tạo luôn ở đây.
CREATE OR REPLACE FUNCTION auth.jwt()
RETURNS jsonb
LANGUAGE sql STABLE
AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim', true), ''),
        nullif(current_setting('request.jwt.claims', true), '')
    )::jsonb
$$;

ALTER FUNCTION auth.jwt() OWNER TO supabase_auth_admin;
GRANT EXECUTE ON FUNCTION auth.jwt() TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 5. Publication cho Realtime
-- ---------------------------------------------------------------------------
-- Supabase cloud dựng sẵn publication `supabase_realtime`; Postgres trần thì
-- không. Chuỗi migration gọi `ALTER PUBLICATION supabase_realtime ADD TABLE …`
-- ở nhiều chỗ, và câu ấy KHÔNG có dạng `IF NOT EXISTS` — thiếu publication là
-- migration đổ giữa chừng:
--
--     ERROR: publication "supabase_realtime" does not exist
--
-- Đã gặp thật ở 20260803000003 khi dựng bộ này. Cùng lý do mà
-- `supabase/tests/bootstrap_plain_postgres.sql` phải tạo nó cho CI.
--
-- Tạo RỖNG: migration sẽ tự thêm từng bảng cần phát sự kiện. Tạo kèm
-- `FOR ALL TABLES` là phát cả những bảng không ai nghe, tốn WAL vô ích.
DO $publication$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime')
    THEN
        CREATE PUBLICATION supabase_realtime;
    END IF;
END
$publication$;

-- ---------------------------------------------------------------------------
-- 6. Quyền mặc định cho bảng sinh sau
-- ---------------------------------------------------------------------------
-- Chuỗi migration tự cấp quyền cho từng bảng (20260730000008 quét pg_policy rồi
-- cấp lại). Nhưng `service_role` phải đọc/ghi được MỌI bảng kể cả bảng chưa có
-- policy nào — backend là đường ghi duy nhất kể từ ADR-0012.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO service_role;

DO $$
BEGIN
    RAISE NOTICE 'nền Supabase: vai + schema + extension + auth.uid() đã sẵn sàng';
END
$$;
