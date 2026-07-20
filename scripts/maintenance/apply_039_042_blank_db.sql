-- ============================================================
-- ÁP 039–042 trên DB TRỐNG (data=0) — vá 8 bảng RLS-rỗng + visit UNIQUE
-- + birth_year + CSKH_CONFIRMED + tìm kiếm bỏ dấu.
-- Idempotent (IF NOT EXISTS / DROP IF EXISTS) — chạy lại an toàn.
-- Cách dùng: dán TOÀN BỘ file này vào Supabase SQL Editor → Run.
-- ============================================================

-- ===================== 20260603_039_visit_unique_and_unaccent_search.sql =====================
-- 039 — Vá nhất quán dữ liệu (Đợt C audit 03/06):
--   1) Chống TRÙNG visit theo lịch hẹn (double-visit race khi ĐD + bác sĩ ghi
--      cùng lúc). Code clinical-record đã bắt 23505 → tìm lại visit.
--   2) Tìm kiếm BN BỎ DẤU ("tuyen" ra "Tuyền").
--
-- An toàn để chạy lại (IF NOT EXISTS). KHÔNG xoá/sửa data.

-- ───────────────────────────────────────────────────────────────────────────
-- 1) UNIQUE visit theo appointment_id (partial — bỏ qua visit nhập cũ NULL).
--    ⚠️ Nếu data hiện có visit TRÙNG appointment_id, lệnh dưới sẽ LỖI. Kiểm tra:
--       SELECT appointment_id, count(*) FROM visit
--       WHERE appointment_id IS NOT NULL GROUP BY 1 HAVING count(*) > 1;
--    Nếu có → giữ visit mới nhất, xoá/gộp bản cũ rồi chạy lại.
CREATE UNIQUE INDEX IF NOT EXISTS uq_visit_appointment_id
  ON visit (appointment_id)
  WHERE appointment_id IS NOT NULL;

-- ───────────────────────────────────────────────────────────────────────────
-- 2) Tìm kiếm bỏ dấu cho patient.full_name.
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- unaccent() là STABLE → không dùng được cho cột GENERATED/index. Bọc IMMUTABLE
-- với từ điển cố định.
CREATE OR REPLACE FUNCTION f_unaccent(text)
  RETURNS text
  LANGUAGE sql
  IMMUTABLE
  PARALLEL SAFE
  STRICT
AS $func$ SELECT unaccent('unaccent', $1) $func$;

-- Cột tên KHÔNG DẤU + thường (đ→d xử lý riêng vì unaccent không đổi đ).
ALTER TABLE patient
  ADD COLUMN IF NOT EXISTS full_name_unaccent text
  GENERATED ALWAYS AS (
    lower(replace(replace(f_unaccent(full_name), 'đ', 'd'), 'Đ', 'D'))
  ) STORED;

-- Index trigram cho ILIKE '%...%'.
CREATE INDEX IF NOT EXISTS idx_patient_full_name_unaccent
  ON patient USING gin (full_name_unaccent gin_trgm_ops);

-- ===================== 20260604_040_patient_birth_year.sql =====================
-- Migration 040: cột `patient.birth_year` cho feedback dashboard (Thu Lê 04/06).
-- Nhiều BN chỉ nhớ NĂM sinh (không nhớ ngày/tháng) — feedback B5#4 "tự động năm".
-- Khi chỉ có năm: lưu `birth_year`, để `date_of_birth` NULL. Hiển thị ưu tiên
-- date_of_birth, fallback birth_year. NULLABLE + additive + re-runnable
-- (ADD COLUMN IF NOT EXISTS) → KHÔNG phá dữ liệu sẵn có.
--
-- Code dashboard chạy được CẢ KHI chưa apply migration này (POST /api/patients
-- bắt lỗi 42703 → fallback lưu date_of_birth = `${năm}-01-01`). Apply migration
-- để lưu năm CHÍNH XÁC + hiển thị đúng "chỉ năm".

BEGIN;

ALTER TABLE patient
  ADD COLUMN IF NOT EXISTS birth_year SMALLINT;

ALTER TABLE patient DROP CONSTRAINT IF EXISTS patient_birth_year_check;
ALTER TABLE patient ADD CONSTRAINT patient_birth_year_check
  CHECK (birth_year IS NULL OR (birth_year BETWEEN 1900 AND 2100));

COMMENT ON COLUMN patient.birth_year IS
  'Năm sinh khi BN không nhớ ngày/tháng (feedback B5#4). date_of_birth NULL khi chỉ có năm.';

COMMIT;

-- ===================== 20260604_041_appointment_cskh_confirmed.sql =====================
-- Migration 041: add CSKH_CONFIRMED to appointment.status.
--
-- Two-step confirmation. CSKH confirms WITH THE PATIENT (SCHEDULED →
-- CSKH_CONFIRMED) but the appointment still awaits the DOCTOR's own decision:
--   doctor confirm:  SCHEDULED | CSKH_CONFIRMED → CONFIRMED
--   doctor reject:   SCHEDULED | CSKH_CONFIRMED → DOCTOR_DECLINED
-- so a CSKH-confirmed slot keeps showing in the doctor's "Chờ xác nhận" column
-- (with Confirm / Reject), and a doctor reject surfaces to CSKH as cancelled.
--
-- The status CHECK is the inline column constraint auto-named
-- `appointment_status_check` (`<table>_<column>_check`). Re-runnable: drop by
-- that name, re-add the widened set.

