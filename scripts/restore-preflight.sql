-- CHẠY CÁI NÀY TRƯỚC KHI NẠP BẢN SAO LƯU. Không chạy thì bản lưu không nạp được.
--
-- VÌ SAO CẦN. `pg_dump --schema=public` KHÔNG mang theo lệnh CREATE EXTENSION —
-- extension là đối tượng cấp database, không thuộc schema được dump. Nạp thẳng
-- bản lưu vào một database trắng sẽ hỏng ngay ở bảng `patient` (cột sinh gọi
-- f_unaccent) rồi kéo theo hàng chục lỗi "relation does not exist" phía sau.
--
-- Kiểm thật ngày 04/08/2026 bằng cách khôi phục bản lưu 02:00 vào Postgres 17
-- trắng: không có file này thì 60 lỗi và không có bảng nào dựng được; có file
-- này thì dựng lại đủ 64 bảng, số dòng khớp production từng bảng.
--
-- CHÚ Ý VỀ SCHEMA CỦA EXTENSION. Trên production, `unaccent`, `pg_trgm` và
-- `btree_gist` nằm ở `public` (không phải `extensions` như mặc định Supabase).
-- Đặt sai schema thì `gin_trgm_ops` và `f_unaccent` không giải được tên, và lỗi
-- sẽ trông y hệt lỗi thiếu extension — mất thời gian đi tìm sai chỗ.
--
-- Dùng:
--   psql "$DSN_MOI" -f scripts/restore-preflight.sql
--   gzcat clinicai_production_*_YYYYMMDD_*.sql.gz      | psql "$DSN_MOI"
--   gzcat clinicai_production_*_YYYYMMDD_*_auth.sql.gz | psql "$DSN_MOI"

CREATE EXTENSION IF NOT EXISTS unaccent   WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pg_trgm    WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;

-- Ba cái này Supabase đặt ở `extensions`; tạo schema trước cho khỏi phụ thuộc
-- thứ tự khi khôi phục vào một Postgres thường.
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto    WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;

-- Các vai mà chính sách RLS nhắc tên. Thiếu chúng thì mọi lệnh GRANT/POLICY
-- trong bản lưu đều hỏng, và database khôi phục xong sẽ KHÔNG có RLS — tức là
-- nhìn thì đủ dữ liệu mà thực chất đang mở toang.
DO $$BEGIN CREATE ROLE anon;          EXCEPTION WHEN duplicate_object THEN NULL; END$$;
DO $$BEGIN CREATE ROLE authenticated; EXCEPTION WHEN duplicate_object THEN NULL; END$$;
DO $$BEGIN CREATE ROLE service_role;  EXCEPTION WHEN duplicate_object THEN NULL; END$$;

-- Chỉ cần khi khôi phục vào Postgres THƯỜNG. Project Supabase mới đã có sẵn
-- schema `auth` KÈM các bảng của nó — và bản lưu auth là DATA-ONLY (chỉ có
-- COPY, không có CREATE TABLE), nên nó chỉ nạp được vào nơi đã có sẵn bảng.
-- Nói cách khác: khôi phục đầy đủ CẢ ĐĂNG NHẬP thì đích phải là một project
-- Supabase mới, không phải một Postgres tự dựng.
CREATE SCHEMA IF NOT EXISTS auth;

DO $verify$
BEGIN
    PERFORM set_config('search_path', '', false);
    IF public.f_unaccent('Nguyễn Thị Hoà') IS DISTINCT FROM 'Nguyen Thi Hoa' THEN
        RAISE EXCEPTION 'f_unaccent chưa sẵn sàng — bản lưu sẽ hỏng ở bảng patient';
    END IF;
EXCEPTION WHEN undefined_function THEN
    -- Bình thường: f_unaccent nằm TRONG bản lưu, chưa nạp thì chưa có.
    NULL;
END
$verify$;
