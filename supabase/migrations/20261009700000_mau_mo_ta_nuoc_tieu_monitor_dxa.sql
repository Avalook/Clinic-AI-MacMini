-- PHIẾU KẾT QUẢ CHỈ MỘT Ô "MÔ TẢ" — nước tiểu, monitor, đo mật độ xương
-- (checklist phòng khám mục 4.1, Tuyền 09/10/2026).
--
-- "Nước tiểu, monitor và đo mật độ xương: chỉ cần một ô Mô tả, ô đó tuỳ chọn;
-- bỏ Kết luận và Đề nghị. Riêng đo mật độ xương GIỮ ô tích Bình thường / Tiền
-- loãng xương / Loãng xương."
--
-- HIỆN TRẠNG. Nước tiểu và monitor chưa gắn mẫu nên rơi về mẫu CHUNG (Mô tả /
-- kết quả · Kết luận · Đề nghị). KHÔNG sửa CHUNG: Laser, Biofeedback, thủ thuật…
-- cũng dùng nó. Đo mật độ xương có mẫu riêng (20260929000010) ba mục.
--
--   1. Mẫu MỚI `MO_TA` "Kết quả (mô tả)" — form `KQ_MO_TA` bản 1: đúng một mục
--      "Mô tả", một ô `noi_dung` (đoạn văn) tuỳ chọn. Mọi phòng khám; đã có bản
--      nào thì không đụng (sửa nội dung là việc của màn).
--   2. GẮN `MO_TA` cho bốn dịch vụ theo service_code (nước tiểu, nước tiểu sau
--      xuất tinh, monitor đơn thai, monitor song/đa thai) — chỉ khi phòng khám
--      có dịch vụ ấy trong bảng giá VÀ dịch vụ ấy CHƯA có dòng gắn mẫu nào: mẫu
--      quản lý đã gắn tay (kể cả CHUNG) là quyết định của họ, không chồng lên.
--      result_mode mặc định INLINE = đúng như lúc chưa gắn
--      (`FormEngineService._result_mode`), nên dây báo kết quả không đổi.
--   3. `KQ_DO_MAT_DO_XUONG`: ra phiên bản mới DỰNG TỪ BẢN ĐANG DÙNG TRONG DB
--      (quản lý có thể đã sửa trên màn — dựng từ seed là đè mất), qua
--      `khung_dxa_mo_ta`:
--        - ô `noi_dung` → tên "Mô tả", tuỳ chọn; mục chứa nó tên "Mô tả";
--        - ô tích `ket_luan_nhanh` chuyển vào CÙNG mục, ngay dưới ô Mô tả;
--        - bỏ ô `ket_luan`, ô `de_nghi` và cả mục `de_nghi`; mục nào hết ô thì bỏ;
--        - mọi mục / ô khác quản lý đã thêm: giữ nguyên, giữ thứ tự.
--      Khung không có ô `noi_dung`, hoặc đã không còn ô Kết luận / Đề nghị
--      (quản lý đã sửa tay) → không đụng, không ra bản mới. Bản cũ
--      → RETIRED như `FormEngineService.xuat_ban` (cùng khoá tư vấn theo mẫu).
--      `xuat_ban_boi` CHÉP từ bản trước như 20261009300000.
--
-- PHIẾU CŨ KHÔNG HỎNG: phiếu đã điền ghim đúng phiên bản cũ (khoá ngoại 3 cột) —
-- mở lại / in lại vẫn đủ Kết luận, Đề nghị như lúc điền. Dữ liệu `ket_luan` cũ
-- không mất, chỉ phiếu MỚI không còn ô ấy.
--
-- BẢN IN không phải sửa: in theo khung của chính phiếu, chỉ in ô đã điền; mục
-- "Mô tả" có hai ô thì in dạng nhãn — giá trị ("Kết luận nhanh — Loãng xương").
--
-- Cùng tệp (cuối tệp): mục 4.4 siêu âm tử cung chỉ còn mẫu phần phụ
-- (`sa_tc_chi_con_phan_phu`), mục 3 Trưởng ca → "Quản lý ca khám"
-- (`truong_ca_quan_ly_ca_kham`).
--
-- HÀM để seed.sql gọi lại: trên DB dựng mới migration chạy TRƯỚC khi bảng giá
-- có dịch vụ (seed nạp sau), bước 2 chỉ ăn khi bảng giá đã có. Chạy lại được:
-- mẫu có rồi thì thôi, gắn rồi thì thôi, khung DXA đã đúng thì không ra bản mới.

