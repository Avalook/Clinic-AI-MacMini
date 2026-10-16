-- GỠ DỊCH VỤ THƯỜNG KHỎI PHÒNG ĐỐI TÁC (Tuyền 16/10/2026). DỮ LIỆU, không migration.
-- Script "mở hết phòng" 01/10 gắn MỌI dịch vụ cho MỌI phòng đang bật, kể cả phòng đối
-- tác (~87 dịch vụ thường: siêu âm, khám, laser…). Chỉ giữ dịch vụ ĐỐI TÁC: khách trả
-- đối tác (billing_owner = EXTERNAL_PARTNER), đối tác tự lấy mẫu, hoặc nhóm việc làm
-- bên ngoài. Dịch vụ thường KHÔNG mồ côi: phần kiểm cuối đếm dịch vụ bị gỡ mà không còn
-- phòng thường đang bật nào gắn — phải bằng 0, khác 0 thì ROLLBACK tự động (RAISE).
-- Tuyền chạy trên STAGING trước, rồi prod:
--   ssh clinic-vps-moi 'docker exec -i clinicai_stg_db psql -U postgres -d postgres -v ON_ERROR_STOP=1' < scripts/go-dich-vu-thua-phong-doi-tac-1610.sql
BEGIN;
CREATE TEMP TABLE _go ON COMMIT DROP AS
SELECT rs.clinic_id, rs.room_id, rs.service_code
  FROM public.clinic_room_service rs
  JOIN public.clinic_room r ON r.id = rs.room_id AND r.clinic_id = rs.clinic_id AND r.la_doi_tac
  LEFT JOIN public.service_price sp
    ON sp.clinic_id = rs.clinic_id AND sp.service_code = rs.service_code
   AND sp."group" = 'dich_vu'
  LEFT JOIN public.node_definition nd
    ON nd.clinic_id = sp.clinic_id AND nd.code = sp.node_code
 WHERE NOT coalesce(sp.billing_owner = 'EXTERNAL_PARTNER'
                    OR sp.doi_tac_lay_mau OR nd.lam_ben_ngoai, false);

DELETE FROM public.clinic_room_service rs
 USING _go g
 WHERE rs.clinic_id = g.clinic_id AND rs.room_id = g.room_id
   AND rs.service_code = g.service_code;

DO $$
DECLARE mo_coi int;
BEGIN
  SELECT count(DISTINCT g.service_code) INTO mo_coi
    FROM _go g
   WHERE NOT EXISTS (
         SELECT 1 FROM public.clinic_room_service rs
           JOIN public.clinic_room r ON r.id = rs.room_id AND r.clinic_id = rs.clinic_id
          WHERE rs.clinic_id = g.clinic_id AND rs.service_code = g.service_code
            AND r.is_active AND NOT r.la_doi_tac);
  IF mo_coi > 0 THEN
    RAISE EXCEPTION 'Dừng: % dịch vụ sẽ không còn phòng thường nào gắn', mo_coi;
  END IF;
END $$;

SELECT r.code AS phong, count(g.*) AS da_go,
       (SELECT count(*) FROM public.clinic_room_service rs WHERE rs.room_id = r.id) AS con_lai
  FROM public.clinic_room r
  LEFT JOIN _go g ON g.room_id = r.id
 WHERE r.la_doi_tac
 GROUP BY r.id, r.code ORDER BY 1;
COMMIT;
