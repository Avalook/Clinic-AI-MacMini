-- KIỂM DỮ LIỆU PROD, LƯỢT 3 — CHỈ ĐỌC, CHỈ TRẢ CON SỐ (21/10/2026).
-- "Bệnh án chưa ký" theo LUẬT HIỆN TẠI: bước Ký bệnh án đã nghỉ 23/09/2026
-- (clinical_sign.py — 410); mốc khoá là bác sĩ bấm Hoàn tất / Khám xong =
-- visit.exam_completed_at (moc_kham_xong.py; dữ liệu cũ: lịch hẹn COMPLETED).
-- Nên 435 lượt "chưa FINALIZED" ở lượt 2 KHÔNG phải số chưa ký. Số thật dưới đây.
--
-- Chạy:
--   ssh clinic-vps-moi 'docker exec -i clinicai_db psql -U postgres -d postgres -X -q -t -A' < docs/ban-do/hieu/kiem-du-lieu-prod-3.sql

\set ON_ERROR_STOP off

-- K1 Khách đã về (check-out) mà bác sĩ CHƯA Hoàn tất khám — lượt khám, không bán lẻ
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','K1','so_dong',(SELECT count(*) FROM visit v WHERE v.closed_at IS NOT NULL AND NOT coalesce(v.ban_le,false) AND v.status NOT IN ('FINALIZED','AMENDED','INCOMPLETE') AND v.exam_completed_at IS NULL AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.id = v.appointment_id AND a.status = 'COMPLETED')))::text; ROLLBACK;
-- K1 theo tháng check-out
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','K1_thang','so',(SELECT coalesce(jsonb_object_agg(thang, n), '{}'::jsonb) FROM (SELECT to_char(v.closed_at AT TIME ZONE 'Asia/Ho_Chi_Minh','YYYY-MM') AS thang, count(*) AS n FROM visit v WHERE v.closed_at IS NOT NULL AND NOT coalesce(v.ban_le,false) AND v.status NOT IN ('FINALIZED','AMENDED','INCOMPLETE') AND v.exam_completed_at IS NULL AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.id = v.appointment_id AND a.status = 'COMPLETED') GROUP BY 1) t))::text; ROLLBACK;
-- K1 theo cơ sở
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','K1_co_so','so',(SELECT coalesce(jsonb_object_agg(coalesce(l.name,'(không cơ sở)'), n), '{}'::jsonb) FROM (SELECT v.location_id, count(*) AS n FROM visit v WHERE v.closed_at IS NOT NULL AND NOT coalesce(v.ban_le,false) AND v.status NOT IN ('FINALIZED','AMENDED','INCOMPLETE') AND v.exam_completed_at IS NULL AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.id = v.appointment_id AND a.status = 'COMPLETED') GROUP BY 1) t LEFT JOIN clinic_location l ON l.id = t.location_id))::text; ROLLBACK;
-- K1 theo bác sĩ phụ trách lượt (tên NHÂN VIÊN, không phải khách; rỗng = chưa gán bác sĩ)
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','K1_bac_si','so',(SELECT coalesce(jsonb_object_agg(coalesce(s.full_name,'(chưa gán bác sĩ)'), n), '{}'::jsonb) FROM (SELECT v.attending_doctor_id, count(*) AS n FROM visit v WHERE v.closed_at IS NOT NULL AND NOT coalesce(v.ban_le,false) AND v.status NOT IN ('FINALIZED','AMENDED','INCOMPLETE') AND v.exam_completed_at IS NULL AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.id = v.appointment_id AND a.status = 'COMPLETED') GROUP BY 1) t LEFT JOIN staff s ON s.id = t.attending_doctor_id))::text; ROLLBACK;
-- K2 Để so: lượt khám đã check-out tháng 10 tổng cộng / trong đó đã Hoàn tất khám
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','K2_thang10','tong',(SELECT count(*) FROM visit v WHERE v.closed_at >= '2026-10-01' AND NOT coalesce(v.ban_le,false)),'da_hoan_tat',(SELECT count(*) FROM visit v WHERE v.closed_at >= '2026-10-01' AND NOT coalesce(v.ban_le,false) AND (v.exam_completed_at IS NOT NULL OR EXISTS (SELECT 1 FROM appointment a WHERE a.id = v.appointment_id AND a.status = 'COMPLETED'))))::text; ROLLBACK;