CREATE OR REPLACE FUNCTION public.khung_dxa_mo_ta(khung jsonb)
RETURNS jsonb
LANGUAGE plpgsql
IMMUTABLE
SET search_path = public
AS $fn$
DECLARE
  o_nhanh jsonb;
  muc jsonb;
  o jsonb;
  block_moi jsonb;
  co_mo_ta boolean;
  ra jsonb := '[]'::jsonb;
BEGIN
  IF jsonb_typeof(khung) IS DISTINCT FROM 'array' THEN
    RETURN khung;
  END IF;
  -- Đã không còn Kết luận chữ / Đề nghị (vd quản lý đã tự sửa trên màn — staging
  -- 09/10 có bản 3 dựng tay) → coi như đã đúng, KHÔNG ra thêm bản mới.
  IF NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(khung) m
     WHERE m ->> 'ma' = 'de_nghi'
        OR (jsonb_typeof(m -> 'block') = 'array'
            AND EXISTS (SELECT 1 FROM jsonb_array_elements(m -> 'block') b
                         WHERE b ->> 'ma' IN ('ket_luan', 'de_nghi')))) THEN
    RETURN khung;
  END IF;
  -- Không có ô Mô tả thì không biết đặt ô tích vào đâu — để nguyên.
  IF NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(khung) m
     WHERE jsonb_typeof(m -> 'block') = 'array'
       AND EXISTS (SELECT 1 FROM jsonb_array_elements(m -> 'block') b
                    WHERE b ->> 'ma' = 'noi_dung')) THEN
    RETURN khung;
  END IF;

  SELECT b INTO o_nhanh
    FROM jsonb_array_elements(khung) WITH ORDINALITY AS x(m, mi),
         jsonb_array_elements(CASE WHEN jsonb_typeof(m -> 'block') = 'array'
                                   THEN m -> 'block' ELSE '[]'::jsonb END)
           WITH ORDINALITY AS y(b, bi)
   WHERE b ->> 'ma' = 'ket_luan_nhanh'
   ORDER BY mi, bi
   LIMIT 1;

  FOR muc IN
    SELECT m FROM jsonb_array_elements(khung) WITH ORDINALITY AS x(m, mi) ORDER BY mi
  LOOP
    CONTINUE WHEN muc ->> 'ma' = 'de_nghi';
    IF jsonb_typeof(muc -> 'block') IS DISTINCT FROM 'array' THEN
      ra := ra || jsonb_build_array(muc);
      CONTINUE;
    END IF;
    block_moi := '[]'::jsonb;
    co_mo_ta := false;
    FOR o IN
      SELECT b FROM jsonb_array_elements(muc -> 'block') WITH ORDINALITY AS y(b, bi)
       ORDER BY bi
    LOOP
      CONTINUE WHEN o ->> 'ma' IN ('ket_luan', 'de_nghi', 'ket_luan_nhanh');
      IF o ->> 'ma' = 'noi_dung' THEN
        block_moi := block_moi
          || jsonb_build_array(o || '{"ten": "Mô tả", "tuy_chon": true}'::jsonb);
        IF o_nhanh IS NOT NULL THEN
          block_moi := block_moi || jsonb_build_array(o_nhanh);
        END IF;
        co_mo_ta := true;
      ELSE
        block_moi := block_moi || jsonb_build_array(o);
      END IF;
    END LOOP;
    CONTINUE WHEN jsonb_array_length(block_moi) = 0;
    muc := jsonb_set(muc, '{block}', block_moi);
    IF co_mo_ta THEN
      muc := muc || '{"ten": "Mô tả"}'::jsonb;
    END IF;
    ra := ra || jsonb_build_array(muc);
  END LOOP;
  RETURN ra;
END;
$fn$;