ALTER TABLE appointment DROP CONSTRAINT IF EXISTS appointment_status_check;
ALTER TABLE appointment ADD CONSTRAINT appointment_status_check
  CHECK (status IN (
    'SCHEDULED','CSKH_CONFIRMED','CONFIRMED','CHECKED_IN','COMPLETED',
    'NO_SHOW','CANCELLED','DOCTOR_DECLINED'
  ));

-- ===================== 20260604_042_rls_dashboard_reads.sql =====================
-- Migration 042: vá NỐT lứa bảng bị "RLS ENABLED nhưng KHÔNG có policy" → mọi
-- read qua PostgREST (authenticated) im lặng trả 0 dòng. Giống hệt lỗi migration
-- 032 đã vá cho staff/service_type/clinic_location/pregnancy, nhưng các bảng dưới
-- (tạo ở migration 029/030/031/035/038… hoặc bật RLS tay trên Supabase) bị SÓT.
--
-- TRIỆU CHỨNG đã xác minh trên DB thật (read-only):
--   cskh_action  RLS=on, policy SELECT = 0  → board "Nhật ký CSKH" rỗng dù có data
--   service_log  RLS=on, policy SELECT = 0  → board "Dịch vụ" rỗng
--   staff_task   RLS=on, policy SELECT = 0  → "Việc đang chờ làm" luôn = 0
-- (data VẪN được ghi đúng qua service-role; chỉ ĐỌC bằng authenticated bị chặn →
--  trông như "các bảng không đồng bộ với nhau".)
--
-- Mở SELECT CHỈ cho role `authenticated` (phiên đăng nhập phòng khám) — anon
-- (internet, chưa login) VẪN không đọc được. Re-runnable: DROP POLICY IF EXISTS.

BEGIN;

-- cskh_action (Nhật ký CSKH — board /tasks bảng 2)
ALTER TABLE cskh_action ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cskh_action_select_authenticated ON cskh_action;
CREATE POLICY cskh_action_select_authenticated
  ON cskh_action FOR SELECT TO authenticated USING (true);

-- service_log (Dịch vụ — board hàng đợi dịch vụ)
ALTER TABLE service_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_log_select_authenticated ON service_log;
CREATE POLICY service_log_select_authenticated
  ON service_log FOR SELECT TO authenticated USING (true);

-- staff_task (Việc đang chờ làm — stat card Trang chủ + board task)
ALTER TABLE staff_task ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff_task_select_authenticated ON staff_task;
CREATE POLICY staff_task_select_authenticated
  ON staff_task FOR SELECT TO authenticated USING (true);

-- prescription (Kê thuốc — board kê thuốc + hồ sơ lâm sàng)
ALTER TABLE prescription ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS prescription_select_authenticated ON prescription;
CREATE POLICY prescription_select_authenticated
  ON prescription FOR SELECT TO authenticated USING (true);

-- patient_medical_profile (tiền sử BN — hồ sơ lâm sàng bác sĩ)
ALTER TABLE patient_medical_profile ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS patient_medical_profile_select_authenticated ON patient_medical_profile;
CREATE POLICY patient_medical_profile_select_authenticated
  ON patient_medical_profile FOR SELECT TO authenticated USING (true);

-- work_session (ca làm việc — tham chiếu lịch)
ALTER TABLE work_session ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS work_session_select_authenticated ON work_session;
CREATE POLICY work_session_select_authenticated
  ON work_session FOR SELECT TO authenticated USING (true);

-- event_log (nhật ký audit — 1 màn đọc lại)
ALTER TABLE event_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS event_log_select_authenticated ON event_log;
CREATE POLICY event_log_select_authenticated
  ON event_log FOR SELECT TO authenticated USING (true);

-- work_session_staff (số nhân sự mỗi ca — cột "Số staff" của lịch/ca trực; lỗi
-- audit nêu "Số staff lặng lẽ về 0" khi bật RLS mà thiếu policy).
ALTER TABLE work_session_staff ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS work_session_staff_select_authenticated ON work_session_staff;
CREATE POLICY work_session_staff_select_authenticated
  ON work_session_staff FOR SELECT TO authenticated USING (true);

COMMIT;

-- ===================== tracking (schema_migrations) =====================
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_021_rls_visit.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_021_rls_visit.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_022_rls_clinical_record.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_022_rls_clinical_record.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_023_rls_lab_result.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_023_rls_lab_result.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_024_rls_appointment.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_024_rls_appointment.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_025_staff_auth_link.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_025_staff_auth_link.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_026_create_booking_channel.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_026_create_booking_channel.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_027_create_patient_contact_channel.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_027_create_patient_contact_channel.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_028_create_patient_next_of_kin.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_028_create_patient_next_of_kin.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_029_create_cskh_action.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_029_create_cskh_action.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_030_create_service_log.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_030_create_service_log.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260529_031_create_prescription.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260529_031_create_prescription.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260530_032_rls_authenticated_reads.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260530_032_rls_authenticated_reads.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260601_034_appointment_doctor_declined.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260601_034_appointment_doctor_declined.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260603_038_patient_admin_fields.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260603_038_patient_admin_fields.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260603_039_visit_unique_and_unaccent_search.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260603_039_visit_unique_and_unaccent_search.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260604_040_patient_birth_year.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260604_040_patient_birth_year.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260604_041_appointment_cskh_confirmed.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260604_041_appointment_cskh_confirmed.sql');
INSERT INTO schema_migrations(filename, applied_at) SELECT '20260604_042_rls_dashboard_reads.sql', now() WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='20260604_042_rls_dashboard_reads.sql');
