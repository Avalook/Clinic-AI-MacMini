-- GỠ DỊCH VỤ ĐỐI TÁC LÀM TRỌN KHỎI PHÒNG THƯỜNG (Tuyền 16/10/2026). DỮ LIỆU, không migration.
-- Script "mở hết phòng" 01/10 gắn MỌI dịch vụ cho MỌI phòng (kể cả Quầy tiếp đón, Thu
-- ngân thuốc). Với dịch vụ thuộc nhóm việc LÀM BÊN NGOÀI (chụp MRI vú, chụp tử cung – vòi
-- trứng, chụp vú ép) điều đó làm `DOI_TAC_LAM_TRON_SQL` sai: phòng thường "làm được" nên
-- việc không còn là của đối tác → không vào Phòng đối tác, quầy gợi ý toàn phòng thường.
-- Gỡ khỏi phòng THƯỜNG các dịch vụ đối tác làm trọn (nhóm việc làm bên ngoài, hoặc đối tác
-- tự lấy mẫu). Dịch vụ thu hộ nhưng lấy mẫu trong nhà (XN máu…) KHÔNG đụng.
-- Chạy SAU `bat-lai-doi-tac-1610.sql`. Tự dừng (RAISE → ROLLBACK) nếu một dịch vụ bị gỡ mà
-- không còn phòng đối tác đang bật nào gắn nó.
--   ssh clinic-vps-moi 'docker exec -i clinicai_stg_db psql -U postgres -d postgres -v ON_ERROR_STOP=1' < scripts/go-dich-vu-doi-tac-khoi-phong-thuong-1610.sql
BEGIN;
CREATE TEMP TABLE _go ON COMMIT DROP AS
SELECT rs.clinic_id, rs.room_id, rs.service_code
  FROM public.clinic_room_service rs
  JOIN public.clinic_room r ON r.id = rs.room_id AND r.clinic_id = rs.clinic_id
   AND NOT r.la_doi_tac
  JOIN public.service_price sp
    ON sp.clinic_id = rs.clinic_id AND sp.service_code = rs.service_code
   AND sp."group" = 'dich_vu'
  LEFT JOIN public.node_definition nd
    ON nd.clinic_id = sp.clinic_id AND nd.code = sp.node_code
 WHERE sp.doi_tac_lay_mau OR coalesce(nd.lam_ben_ngoai, false);

DELETE FROM public.clinic_room_service rs
 USING _go g
 WHERE rs.clinic_id = g.clinic_id AND rs.room_id = g.room_id
   AND rs.service_code = g.service_code;

-- Kiểm SAU khi gỡ, bằng đúng hàm máy dùng khi xếp phòng: mỗi dịch vụ vừa gỡ phải còn ít
-- nhất một phòng ĐỐI TÁC đang bật làm được (gắn tên, hoặc qua nhóm việc của phòng).
DO $$
DECLARE mo_coi int;
BEGIN
  SELECT count(DISTINCT g.service_code) INTO mo_coi
    FROM _go g
    JOIN public.service_price sp
      ON sp.clinic_id = g.clinic_id AND sp.service_code = g.service_code
     AND sp."group" = 'dich_vu'
   WHERE NOT EXISTS (
         SELECT 1 FROM public.clinic_room r
          WHERE r.clinic_id = g.clinic_id AND r.is_active AND r.la_doi_tac
            AND public.phong_lam_duoc(r.clinic_id, r.id, sp.node_code, sp.service_code));
  IF mo_coi > 0 THEN
    RAISE EXCEPTION 'Dừng: % dịch vụ đối tác không còn phòng đối tác nào làm được', mo_coi;
  END IF;
END $$;

SELECT g.service_code, count(*) AS da_go_khoi_phong_thuong
  FROM _go g GROUP BY 1 ORDER BY 1;
COMMIT;
