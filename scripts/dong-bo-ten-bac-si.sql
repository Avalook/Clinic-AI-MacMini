-- ĐỒNG BỘ LẠI TÊN BÁC SĨ trên prod (16/10/2026) — kiểu duy nhất "Bác sĩ <họ tên>".
--
-- VÌ SAO CÓ FILE NÀY: lúc dựng VPS mới (16/09) nhân sự được tạo lại từ seed nên mọi
-- tên đã sửa trên hệ thống cũ (ví dụ "Bác sĩ Phan Chí Thành", sửa 09/08) về lại
-- "BS Thành". Tên đầy đủ lấy từ bảng phòng khám cung cấp (supabase/fixtures/
-- ten_day_du_bac_si.sql), bỏ học hàm (TS.BS., BSNT., Ths.…) để chỉ còn MỘT kiểu.
--
-- LÀM GÌ (một giao dịch):
--   1. staff.full_name của 14 bác sĩ → "Bác sĩ <họ tên>" (khớp theo id seed, không
--      theo short_name — short_name có bác sĩ trùng nhau).
--   2. work_roster.staff_name — bản sao CHỮ của tên lúc xếp ca, trước nay không tự
--      cập nhật — chép lại từ staff.full_name cho mọi dòng lệch (cả điều dưỡng/lễ tân).
--      Tắt trigger sổ lịch sử lịch trực trong bước này (session_replication_role):
--      đây là chỉnh nhãn, không phải "đổi người", không được đổ hàng trăm dòng
--      DOI_NGUOI vào lịch sử lịch trực.
--   3. Ghi 'staff.updated' vào domain_event (người = SYSTEM) để /ops "Nhật ký" thấy.
--   4. pg_notify để các màn đang mở tự tải lại.
--
-- KHÔNG ĐỤNG: short_name (bảng lịch/fixture tra theo nó); bản chụp lịch sử
-- (so_sua_chi_dinh, phiếu khám, form_instance… — đúng với lúc ghi); tên phòng.
--
-- CHẠY (mặc định XEM TRƯỚC rồi ROLLBACK; thêm -v that=1 mới ghi thật):
--   ssh clinic-vps-moi 'docker exec -i clinicai_db psql -U postgres -d postgres' \
--       < scripts/dong-bo-ten-bac-si.sql
--   ssh clinic-vps-moi 'docker exec -i clinicai_db psql -U postgres -d postgres -v that=1' \
--       < scripts/dong-bo-ten-bac-si.sql
-- Chạy lại nhiều lần an toàn (lần sau không còn gì để đổi).

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE ten_moi (staff_id uuid PRIMARY KEY, ten text NOT NULL) ON COMMIT DROP;
INSERT INTO ten_moi VALUES
  ('d0000000-0000-4000-8000-000000000001', 'Bác sĩ Phan Chí Thành'),
  ('d0000000-0000-4000-8000-000000000002', 'Bác sĩ Phan Thu Hằng'),
  ('d0000000-0000-4000-8000-000000000003', 'Bác sĩ Nguyễn Phương Nam'),
  ('d0000000-0000-4000-8000-000000000004', 'Bác sĩ Vũ Trọng Hùng'),
  ('d0000000-0000-4000-8000-000000000005', 'Bác sĩ Hoàng Đình Thiệp'),
  ('d0000000-0000-4000-8000-000000000006', 'Bác sĩ Lê Thiệu Quyết'),
  ('d0000000-0000-4000-8000-000000000007', 'Bác sĩ Nguyễn Khánh Linh'),
  ('d0000000-0000-4000-8000-000000000009', 'Bác sĩ Phạm Văn Nghị'),
  ('d0000000-0000-4000-8000-000000000011', 'Bác sĩ Phạm Ngọc Minh'),
  ('d0000000-0000-4000-8000-000000000012', 'Bác sĩ Nguyễn Thành Đạt'),
  ('d0000000-0000-4000-8000-000000000013', 'Bác sĩ Nguyễn Trung Tiến'),
  ('d0000000-0000-4000-8000-000000000014', 'Bác sĩ Nguyễn Mạnh Minh Hoàng'),
  ('d0000000-0000-4000-8000-000000000015', 'Bác sĩ Nguyễn Hữu Giáp'),
  ('d0000000-0000-4000-8000-000000000016', 'Bác sĩ Đào Bá Linh');

