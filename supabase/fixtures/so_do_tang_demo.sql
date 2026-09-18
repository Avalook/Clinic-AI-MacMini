-- SƠ ĐỒ TẦNG GIẢ LẬP — để màn Trưởng ca có tầng mà vẽ (Tuyền 16/09/2026).
--
-- Bảng `clinic_room` đã có cột `floor` từ 20260804000011, nhưng chưa dòng nào
-- khai: mọi phòng hiện ra là "chưa khai tầng", nên không dựng được lưới phòng
-- theo tầng như bản thiết kế. Fixture này khai tầng cho các phòng ĐANG CÓ và
-- thêm hai phòng còn thiếu (thủ thuật, tư vấn) để mỗi tầng có việc riêng.
--
-- GIẢ HOÀN TOÀN, chỉ nạp vào local/staging:
--   docker exec -i clinicai_thu_db psql -U postgres -d postgres < supabase/fixtures/so_do_tang_demo.sql
--
-- Chạy lại được: chỉ UPDATE theo `code` và INSERT ... ON CONFLICT DO UPDATE.

BEGIN;

-- Tầng 1 — nơi khách vào và ra: tiếp đón, sinh hiệu, thu ngân, nhà thuốc.
UPDATE clinic_room SET floor = '1', sort = 10 WHERE code = 'TIEPNHAN';
UPDATE clinic_room SET floor = '1', sort = 20 WHERE code = 'SINHHIEU';
UPDATE clinic_room SET floor = '1', sort = 30 WHERE code = 'THUNGAN';
UPDATE clinic_room SET floor = '1', sort = 40 WHERE code = 'NHATHUOC';

-- Tầng 2 — bàn khám + lấy mẫu.
UPDATE clinic_room SET floor = '2', sort = 10 WHERE code = 'KB01';
UPDATE clinic_room SET floor = '2', sort = 20 WHERE code = 'KB02';
UPDATE clinic_room SET floor = '2', sort = 30 WHERE code = 'KB03';
UPDATE clinic_room SET floor = '2', sort = 40 WHERE code = 'KB04';
UPDATE clinic_room SET floor = '2', sort = 50 WHERE code = 'XETNGHIEM';

-- Tầng 3 — siêu âm + thủ thuật.
UPDATE clinic_room SET floor = '3', sort = 10 WHERE code = 'SA1';
UPDATE clinic_room SET floor = '3', sort = 20 WHERE code = 'SA2';
UPDATE clinic_room SET floor = '3', sort = 30 WHERE code = 'SA3';

-- Hai phòng THÊM. `location_id` lấy từ chính cơ sở đang có phòng — không viết
-- cứng id, để fixture chạy được trên mọi bản database local.
INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,
                         capacity, accepting, sort, show_on_tv, floor)
SELECT r.clinic_id, r.location_id, v.code, v.name, v.node_code,
       v.capacity, true, v.sort, v.show_on_tv, v.floor
  FROM (SELECT clinic_id, location_id FROM clinic_room
         WHERE code = 'SA1' LIMIT 1) r,
       (VALUES
          ('THUTHUAT1', 'Thủ thuật 1', 'DICHVU-THUTHUAT', 1, 40, true,  '3'),
          ('TUVAN1',    'Tư vấn 1',    'LUOTKHAM-13',     2, 60, false, '3')
       ) AS v(code, name, node_code, capacity, sort, show_on_tv, floor)
ON CONFLICT (clinic_id, code) DO UPDATE
   SET floor = EXCLUDED.floor,
       sort = EXCLUDED.sort,
       name = EXCLUDED.name,
       capacity = EXCLUDED.capacity,
       show_on_tv = EXCLUDED.show_on_tv,
       is_active = true;

-- BƯỚC NÀO PHÒNG NÀY LÀM ĐƯỢC. Hai phòng mới chưa có dòng nào trong
-- `clinic_room_node`, nên điều phối không xếp được ai vào; và bốn phòng khám
-- chỉ khai năm chuyên khoa mà thiếu chính bước "Khám" của lượt khám
-- (LUOTKHAM-05) — lượt nào tới bước ấy cũng không tìm ra phòng.
INSERT INTO clinic_room_node (clinic_id, room_id, node_code)
SELECT r.clinic_id, r.id, v.node_code
  FROM clinic_room r
  JOIN (VALUES
      ('KB01', 'LUOTKHAM-05'), ('KB02', 'LUOTKHAM-05'),
      ('KB03', 'LUOTKHAM-05'), ('KB04', 'LUOTKHAM-05'),
      ('THUTHUAT1', 'DICHVU-THUTHUAT'),
      ('TUVAN1', 'LUOTKHAM-13')
  ) AS v(code, node_code) ON v.code = r.code
 WHERE r.is_active
ON CONFLICT DO NOTHING;

-- Sức chứa cho khớp đời thật: bàn khám 1 người, phòng lấy mẫu và tiếp đón 2.
UPDATE clinic_room SET capacity = 2 WHERE code IN ('TIEPNHAN', 'SINHHIEU', 'XETNGHIEM', 'THUNGAN');

COMMIT;

\echo 'Sơ đồ tầng:'
SELECT floor AS tang, code, name, node_code, capacity, accepting, show_on_tv
  FROM clinic_room
 WHERE is_active
 ORDER BY floor NULLS LAST, sort, code;