COMMENT ON FUNCTION public.khung_dxa_mo_ta(jsonb) IS
'Khung mẫu đo mật độ xương → Mô tả (tuỳ chọn) + ô tích Kết luận nhanh ngay dưới, bỏ Kết luận / Đề nghị; giữ mọi ô khác. Không có ô noi_dung thì trả nguyên (09/10/2026).';

CREATE OR REPLACE FUNCTION public.mau_mo_ta_nuoc_tieu_monitor_dxa()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE
  khung_mo_ta constant jsonb := $k$[
    {"ma": "mo_ta", "ten": "Mô tả",
     "block": [{"ma": "noi_dung", "ten": "Mô tả", "kieu": "doan_van",
                "tuy_chon": true}]}
  ]$k$::jsonb;
  r record;
  hien record;
  khung_moi jsonb;
  so integer;
  n integer := 0;
BEGIN
  -- 1. Mẫu MO_TA cho mọi phòng khám.
  INSERT INTO ket_qua_mau (clinic_id, ma, nhom, ten)
  SELECT c.id, 'MO_TA', 'Chung', 'Kết quả (mô tả)'
    FROM clinic c
  ON CONFLICT (clinic_id, ma) DO NOTHING;

  INSERT INTO form_definition
      (clinic_id, form_id, version, ten, nhom, khung, trang_thai,
       xuat_ban_boi, xuat_ban_luc)
  SELECT k.clinic_id, 'KQ_MO_TA', 1, k.ten, k.nhom, khung_mo_ta,
         'PUBLISHED', NULL, now()
    FROM ket_qua_mau k
   WHERE k.ma = 'MO_TA'
     AND NOT EXISTS (SELECT 1 FROM form_definition d
                      WHERE d.clinic_id = k.clinic_id AND d.form_id = 'KQ_MO_TA');
  GET DIAGNOSTICS so = ROW_COUNT;
  n := n + so;

  -- 2. Gắn cho nước tiểu / monitor chưa có mẫu gắn nào.
  INSERT INTO dich_vu_mau_ket_qua (clinic_id, service_code, mau)
  SELECT DISTINCT p.clinic_id, p.service_code, 'MO_TA'
    FROM service_price p
    JOIN ket_qua_mau k ON k.clinic_id = p.clinic_id AND k.ma = 'MO_TA'
   WHERE p.service_code IN ('CLS_NUOC_TIEU',                -- SP000025
                            'CLS_NUOC_TIEU_SAU_XUAT_TINH',
                            'CLS_CHAY_MONITORING',          -- SP000026 đơn thai
                            'KV_SP000081')                  -- song thai - đa thai
     AND NOT EXISTS (SELECT 1 FROM dich_vu_mau_ket_qua g
                      WHERE g.clinic_id = p.clinic_id
                        AND g.service_code = p.service_code)
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS so = ROW_COUNT;
  n := n + so;

  -- 3. Mẫu đo mật độ xương: Mô tả + ô tích, dựng từ bản đang dùng.
  FOR r IN
    SELECT d.clinic_id
      FROM form_definition d
     WHERE d.form_id = 'KQ_DO_MAT_DO_XUONG' AND d.trang_thai = 'PUBLISHED'
       AND public.khung_dxa_mo_ta(d.khung) IS DISTINCT FROM d.khung
     ORDER BY d.clinic_id
  LOOP
    -- Cùng khoá với `FormEngineService.xuat_ban`, rồi ĐỌC LẠI bản đang dùng.
    PERFORM pg_advisory_xact_lock(
      hashtext('bieu_mau:' || r.clinic_id::text || ':KQ_DO_MAT_DO_XUONG'));
    SELECT d.version, d.ten, d.nhom, d.khung, d.xuat_ban_boi INTO hien
      FROM form_definition d
     WHERE d.clinic_id = r.clinic_id AND d.form_id = 'KQ_DO_MAT_DO_XUONG'
       AND d.trang_thai = 'PUBLISHED'
     FOR UPDATE;
    IF NOT FOUND THEN
      CONTINUE;
    END IF;
    khung_moi := public.khung_dxa_mo_ta(hien.khung);
    IF khung_moi IS NOT DISTINCT FROM hien.khung THEN
      CONTINUE;
    END IF;

    UPDATE form_definition SET trang_thai = 'RETIRED'
     WHERE clinic_id = r.clinic_id AND form_id = 'KQ_DO_MAT_DO_XUONG'
       AND trang_thai = 'PUBLISHED';
    INSERT INTO form_definition
        (clinic_id, form_id, version, ten, nhom, khung, trang_thai,
         xuat_ban_boi, xuat_ban_luc)
    SELECT r.clinic_id, 'KQ_DO_MAT_DO_XUONG', max(x.version) + 1, hien.ten,
           hien.nhom, khung_moi, 'PUBLISHED', hien.xuat_ban_boi, now()
      FROM form_definition x
     WHERE x.clinic_id = r.clinic_id AND x.form_id = 'KQ_DO_MAT_DO_XUONG';
    n := n + 1;
  END LOOP;

  RETURN n;
