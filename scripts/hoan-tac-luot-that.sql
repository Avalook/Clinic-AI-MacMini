-- GỠ các lượt thật đã chuyển từ hồ sơ cũ (src/clinicai/services/chuyen_luot_that.py).
--
--   docker exec -i clinicai_db psql -v ON_ERROR_STOP=1 -U postgres < scripts/hoan-tac-luot-that.sql
--
-- Xoá đúng các bản ghi trong sổ ghép lich_su_notion.luot_that / ban_ghi_that; dữ
-- liệu cũ ở lich_su_notion.* GIỮ NGUYÊN (khối "Hồ sơ khám trước 10/2026" tự hiện
-- lại đủ lượt). Chuyển lại sau đó bằng chính bộ chuyển.
--
-- DỪNG (không xoá gì) nếu nhân viên đã ghi thêm vào lượt cũ: chỉ định, đơn thuốc,
-- tệp, phiếu, hay lượt bị mở lại — những thứ ấy là dữ liệu thật, gỡ tay.
BEGIN;

CREATE TEMP TABLE _v ON COMMIT DROP AS
SELECT DISTINCT visit_id, appointment_id FROM lich_su_notion.luot_that WHERE visit_id IS NOT NULL;
CREATE TEMP TABLE _so ON COMMIT DROP AS
SELECT DISTINCT ban_ghi_id AS id FROM lich_su_notion.ban_ghi_that WHERE bang = 'service_order';

DO $$
DECLARE n bigint;
BEGIN
    SELECT (SELECT count(*) FROM service_order s JOIN _v ON _v.visit_id = s.visit_id
             WHERE s.id NOT IN (SELECT id FROM _so))
         + (SELECT count(*) FROM prescription p JOIN _v ON _v.visit_id = p.visit_id
             WHERE p.source_ref NOT LIKE 'ho-so-cu-%')
         + (SELECT count(*) FROM tep_ket_qua t JOIN _v ON _v.appointment_id = t.appointment_id
             WHERE t.khoa NOT LIKE '%/lich-su-notion/%')
         + (SELECT count(*) FROM visit v JOIN _v USING (visit_id) WHERE v.status <> 'FINALIZED')
      INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'Có % bản ghi nhân viên đã thêm/sửa trên lượt cũ — không gỡ tự động.', n;
    END IF;
END $$;

-- Tắt trigger (chặn xoá cứng, khoá đơn thuốc lượt đã ký…) CHỈ trong giao dịch này.
SET LOCAL session_replication_role = replica;

DELETE FROM tep_ket_qua t USING _v WHERE t.appointment_id = _v.appointment_id
   AND t.khoa LIKE '%/lich-su-notion/%';
DELETE FROM form_instance_lich_su h USING _so WHERE h.service_order_id = _so.id;
DELETE FROM form_instance f USING _so WHERE f.service_order_id = _so.id;
DELETE FROM service_order s USING _so WHERE s.id = _so.id;
DELETE FROM prescription p USING _v WHERE p.visit_id = _v.visit_id
   AND p.source_ref LIKE 'ho-so-cu-%';
DELETE FROM phieu_kham_lich_su h USING phieu_kham_luot p, _v
 WHERE h.phieu_id = p.id AND p.visit_id = _v.visit_id;
DELETE FROM phieu_kham_luot p USING _v WHERE p.visit_id = _v.visit_id;
DELETE FROM consultation_note n USING consultation c, _v
 WHERE n.consultation_id = c.id AND c.visit_id = _v.visit_id;
DELETE FROM consultation c USING _v WHERE c.visit_id = _v.visit_id;
DELETE FROM luot_ghi_chu g USING _v WHERE g.visit_id = _v.visit_id;
DELETE FROM clinical_release r USING _v WHERE r.visit_id = _v.visit_id;
DELETE FROM visit v USING _v WHERE v.visit_id = _v.visit_id;
DELETE FROM appointment a USING _v WHERE a.id = _v.appointment_id;

DELETE FROM lich_su_notion.ban_ghi_that;
DELETE FROM lich_su_notion.luot_that;
UPDATE lich_su_notion.lan_chuyen SET hoan_tac_luc = now() WHERE hoan_tac_luc IS NULL;

SELECT (SELECT count(*) FROM _v) AS so_luot_da_go;
COMMIT;
