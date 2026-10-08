-- VỊ TRÍ LỊCH LÀM VIỆC HÀO NAM THEO SƠ ĐỒ 4 TẦNG (Tuyền duyệt 08/10/2026).
--
-- Vị trí Hào Nam được nhân bản từ Kim Ngưu nên thứ tự, tên và số người mỗi phòng
-- theo Kim Ngưu → lịch nhảy tầng 1 → 4 → 1 → 3 → 2. Tệp này đặt lại đúng sơ đồ:
-- Tầng 1 → 2 → 3 → 4 → Điều phối; mỗi phòng khám/thủ thuật/siêu âm đúng MỘT vị trí
-- bác sĩ, người hỗ trợ cùng phòng (luật: hỗ trợ cùng phòng làm hộ + ký tên bác sĩ
-- đứng phòng). Thu ngân tầng 2, 3 = quầy thu nhỏ (không nhận khách tự động).
--
-- Mã vị trí giữ dạng HN__<mã mẫu Kim Ngưu>[__n] để vai/ca khám bác sĩ tra đúng.
-- Chạy lại được (upsert). Kim Ngưu không đụng. Lịch làm việc đang trống.
--
-- Chạy thử:  psql -v that=0 -f …   ·   Ghi thật: psql -v that=1 -f …

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE _cs ON COMMIT DROP AS
SELECT l.clinic_id AS cid, l.id AS hn
  FROM public.clinic_location l
 WHERE l.code = 'HN' AND l.clinic_id = 'a0000000-0000-4000-8000-000000000001';

DO $$ BEGIN
    IF (SELECT count(*) FROM _cs) <> 1 THEN
        RAISE EXCEPTION 'Không thấy đúng một cơ sở Hào Nam';
    END IF;
END $$;

-- ── 1. Hai quầy thu nhỏ tầng 2, tầng 3 (không nhận khách tự động, không lên TV)
INSERT INTO public.clinic_room (clinic_id, location_id, code, name, node_code, floor,
                                sort, capacity, accepting, show_on_tv, is_active,
                                la_doi_tac)
SELECT c.cid, c.hn, x.code, x.name, 'LUOTKHAM-14', x.floor, x.sort, 1, false, false,
       true, false
  FROM _cs c,
       (VALUES ('HN-THUNGAN-T2', 'Thu ngân tầng 2', 'Tầng 2', 65),
               ('HN-THUNGAN-T3', 'Thu ngân tầng 3', 'Tầng 3', 85)) x(code, name, floor, sort)
ON CONFLICT (clinic_id, code) DO UPDATE
   SET name = EXCLUDED.name, floor = EXCLUDED.floor, sort = EXCLUDED.sort,
       is_active = true, accepting = false, show_on_tv = false;

INSERT INTO public.clinic_room_node (clinic_id, room_id, node_code)
SELECT r.clinic_id, r.id, 'LUOTKHAM-14'
  FROM public.clinic_room r, _cs c
 WHERE r.clinic_id = c.cid AND r.code IN ('HN-THUNGAN-T2', 'HN-THUNGAN-T3')
ON CONFLICT DO NOTHING;

