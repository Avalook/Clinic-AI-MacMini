-- PHIẾU KẾT QUẢ CHỈ MỘT Ô "MÔ TẢ" + LỄ TÂN CHỈ ĐỊNH — nước tiểu, monitor thai
-- (checklist phòng khám mục 1 + 4.1, Tuyền 09/10/2026).
--
-- "Đưa đo monitoring thai về cùng đo sinh hiệu và cho lễ tân chỉ định. Phiếu
-- kết quả nước tiểu, monitor: chỉ cần một ô Mô tả (tuỳ chọn); bỏ Kết luận và Đề
-- nghị. Monitoring thai gồm: Monitor sản khoa đơn thai, Monitor Sản khoa song
-- thai - đa thai." ĐO MẬT ĐỘ XƯƠNG KHÔNG ĐỔI (Tuyền đính chính 09/10 — mẫu DXA
-- giữ Mô tả / kết quả · Kết luận (ô tích + chữ) · Đề nghị).
--
-- HIỆN TRẠNG. Nước tiểu và monitor chưa gắn mẫu nên rơi về mẫu CHUNG (Mô tả /
-- kết quả · Kết luận · Đề nghị). KHÔNG sửa CHUNG: Laser, Biofeedback, thủ thuật…
-- cũng dùng nó.
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
--   3. Monitor đơn thai / song thai thành NÚT LÀM THÊM TẠI QUẦY (bảng
--      `lam_them_tai_quay`, 20261002200000) ở cả Tiếp đón lẫn Đo sinh hiệu — lễ
--      tân / người đo tick là chỉ định, làm ngay ở bàn sinh hiệu, giống nút
--      "Nước tiểu". Đã có dòng (quản lý đã chỉnh) thì không đè.
--
-- Cùng tệp (cuối tệp): mục 4.4 siêu âm tử cung chỉ còn mẫu phần phụ
-- (`sa_tc_chi_con_phan_phu`), mục 3 Trưởng ca → "Quản lý ca khám"
-- (`truong_ca_quan_ly_ca_kham`).
--
-- HÀM để seed.sql gọi lại: trên DB dựng mới migration chạy TRƯỚC khi bảng giá
-- có dịch vụ (seed nạp sau), bước 2–3 chỉ ăn khi bảng giá đã có. Chạy lại được:
-- mẫu có rồi thì thôi, gắn rồi thì thôi, nút có rồi thì thôi.

CREATE OR REPLACE FUNCTION public.mau_mo_ta_nuoc_tieu_monitor()
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

  -- 3. Monitor thai: nút làm thêm tại quầy ở Tiếp đón + Đo sinh hiệu.
  INSERT INTO lam_them_tai_quay
      (clinic_id, service_code, nhan, bat, thu_tu, o_tiep_don, o_sinh_hieu)
  SELECT DISTINCT sp.clinic_id, sp.service_code, x.nhan, true, x.thu_tu, true, true
    FROM service_price sp
    JOIN (VALUES ('CLS_CHAY_MONITORING', 'Monitor đơn thai', 30),
                 ('KV_SP000081', 'Monitor song thai', 31)) AS x(ma, nhan, thu_tu)
      ON x.ma = sp.service_code
   WHERE sp."group" = 'dich_vu'
  ON CONFLICT (clinic_id, service_code) DO NOTHING;
  GET DIAGNOSTICS so = ROW_COUNT;
  n := n + so;

  RETURN n;
END;
$fn$;

COMMENT ON FUNCTION public.mau_mo_ta_nuoc_tieu_monitor() IS
'Mẫu MO_TA (một ô Mô tả tuỳ chọn) gắn cho nước tiểu / monitor chưa gắn mẫu; monitor đơn / song thai thành nút làm thêm tại quầy (Tiếp đón + Đo sinh hiệu). Không đụng mẫu đo mật độ xương. Chạy lại được; seed.sql gọi lại sau khi nạp bảng giá (09/10/2026).';

SELECT public.mau_mo_ta_nuoc_tieu_monitor();

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
