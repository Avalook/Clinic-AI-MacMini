-- =====================================================================
-- clear_work_roster.sql — XOÁ RIÊNG data "Lịch làm việc" (work_roster)
-- =====================================================================
-- MỤC ĐÍCH: bản lịch trực clone hiện tại là DEMO (không phải data thật của
-- phòng khám). Bảng "Lịch làm việc · tuần này" trên trang chủ + trang
-- /schedule đọc thẳng từ work_roster → muốn để TRỐNG cho mỗi vai trò tự đăng
-- ký ca (/schedule) và quản lý tự xếp (/schedule/edit) nhập tay.
--
-- KHÁC reset_clinical_data.sql: file này CHỈ xoá work_roster, KHÔNG đụng
-- patient/appointment/... → an toàn khi phòng khám ĐÃ bắt đầu nhập tay BN.
--
-- CÁCH CHẠY: dán vào Supabase SQL Editor → Run. (work_roster không có guard
-- append-only nên TRUNCATE chạy trực tiếp, không cần app.allow_hard_delete.)
--
-- ♻️ Sau khi chạy: bảng "Lịch làm việc" hiện lưới TRỐNG (toàn "—"); nhập lại
--    qua /schedule (tự đăng ký) hoặc /schedule/edit (quản lý xếp).
-- =====================================================================

TRUNCATE TABLE work_roster RESTART IDENTITY;

-- Kiểm tra (nên thấy 0):
SELECT 'work_roster' AS bang, count(*) AS so_dong FROM work_roster;