END;
$fn$;

COMMENT ON FUNCTION public.mau_mo_ta_nuoc_tieu_monitor_dxa() IS
'Mẫu MO_TA (một ô Mô tả tuỳ chọn) gắn cho nước tiểu / monitor chưa gắn mẫu; mẫu đo mật độ xương ra bản Mô tả + ô tích. Chạy lại được; seed.sql gọi lại sau khi nạp bảng giá (09/10/2026).';

SELECT public.mau_mo_ta_nuoc_tieu_monitor_dxa();

-- 4.4 SIÊU ÂM TỬ CUNG: CHỈ CÒN MẪU PHẦN PHỤ (checklist mục 4.4, 09/10/2026).
-- Ba dịch vụ siêu âm tử cung (2D, 4D, KV_SP000080) đang gắn CẢ SA_TC_BT (buồng
-- trứng) lẫn SA_TC_PP (phần phụ) — theo tên, "buồng trứng" đứng trước và được
-- chọn sẵn. Gỡ dòng gắn SA_TC_BT; dịch vụ đang gắn BT mà chưa có PP thì gắn PP
-- TRƯỚC (chép result_mode / thu_tu của dòng BT) rồi mới gỡ — không để dịch vụ
-- nào rơi về mẫu CHUNG. Dịch vụ không gắn BT thì không đụng (gắn tay của quản
-- lý). KHÔNG đụng mẫu SA_TC_BT: phiếu cũ ghim KQ_SA_TC_BT vẫn mở / in được, và
-- dịch vụ khác vẫn gắn được nó trên màn. Chạy lại được.
CREATE OR REPLACE FUNCTION public.sa_tc_chi_con_phan_phu()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE
  dv constant text[] := ARRAY['CLS_SIEU_AM_2D_TC_BT', 'CLS_SIEU_AM_4D_TC_BT',
                              'KV_SP000080'];
  so integer;
  n integer := 0;
BEGIN
  INSERT INTO dich_vu_mau_ket_qua
      (clinic_id, service_code, mau, result_mode, thu_tu)
  SELECT bt.clinic_id, bt.service_code, 'SA_TC_PP', bt.result_mode, bt.thu_tu
    FROM dich_vu_mau_ket_qua bt
    JOIN ket_qua_mau k ON k.clinic_id = bt.clinic_id AND k.ma = 'SA_TC_PP'
   WHERE bt.mau = 'SA_TC_BT' AND bt.service_code = ANY (dv)
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS so = ROW_COUNT;
  n := n + so;

  DELETE FROM dich_vu_mau_ket_qua bt
   WHERE bt.mau = 'SA_TC_BT' AND bt.service_code = ANY (dv)
     AND EXISTS (SELECT 1 FROM dich_vu_mau_ket_qua pp
                  WHERE pp.clinic_id = bt.clinic_id
                    AND pp.service_code = bt.service_code
                    AND pp.mau = 'SA_TC_PP');
  GET DIAGNOSTICS so = ROW_COUNT;
  RETURN n + so;
END;
$fn$;

COMMENT ON FUNCTION public.sa_tc_chi_con_phan_phu() IS
'Siêu âm tử cung 2D/4D/KV_SP000080: gỡ gắn SA_TC_BT, giữ (hoặc gắn trước) SA_TC_PP. Không đụng mẫu SA_TC_BT. Chạy lại được; seed.sql gọi lại (09/10/2026).';