-- ── 2. Danh sách vị trí theo sơ đồ
CREATE TEMP TABLE _vt (code text, phong text, ten text, sort int, nhom text) ON COMMIT DROP;
INSERT INTO _vt VALUES
    -- Tầng 1
    ('HN__T1_LETAN',        'HN-TIEPDON-B',   'Lễ tân',                         110, 'DIEU_DUONG'),
    ('HN__T1_THUNGAN',      'HN-TIEPDON-B',   'Thu ngân',                       120, 'DIEU_DUONG'),
    ('HN__T2_XEPTHUOC',     'HN-QUAYTHUOC-B', 'Xếp thuốc + Giải thích thuốc',   130, 'DIEU_DUONG'),
    ('HN__T2_TAODON',       'HN-QUAYTHUOC-B', 'Tạo đơn thuốc + Thu ngân',       140, 'DIEU_DUONG'),
    ('HN__T1_HOIBENH',      'HN-TUVAN-B',     'Hỏi bệnh ban đầu',               150, 'CHUNG'),
    ('HN__T1_BS_NOITIET',   'HN-NOITIET-B',   'Bác sĩ',                         160, 'BAC_SI'),
    ('HN__T1_TKYK',         'HN-NOITIET-B',   'Thư ký y khoa',                  170, 'DIEU_DUONG'),
    -- Tầng 2
    ('HN__T1_SA_BS',        'HN-SA1-B',       'BS siêu âm',                     210, 'BAC_SI'),
    ('HN__T1_SA_DD',        'HN-SA1-B',       'Điều dưỡng',                     220, 'DIEU_DUONG'),
    ('HN__T1_SA_TK',        'HN-SA1-B',       'Thư ký',                         230, 'DIEU_DUONG'),
    ('HN__T4_SANCHAU_BSTT', 'HN-SANCHAU-B',   'BS thủ thuật',                   240, 'BAC_SI'),
    ('HN__T4_SANCHAU_DD',   'HN-SANCHAU-B',   'Điều dưỡng thủ thuật',           250, 'DIEU_DUONG'),
    ('HN__T4_BIO_DD',       'HN-SANCHAU-B',   'Điều dưỡng Bio',                 260, 'DIEU_DUONG'),
    ('HN__T4_SANCHAU_TKTT', 'HN-SANCHAU-B',   'Thư ký',                         270, 'DIEU_DUONG'),
    ('HN__T1_THUNGAN__2',   'HN-THUNGAN-T2',  'Thu ngân',                       280, 'DIEU_DUONG'),
    -- Tầng 3
    ('HN__T4_SAN_BS',       'HN-SAN-BIO-B',   'Bác sĩ',                         310, 'BAC_SI'),
    ('HN__T4_SAN_DD',       'HN-SAN-BIO-B',   'Điều dưỡng',                     320, 'DIEU_DUONG'),
    ('HN__T4_SAN_TK',       'HN-SAN-BIO-B',   'Thư ký',                         330, 'DIEU_DUONG'),
    ('HN__T1_TT_BS',        'HN-THUTHUAT-B',  'BS thủ thuật',                   340, 'BAC_SI'),
    ('HN__T1_TT_DD',        'HN-THUTHUAT-B',  'Điều dưỡng',                     350, 'DIEU_DUONG'),
    ('HN__T4_BIO_DD__3',    'HN-THUTHUAT-B',  'Điều dưỡng Bio',                 360, 'DIEU_DUONG'),
    ('HN__T1_TT_TK',        'HN-THUTHUAT-B',  'Thư ký',                         370, 'DIEU_DUONG'),
    ('HN__T1_THUNGAN__3',   'HN-THUNGAN-T3',  'Thu ngân',                       380, 'DIEU_DUONG'),
    -- Tầng 4
    ('HN__T1_DOCHISO',      'HN-XN-B',        'Đo chỉ số (HA, MĐX, nước tiểu)', 410, 'DIEU_DUONG'),
    ('HN__T1_LAYMAU',       'HN-XN-B',        'Lấy mẫu máu',                    420, 'DOI_TAC'),
    ('HN__T1_SA_BS__4',     'HN-SA-E10-B',    'BS siêu âm',                     430, 'BAC_SI'),
    ('HN__T1_SA_DD__4',     'HN-SA-E10-B',    'Điều dưỡng',                     440, 'DIEU_DUONG'),
    ('HN__T1_SA_TK__4',     'HN-SA-E10-B',    'Thư ký',                         450, 'DIEU_DUONG');

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM _vt v WHERE NOT EXISTS (
                   SELECT 1 FROM public.clinic_room r, _cs c
                    WHERE r.clinic_id = c.cid AND r.code = v.phong AND r.is_active)) THEN
        RAISE EXCEPTION 'Có phòng trong danh sách không tồn tại / đang tắt: %',
            (SELECT string_agg(DISTINCT v.phong, ', ') FROM _vt v WHERE NOT EXISTS (
                 SELECT 1 FROM public.clinic_room r, _cs c
                  WHERE r.clinic_id = c.cid AND r.code = v.phong AND r.is_active));
    END IF;
END $$;

INSERT INTO public.vi_tri_lam_viec (clinic_id, code, ten, ten_ngan, tang, phong,
                                    nhom_nghe, sort, is_active, room_id)
SELECT c.cid, v.code, v.ten, v.ten, r.floor, r.name, v.nhom, v.sort, true, r.id
  FROM _vt v
  JOIN _cs c ON true
  JOIN public.clinic_room r ON r.clinic_id = c.cid AND r.code = v.phong
ON CONFLICT (clinic_id, code) DO UPDATE
   SET ten = EXCLUDED.ten, ten_ngan = EXCLUDED.ten_ngan, tang = EXCLUDED.tang,
       phong = EXCLUDED.phong, nhom_nghe = EXCLUDED.nhom_nghe, sort = EXCLUDED.sort,
       room_id = EXCLUDED.room_id, is_active = true;

-- Vị trí HN cũ không còn trong sơ đồ → tắt (không xoá).
UPDATE public.vi_tri_lam_viec v SET is_active = false
  FROM _cs c
 WHERE v.clinic_id = c.cid AND v.code LIKE 'HN\_\_%' AND v.is_active
   AND v.code NOT IN (SELECT code FROM _vt);

-- Vai được vào trạm cho mã mới: chép từ mã mẫu Kim Ngưu.
INSERT INTO public.vai_duoc_vao_tram (clinic_id, tram_ma, vai, ghi_chu)
SELECT DISTINCT c.cid, v.code, t.vai, t.ghi_chu
  FROM _vt v
  JOIN _cs c ON true
  JOIN public.vai_duoc_vao_tram t
    ON t.clinic_id = c.cid
   AND t.tram_ma = regexp_replace(regexp_replace(v.code, '^[A-Z0-9]+__', ''), '__[0-9]+$', '')
 WHERE NOT EXISTS (SELECT 1 FROM public.vai_duoc_vao_tram x
                    WHERE x.clinic_id = c.cid AND x.tram_ma = v.code AND x.vai = t.vai);

-- ── 3. Trưởng ca: cột Tầng ghi "Điều phối", nằm dòng cuối.
UPDATE public.vi_tri_lam_viec v SET tang = 'Điều phối', sort = 900
  FROM _cs c
 WHERE v.clinic_id = c.cid AND v.code = 'DIEU_PHOI';

-- ── Bảng kiểm: lịch Hào Nam sẽ hiện thế này
SELECT coalesce(r.floor, v.tang) AS tang, coalesce(r.name, v.phong) AS phong, v.ten,
       v.code
  FROM public.vi_tri_lam_viec v
  JOIN _cs c ON v.clinic_id = c.cid
  LEFT JOIN public.clinic_room r ON r.id = v.room_id
 WHERE v.is_active AND (v.code LIKE 'HN\_\_%' OR v.room_id IS NULL)
 ORDER BY v.sort, v.code;

\if :that
COMMIT;
\echo 'ĐÃ GHI THẬT.'
\else
ROLLBACK;
\echo 'CHẠY THỬ — đã ROLLBACK. Chạy lại với -v that=1 để ghi.'
\endif
