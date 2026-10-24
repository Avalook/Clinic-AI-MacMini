-- HOÀN TÁC phần BỔ SUNG của lịch sử Notion (06/10/2026): lịch sử chăm sóc, nguồn
-- khách, người nhà, dự kiến sinh — nạp bởi clinicai.services.nhap_bo_sung_notion.
--
--   docker exec -i clinicai_db psql -U postgres -v ON_ERROR_STOP=1 < scripts/hoan-tac-bo-sung-notion.sql
--
-- * Lịch sử chăm sóc (lich_su_notion.cham_soc) và nguồn khách (lich_su_notion.nguoi.kenh)
--   là dữ liệu riêng, chỉ đọc → xoá sạch.
-- * Người nhà (patient_link) và thai kỳ (pregnancy) do bộ nạp tạo → xoá ĐÚNG những dòng
--   ghi trong sổ lich_su_notion.ban_ghi_bo_sung. Thai kỳ bác sĩ ĐÃ sửa / xác nhận trên
--   hệ thống (updated_by hoặc xac_nhan_visit_id có giá trị) → GIỮ, in ra để người xem.
-- * Nạp lại sau đó: bộ nạp tạo lại đúng như cũ.
-- Một giao dịch; in số dòng trước khi COMMIT.
BEGIN;

SELECT 'thai_ky_giu_vi_bac_si_da_sua' AS viec, count(*)
  FROM public.pregnancy p
  JOIN lich_su_notion.ban_ghi_bo_sung s ON s.bang = 'pregnancy' AND s.ban_ghi_id = p.id
 WHERE p.updated_by IS NOT NULL OR p.xac_nhan_visit_id IS NOT NULL;

WITH xoa AS (
    DELETE FROM public.pregnancy p
     USING lich_su_notion.ban_ghi_bo_sung s
     WHERE s.bang = 'pregnancy' AND s.ban_ghi_id = p.id
       AND p.updated_by IS NULL AND p.xac_nhan_visit_id IS NULL
    RETURNING p.id
)
DELETE FROM lich_su_notion.ban_ghi_bo_sung s USING xoa
 WHERE s.bang = 'pregnancy' AND s.ban_ghi_id = xoa.id;

WITH xoa AS (
    DELETE FROM public.patient_link l
     USING lich_su_notion.ban_ghi_bo_sung s
     WHERE s.bang = 'patient_link' AND s.ban_ghi_id = l.id
    RETURNING l.id
)
SELECT 'xoa_lien_ket_nguoi_nha' AS viec, count(*) FROM xoa;
DELETE FROM lich_su_notion.ban_ghi_bo_sung WHERE bang = 'patient_link';

SELECT 'xoa_lich_su_cham_soc' AS viec, count(*) FROM lich_su_notion.cham_soc;
TRUNCATE lich_su_notion.cham_soc;

SELECT 'xoa_nguon_khach' AS viec, count(*) FROM lich_su_notion.nguoi WHERE kenh IS NOT NULL;
UPDATE lich_su_notion.nguoi SET kenh = NULL WHERE kenh IS NOT NULL;

UPDATE lich_su_notion.lan_nhap SET hoan_tac_luc = now()
 WHERE hoan_tac_luc IS NULL AND goi LIKE 'phu-%';

COMMIT;
