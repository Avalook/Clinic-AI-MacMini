-- Minimal Supabase Auth surface for validating public migrations in a disposable
-- stock-Postgres container. Never run this fixture against a Supabase project.

DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
    END IF;
END
$roles$;

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id uuid PRIMARY KEY
);

-- PHẢI GIỐNG HỆT BẢN THẬT, KHÔNG ĐƯỢC RÚT GỌN.
--
-- Bản cũ ở đây chỉ đọc `request.jwt.claim.sub`. PostgREST v12 KHÔNG đặt GUC đó
-- nữa — nó chỉ đặt `request.jwt.claims` (JSON). Trên database thật của Supabase
-- auth.uid() đọc cả hai, nên không ai thấy gì.
--
-- Nhưng script dựng staging nạp chính file này, nên staging thừa hưởng bản rút
-- gọn: auth.uid() luôn NULL → current_staff_id() NULL → current_clinic_ids()
-- rỗng → MỌI lượt đọc qua PostgREST trả về `[]` cho mọi tài khoản. Không lỗi,
-- không cảnh báo, chỉ là danh sách trống — trông y hệt một phòng khám chưa có
-- dữ liệu. Đo ngày 07/08/2026: prod trả về hàng, staging trả `[]`, cùng ảnh
-- PostgREST v12.2.3, khác đúng hàm này.
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $function$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
    )::uuid
$function$;

-- ---------------------------------------------------------------------------
-- Publication realtime
-- ---------------------------------------------------------------------------
-- Mọi project Supabase đều có sẵn `supabase_realtime`; Postgres thường thì
-- không. Thiếu nó, migration 20260803000003 dừng ngay ở dòng
-- `ALTER PUBLICATION supabase_realtime ADD TABLE public.work_item` và cả chuỗi
-- migration đứt — đúng chỗ CI đang đỏ.
--
-- Đây là khoảng trống của FIXTURE, không phải lỗi của migration: trên Supabase
-- câu đó chạy đúng. Vá ở fixture để môi trường thử giống môi trường thật, thay
-- vì sửa một migration đã nằm trên production.
DO $publication$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime')
    THEN
        CREATE PUBLICATION supabase_realtime;
    END IF;
END
$publication$;