-- Hàm gắn mẫu v3 theo mã phòng khám (20260926000004) bỏ ba cặp SA_TC_BT: gọi
-- lại nó (seed.sql, hay ai chạy tay) không được gắn lại BT vừa gỡ. Danh sách còn
-- lại chép nguyên.
CREATE OR REPLACE FUNCTION public.gan_mau_ket_qua_theo_kiotviet()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE n integer;
BEGIN
  INSERT INTO public.dich_vu_mau_ket_qua (clinic_id, service_code, mau)
  SELECT p.clinic_id, p.service_code, g.mau
    FROM (VALUES
  ('SA_THAI_SOM', 'SP000008'),
  ('SA_THAI_SOM', 'SP000132'),
  ('SA_THAI_QUY_1', 'SP000098'),
  ('SA_THAI_QUY_1', 'SP000008'),
  ('SA_THAI_QUY_1', 'SP000078'),
  ('SA_THAI_QUY_23', 'SP000009'),
  ('SA_THAI_QUY_23', 'SP000078'),
  ('SA_THAI_QUY_23', 'SP000010'),
  ('SA_SONG_THAI_QUY_1', 'SP000132'),
  ('SA_SONG_THAI_QUY_23', 'SP000084'),
  ('SA_SONG_THAI_QUY_23', 'SP000085'),
  ('SA_TC_PP', 'SP000013'),
  ('SA_TC_PP', 'SP000014'),
  ('SA_TC_PP', 'SP000080'),
  ('SA_VU', 'SP000015'),
  ('SA_VU', 'SP000080'),
  ('SA_GIAP', 'SP000017'),
  ('SA_GIAP', 'SP000080'),
  ('SA_OBUNG', 'SP000016'),
  ('SA_OBUNG', 'SP000080'),
  ('SA_TINH_HOAN', 'SP000019'),
  ('SA_MACH_CANH', 'SP000018'),
  ('SA_MACH_CANH', 'SP000080'),
  ('SA_MACH_THAN', 'SP000099'),
  ('SA_DOPPLER_AM_VAT', 'SP000125'),
  ('SOI_AM_HO', 'SP000163'),
  ('XN_HPV', 'SP000028'),
  ('XN_HPV', 'SP000170'),
  ('XN_PCR_STDS', 'SP000171')
    ) AS g(mau, ma_kv)
    JOIN public.service_price p
      ON p.ma_kiotviet = g.ma_kv AND p."group" = 'dich_vu'
    JOIN public.ket_qua_mau k ON k.clinic_id = p.clinic_id AND k.ma = g.mau
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$fn$;

SELECT public.sa_tc_chi_con_phan_phu();

-- 3 TRƯỞNG CA → "Quản lý ca khám" (checklist mục 3, 09/10/2026). Vị trí
-- `DIEU_PHOI` không có phòng / tầng nên lịch xếp nó vào nhóm trống. Chỉ điền
-- chỗ đang TRỐNG (tầng còn đổi từ nhãn cũ "Điều phối"); quản lý đã đặt tay thì
-- giữ. KHÔNG đụng room_id (phòng thật là việc của màn). Chạy lại được.
CREATE OR REPLACE FUNCTION public.truong_ca_quan_ly_ca_kham()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE n integer;
BEGIN
  UPDATE vi_tri_lam_viec
     SET phong = CASE WHEN coalesce(btrim(phong), '') = ''
                      THEN 'Quản lý ca khám' ELSE phong END,
         tang = CASE WHEN coalesce(btrim(tang), '') IN ('', 'Điều phối')
                     THEN 'Quản lý ca khám' ELSE tang END
   WHERE code = 'DIEU_PHOI'
     AND (coalesce(btrim(phong), '') = ''
          OR coalesce(btrim(tang), '') IN ('', 'Điều phối'));
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$fn$;

COMMENT ON FUNCTION public.truong_ca_quan_ly_ca_kham() IS
'Vị trí DIEU_PHOI (Trưởng ca): phòng / tầng trống (tầng "Điều phối") → "Quản lý ca khám". Không đụng room_id. Chạy lại được (09/10/2026).';

SELECT public.truong_ca_quan_ly_ca_kham();
