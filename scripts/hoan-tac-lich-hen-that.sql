-- GỠ các lịch hẹn / việc gọi đã chuyển từ sổ hẹn cũ (src/clinicai/services/chuyen_lich_hen.py).
--
--   docker exec -i clinicai_db psql -v ON_ERROR_STOP=1 -U postgres < scripts/hoan-tac-lich-hen-that.sql
--
-- Xoá đúng các bản ghi trong sổ ghép lich_su_notion.lich_hen_that; sổ hẹn cũ
-- (lich_su_notion.lich_hen) GIỮ NGUYÊN — chuyển lại sau đó bằng chính bộ chuyển.
-- Việc gọi "mời tái khám" từ phiếu khám mà lịch chuyển đã tự đóng ("đã có lịch")
-- được MỞ LẠI như trước khi chuyển.
--
-- DỪNG (không xoá gì) nếu nhân viên đã làm gì trên lịch / việc đã chuyển: đổi giờ,
-- đổi bác sĩ, huỷ, check-in, gọi CSKH, mở lượt, tải tệp… — những thứ ấy là dữ
-- liệu thật, gỡ tay.
BEGIN;

CREATE TEMP TABLE _l ON COMMIT DROP AS
SELECT DISTINCT appointment_id AS id, trang_thai_luc_chuyen, slot_start, doctor_id
  FROM lich_su_notion.lich_hen_that WHERE appointment_id IS NOT NULL;
CREATE TEMP TABLE _n ON COMMIT DROP AS
SELECT DISTINCT nhac_tai_kham_id AS id
  FROM lich_su_notion.lich_hen_that WHERE nhac_tai_kham_id IS NOT NULL;

DO $$
DECLARE n bigint;
BEGIN
    SELECT (SELECT count(*) FROM appointment a JOIN _l ON _l.id = a.id
             WHERE a.status IS DISTINCT FROM _l.trang_thai_luc_chuyen
                OR a.slot_start IS DISTINCT FROM _l.slot_start
                OR a.doctor_id IS DISTINCT FROM _l.doctor_id)
         + (SELECT count(*) FROM visit v JOIN _l ON _l.id = v.appointment_id)
         + (SELECT count(*) FROM work_item w JOIN _l ON _l.id = w.appointment_id)
         + (SELECT count(*) FROM lab_result r JOIN _l ON _l.id = r.appointment_id)
         + (SELECT count(*) FROM care_episode e JOIN _l ON _l.id = e.opened_appointment_id)
         + (SELECT count(*) FROM tuong_tac_cskh t JOIN _l ON _l.id = t.appointment_id)
         + (SELECT count(*) FROM tep_ket_qua t JOIN _l ON _l.id = t.appointment_id)
         + (SELECT count(*) FROM appointment_doi_lich d JOIN _l ON _l.id = d.appointment_id)
         + (SELECT count(*) FROM appointment a JOIN _l ON _l.id = a.lich_truoc_id)
         + (SELECT count(*) FROM nhac_tai_kham k JOIN _n ON _n.id = k.id
             WHERE k.trang_thai <> 'CHO_GOI')
      INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'Có % chỗ nhân viên đã làm trên lịch / việc đã chuyển — không gỡ tự động.', n;
    END IF;
END $$;

-- Mở lại việc gọi tái khám (từ phiếu khám) mà trigger nhac_tai_kham_dong_khi_co_lich
-- đã đóng vì lịch chuyển, kèm chuông hẹn giờ của nó.
UPDATE hen_gio h SET trang_thai = 'CHO', lam_luc = NULL, ket_qua = NULL
  FROM nhac_tai_kham k
 WHERE k.appointment_id IN (SELECT id FROM _l) AND k.dong_vi = 'DA_CO_LICH'
   AND k.trang_thai = 'KHONG_CAN'
   AND h.loai = 'nhac_tai_kham.den_han' AND h.ve_cai_gi = k.id
   AND h.trang_thai = 'BO_QUA' AND h.ket_qua = 'da_co_lich';
UPDATE nhac_tai_kham k
   SET trang_thai = 'CHO_GOI', dong_vi = NULL, ghi_chu = NULL, appointment_id = NULL,
       dong_luc = NULL, updated_at = now()
 WHERE k.appointment_id IN (SELECT id FROM _l) AND k.dong_vi = 'DA_CO_LICH'
   AND k.trang_thai = 'KHONG_CAN';
UPDATE nhac_tai_kham SET appointment_id = NULL WHERE appointment_id IN (SELECT id FROM _l);

DELETE FROM nhac_tai_kham k USING _n WHERE k.id = _n.id;
-- Tắt trigger chặn xoá cứng lịch hẹn CHỈ trong giao dịch này. Khoá ngoại cũng tắt
-- theo — nên mọi bảng trỏ tới lịch đã được kiểm rỗng / gỡ ở trên.
SET LOCAL session_replication_role = replica;
DELETE FROM appointment a USING _l WHERE a.id = _l.id;

SELECT (SELECT count(*) FROM _l) AS so_lich_da_go, (SELECT count(*) FROM _n) AS so_viec_goi_da_go;

DELETE FROM lich_su_notion.lich_hen_that;
UPDATE lich_su_notion.lan_chuyen_lich SET hoan_tac_luc = now() WHERE hoan_tac_luc IS NULL;
COMMIT;