-- Đủ 14 người, đều là bác sĩ — thiếu/sai thì dừng, không đổi nửa vời.
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM staff s JOIN ten_moi t ON t.staff_id = s.id
   WHERE s.primary_department IN ('DOCTOR', 'ULTRASOUND_DOCTOR');
  IF n <> 14 THEN
    RAISE EXCEPTION 'Chỉ khớp % / 14 bác sĩ theo id — dừng, không đổi gì.', n;
  END IF;
END $$;

\echo '== TRƯỚC: tên sẽ đổi'
SELECT s.primary_department AS vai, s.full_name AS ten_hien_tai, t.ten AS ten_moi
  FROM staff s JOIN ten_moi t ON t.staff_id = s.id
 WHERE s.full_name IS DISTINCT FROM t.ten
 ORDER BY s.primary_department, t.ten;

\echo '== TRƯỚC: dòng lịch trực lệch tên (staff_name ≠ full_name MỚI), gom theo người'
SELECT coalesce(t.ten, s.full_name) AS ten_se_la, count(*) AS so_dong,
       count(DISTINCT r.staff_name) AS so_cach_viet
  FROM work_roster r JOIN staff s ON s.id = r.staff_id
  LEFT JOIN ten_moi t ON t.staff_id = s.id
 WHERE r.staff_name IS DISTINCT FROM coalesce(t.ten, s.full_name)
 GROUP BY 1 ORDER BY 2 DESC;

-- 1. Tên nhân sự
CREATE TEMP TABLE da_doi ON COMMIT DROP AS
SELECT s.id AS staff_id, s.full_name AS ten_cu, t.ten AS ten_moi
  FROM staff s JOIN ten_moi t ON t.staff_id = s.id
 WHERE s.full_name IS DISTINCT FROM t.ten;

UPDATE staff s SET full_name = d.ten_moi, updated_at = now()
  FROM da_doi d WHERE s.id = d.staff_id;

-- 3. Nhật ký (một dòng mỗi người, cùng khuôn sự kiện staff_service ghi)
INSERT INTO domain_event
    (event_type, clinic_id, aggregate_type, aggregate_id, actor_type,
     source_module, payload)
SELECT 'staff.updated', m.clinic_id, 'staff', d.staff_id, 'SYSTEM',
       'scripts.dong-bo-ten-bac-si',
       jsonb_build_object('staff_id', d.staff_id, 'fields', jsonb_build_array('full_name'),
                          'role', NULL, 'is_active', NULL,
                          'ten_cu', d.ten_cu, 'ten_moi', d.ten_moi)
  FROM da_doi d JOIN clinic_membership m ON m.staff_id = d.staff_id;

-- 2. Nhãn tên trên lịch trực (tắt trigger sổ lịch sử + notify chỉ trong bước này)
SET LOCAL session_replication_role = replica;
UPDATE work_roster r SET staff_name = s.full_name
  FROM staff s
 WHERE r.staff_id = s.id AND r.staff_name IS DISTINCT FROM s.full_name;
SET LOCAL session_replication_role = DEFAULT;

\echo '== SAU: còn dòng lịch trực lệch tên không (phải = 0)'
SELECT count(*) AS dong_lech
  FROM work_roster r JOIN staff s ON s.id = r.staff_id
 WHERE r.staff_name IS DISTINCT FROM s.full_name;

\echo '== SAU: 14 bác sĩ'
SELECT s.primary_department AS vai, s.full_name, s.short_name, s.is_active
  FROM staff s JOIN ten_moi t ON t.staff_id = s.id
 ORDER BY s.primary_department, s.full_name;

-- 4. Báo các màn đang mở (tin nghèo: chỉ tên bảng + phòng khám, như notify_row_change)
SELECT pg_notify('clinicai_changes', json_build_object('t', tb, 'c', cl)::text)
  FROM (SELECT DISTINCT m.clinic_id AS cl, x.tb
          FROM da_doi d JOIN clinic_membership m ON m.staff_id = d.staff_id
          CROSS JOIN (VALUES ('staff'), ('work_roster')) AS x(tb)) q;

\if :{?that}
  \echo '== GHI THẬT (COMMIT)'
  COMMIT;
\else
  \echo '== CHỈ XEM TRƯỚC — ROLLBACK (thêm -v that=1 để ghi thật)'
  ROLLBACK;
\endif
