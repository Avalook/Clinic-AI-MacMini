-- =====================================================================
-- reset_clinical_data.sql — ĐƯA SUPABASE VỀ "TRỐNG DATA BỆNH NHÂN"
-- =====================================================================
-- MỤC ĐÍCH (quyết định 04/06): tạm KHÔNG dùng data chuẩn hoá từ Notion
-- clone / Excel nữa. Dashboard chạy như MVP NHẬP TAY (thay việc nhập tay
-- Notion + Excel). Script này xoá sạch DATA KHÁCH/BỆNH NHÂN nhưng GIỮ
-- nguyên schema + cấu hình gốc phòng khám.
--
-- CÁCH CHẠY: dán toàn bộ file này vào Supabase SQL Editor → Run.
-- (Một transaction; nếu lỗi sẽ rollback, không để DB dở dang.)
--
-- ✅ GIỮ LẠI (cấu hình phòng khám — dashboard cần để chạy):
--      clinic_location, service_type, booking_channel,
--      staff, staff_capability, work_session,
--      work_session_staff, schema_migrations, event_log (nhật ký audit).
--
-- 🗑️ XOÁ SẠCH (data khách/bệnh nhân — sẽ nhập tay lại từ dashboard):
--      patient (+ CASCADE: patient_contact_channel, patient_medical_profile,
--               pregnancy, patient_next_of_kin, ultrasound_record,
--               visit, clinical_record, visit_amendment, lab_result,
--               prescription, appointment, mpi_merge_queue, staff_task …),
--      cskh_action, cskh_log, service_log,
--      work_roster (lịch trực tuần — bản clone là demo; để trống cho nhập tay).
--
-- ♻️ ĐẢO NGƯỢC ĐƯỢC: muốn lấy lại bộ data demo (5.5k BN) chỉ cần chạy lại
--      sync (xem CHỐT CHẶN bên dưới) — script này KHÔNG phá huỷ gì
--      không tái tạo được.
--
-- ⚠️ CHỐT CHẶN QUAN TRỌNG: SAU KHI phòng khám bắt đầu nhập THẬT, TUYỆT ĐỐI
--      KHÔNG chạy lại `scripts/data_import/sync_to_supabase.py` — nó
--      TRUNCATE rồi nạp lại data Notion = XOÁ data nhập tay. Đã thêm guard
--      env `CLINIC_ALLOW_NOTION_SYNC=1` để chặn lỡ tay (sync từ chối chạy
--      nếu thiếu biến này).
--
-- An toàn append-only: bảng patient/appointment có guard migration 033
-- (chặn TRUNCATE) → mở khoá CÓ KIỂM SOÁT trong đúng transaction này bằng
-- `app.allow_hard_delete='on'` (đúng cơ chế sync dùng). visit_amendment chỉ
-- chặn UPDATE/DELETE, KHÔNG chặn TRUNCATE → CASCADE chạy bình thường.
-- =====================================================================

BEGIN;

-- Mở khoá guard append-only (patient/appointment) CHỈ trong transaction này.
SET LOCAL app.allow_hard_delete = 'on';

-- Xoá theo CASCADE (Postgres tự gỡ mọi bảng con tham chiếu các bảng dưới).
-- Danh sách mirror sync_to_supabase._truncate_targets + 1 bảng log (cskh_log).
TRUNCATE TABLE
  cskh_action,
  cskh_log,
  service_log,
  prescription,
  appointment,
  lab_result,
  clinical_record,
  visit,
  patient
RESTART IDENTITY CASCADE;

-- Lịch trực tuần (work_roster): bản clone là DEMO. Để TRỐNG cho mỗi vai trò tự
-- đăng ký ca (/schedule) + quản lý xếp (/schedule/edit) ghi vào. Bỏ dòng này nếu
-- muốn GIỮ lịch trực.
TRUNCATE TABLE work_roster RESTART IDENTITY;

COMMIT;

-- ---------------------------------------------------------------------
-- KIỂM TRA SAU KHI CHẠY (nên thấy data = 0, cấu hình > 0):
-- ---------------------------------------------------------------------
SELECT 'patient'        AS bang, count(*) AS so_dong FROM patient
UNION ALL SELECT 'appointment',          count(*) FROM appointment
UNION ALL SELECT 'visit',                count(*) FROM visit
UNION ALL SELECT 'clinical_record',      count(*) FROM clinical_record
UNION ALL SELECT 'lab_result',           count(*) FROM lab_result
UNION ALL SELECT 'prescription',         count(*) FROM prescription
UNION ALL SELECT 'cskh_action',          count(*) FROM cskh_action
UNION ALL SELECT 'service_log',          count(*) FROM service_log
UNION ALL SELECT 'patient_contact_channel', count(*) FROM patient_contact_channel
UNION ALL SELECT 'work_roster',          count(*) FROM work_roster
UNION ALL SELECT '— GIỮ: staff —',       count(*) FROM staff
UNION ALL SELECT '— GIỮ: service_type —',count(*) FROM service_type
UNION ALL SELECT '— GIỮ: booking_channel —', count(*) FROM booking_channel
UNION ALL SELECT '— GIỮ: clinic_location —', count(*) FROM clinic_location
ORDER BY bang;
