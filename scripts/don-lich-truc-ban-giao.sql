-- Xoá LỊCH LÀM VIỆC trên prod — phần mà `don-prod-truoc-ban-giao.sql` cố tình
-- giữ lại theo phạm vi chốt 14/08. Tuyền đổi ý 17/08: bàn giao là bàn giao
-- trắng, quản lý sẽ tự xếp ca từ đầu — nên xoá nốt.
--
-- Chạy SAU `don-prod-truoc-ban-giao.sql` (để appointment đã trống, không còn
-- gì trỏ vào ca trực). Cùng kiểu: một giao dịch, tắt trigger trong phạm vi
-- giao dịch, lỗi giữa chừng là cuộn lại toàn bộ.
--
--   docker cp scripts/don-lich-truc-ban-giao.sql clinicai_db:/tmp/
--   docker exec clinicai_db psql -U postgres -d postgres \
--       -v ON_ERROR_STOP=1 -f /tmp/don-lich-truc-ban-giao.sql

BEGIN;

SET LOCAL session_replication_role = 'replica';

TRUNCATE roster_week, work_roster, work_session, work_session_staff CASCADE;

COMMIT;

-- Đếm lại: nhóm đầu phải về 0, nhóm GIU phải còn nguyên.
SELECT 'benh_nhan' AS bang, count(*) FROM patient
UNION ALL SELECT 'lich_hen', count(*) FROM appointment
UNION ALL SELECT 'so_su_kien', count(*) FROM event_log
UNION ALL SELECT 'ca_truc', count(*) FROM work_roster
UNION ALL SELECT 'tuan_truc', count(*) FROM roster_week
UNION ALL SELECT 'GIU: nhan_su', count(*) FROM staff
UNION ALL SELECT 'GIU: dich_vu', count(*) FROM service_type
UNION ALL SELECT 'GIU: kho_thuoc', count(*) FROM drug_batch
ORDER BY 1;
