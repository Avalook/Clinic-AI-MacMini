-- KIỂM DỮ LIỆU PROD, LƯỢT 2 — CHỈ ĐỌC, CHỈ TRẢ CON SỐ (21/10/2026).
-- Tách nhỏ 3 bất biến khác 0 ở lượt 1 (D13=46, D14=460, D15=51).
--
-- D14 lượt 1 ĐẾM OAN: check-out không đổi visit.status, chỉ ghi closed_at
-- (checkout_service.py — FINALIZED là bác sĩ KÝ bệnh án, việc riêng). Nên lượt
-- đã check-out mà bác sĩ chưa ký vẫn OPEN/IN_PROGRESS. Treo THẬT = chưa check-out.
--
-- Chạy:
--   ssh clinic-vps-moi 'docker exec -i clinicai_db psql -U postgres -d postgres -X -q -t -A' < docs/ban-do/hieu/kiem-du-lieu-prod-2.sql

\set ON_ERROR_STOP off

-- D14a Lượt treo THẬT: chưa check-out (closed_at rỗng), quá 2 ngày
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D14a','so_dong',(SELECT count(*) FROM visit WHERE status IN ('OPEN','IN_PROGRESS') AND closed_at IS NULL AND created_at < now() - interval '2 days'))::text; ROLLBACK;
-- D14b Đã check-out nhưng bác sĩ chưa ký bệnh án
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D14b','so_dong',(SELECT count(*) FROM visit WHERE status IN ('OPEN','IN_PROGRESS') AND closed_at IS NOT NULL AND created_at < now() - interval '2 days'))::text; ROLLBACK;
-- D14a tách: bán lẻ quầy thuốc (ban_le) hay lượt khám, và trạng thái
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D14a_loai','so',(SELECT coalesce(jsonb_object_agg(k, n), '{}'::jsonb) FROM (SELECT (CASE WHEN ban_le THEN 'ban_le ' ELSE 'kham ' END) || status AS k, count(*) AS n FROM visit WHERE status IN ('OPEN','IN_PROGRESS') AND closed_at IS NULL AND created_at < now() - interval '2 days' GROUP BY 1) t))::text; ROLLBACK;
-- D14a: lượt khám (không bán lẻ) mà đã có thu tiền — tức khách đã qua quầy thu nhưng chưa check-out
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D14a_da_thu','so_dong',(SELECT count(*) FROM visit v WHERE v.status IN ('OPEN','IN_PROGRESS') AND v.closed_at IS NULL AND NOT coalesce(v.ban_le,false) AND v.created_at < now() - interval '2 days' AND EXISTS (SELECT 1 FROM payment_cycle c WHERE c.visit_id = v.visit_id AND c.status = 'PAID')))::text; ROLLBACK;
-- D14a theo tháng tạo (treo mới hay treo cũ)
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D14a_thang','so',(SELECT coalesce(jsonb_object_agg(thang, n), '{}'::jsonb) FROM (SELECT to_char(created_at AT TIME ZONE 'Asia/Ho_Chi_Minh','YYYY-MM') AS thang, count(*) AS n FROM visit WHERE status IN ('OPEN','IN_PROGRESS') AND closed_at IS NULL AND created_at < now() - interval '2 days' GROUP BY 1) t))::text; ROLLBACK;
-- D14a theo cơ sở (chỉ số đếm theo tên cơ sở)
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D14a_co_so','so',(SELECT coalesce(jsonb_object_agg(coalesce(l.name,'(không cơ sở)'), n), '{}'::jsonb) FROM (SELECT location_id, count(*) AS n FROM visit WHERE status IN ('OPEN','IN_PROGRESS') AND closed_at IS NULL AND created_at < now() - interval '2 days' GROUP BY 1) t LEFT JOIN clinic_location l ON l.id = t.location_id))::text; ROLLBACK;
-- D15 theo tháng hẹn + kênh đặt (lịch quá hạn vẫn 'đã xác nhận')
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D15_thang','so',(SELECT coalesce(jsonb_object_agg(k, n), '{}'::jsonb) FROM (SELECT to_char(slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh','YYYY-MM') || ' ' || coalesce(booking_channel,'?') AS k, count(*) AS n FROM appointment WHERE status = 'CONFIRMED' AND slot_start < now() - interval '1 day' GROUP BY 1) t))::text; ROLLBACK;
-- Các trạng thái lịch đang có (có trạng thái 'không đến' để đóng lịch không)
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','lich_trang_thai','so',(SELECT coalesce(jsonb_object_agg(status, n), '{}'::jsonb) FROM (SELECT status, count(*) AS n FROM appointment GROUP BY 1) t))::text; ROLLBACK;
-- D13 theo cơ sở (lô còn tồn khác đơn vị bán)
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D13_co_so','so',(SELECT coalesce(jsonb_object_agg(coalesce(l.name,'(không cơ sở)'), n), '{}'::jsonb) FROM (SELECT b.location_id, count(*) AS n FROM drug_batch b JOIN drug_catalog c ON c.id = b.drug_catalog_id WHERE c.don_vi_ban IS NOT NULL AND lower(btrim(b.unit)) <> lower(btrim(c.don_vi_ban)) AND b.quantity_on_hand > 0 GROUP BY 1) t LEFT JOIN clinic_location l ON l.id = t.location_id))::text; ROLLBACK;
