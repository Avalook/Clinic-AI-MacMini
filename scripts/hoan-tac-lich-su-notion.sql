-- HOÀN TÁC việc nhập lịch sử Notion (05/10/2026).
--
--   docker exec -i clinicai_db psql -U postgres -v ON_ERROR_STOP=1 < scripts/hoan-tac-lich-su-notion.sql
--
-- * Lịch sử (schema lich_su_notion) là bảng riêng, chỉ đọc → xoá sạch được.
-- * Hồ sơ khách TẠO từ Notion (patient.nguon_nhap = 'notion') không xoá cứng được
--   (khoá chặn xoá). Hồ sơ chưa có hoạt động nào trên hệ thống → ẨN (is_active =
--   false). Hồ sơ đã có lịch hẹn / lượt khám trên hệ thống → GIỮ (đã là khách thật).
-- * Nạp lại sau đó: bộ nạp nhận lại đúng hồ sơ ẩn theo mã Notion và bật lại.
-- Một giao dịch; in số dòng trước khi COMMIT.
BEGIN;

SELECT 'an_ho_so' AS viec, count(*) FROM public.patient p
 WHERE p.nguon_nhap = 'notion' AND p.is_active
   AND NOT EXISTS (SELECT 1 FROM public.appointment a WHERE a.clinic_patient_id = p.clinic_patient_id)
   AND NOT EXISTS (SELECT 1 FROM public.visit v WHERE v.clinic_patient_id = p.clinic_patient_id);

UPDATE public.patient p SET is_active = false, updated_at = now()
 WHERE p.nguon_nhap = 'notion' AND p.is_active
   AND NOT EXISTS (SELECT 1 FROM public.appointment a WHERE a.clinic_patient_id = p.clinic_patient_id)
   AND NOT EXISTS (SELECT 1 FROM public.visit v WHERE v.clinic_patient_id = p.clinic_patient_id);

TRUNCATE lich_su_notion.bat_thuong, lich_su_notion.lich_hen, lich_su_notion.ke_thuoc,
         lich_su_notion.xet_nghiem, lich_su_notion.ket_qua, lich_su_notion.dich_vu,
         lich_su_notion.luot_kham, lich_su_notion.nguoi;
UPDATE lich_su_notion.lan_nhap SET hoan_tac_luc = now() WHERE hoan_tac_luc IS NULL;

COMMIT;
