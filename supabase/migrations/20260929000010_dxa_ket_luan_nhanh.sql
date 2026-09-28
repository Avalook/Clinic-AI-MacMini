-- PHIẾU ĐO MẬT ĐỘ XƯƠNG + "KẾT LUẬN NHANH" (Tuyền 29/09/2026).
--
-- "Ở phiếu ĐO MẬT ĐỘ XƯƠNG thì có thêm 3 checkbox: Bình thường, Tiền loãng
-- xương, Loãng xương, để người thao tác tích nhanh — nhớ là nó được LƯU, và IN
-- ra nữa."
--
-- HIỆN TRẠNG. Dịch vụ Đo mật độ xương (CLS_DO_MAT_DO_XUONG, mã phòng khám
-- SP000134) KHÔNG có mẫu kết quả riêng: 17 mẫu v3 dựng theo PDF không có PDF
-- nào cho DXA, nên màn điền kết quả chọn sẵn mẫu CHUNG (nhập tự do,
-- 20260925000008). Thêm ô vào mẫu CHUNG là thêm "loãng xương" cho cả Laser,
-- Biofeedback, thủ thuật… — sai. Nên:
--
--   1. Mẫu MỚI `DO_MAT_DO_XUONG` (form `KQ_DO_MAT_DO_XUONG` bản 1) = đúng ba mục
--      của mẫu CHUNG (giữ mã ô noi_dung / ket_luan / de_nghi) + ô
--      `ket_luan_nhanh` đứng ĐẦU mục Kết luận.
--   2. Ô ấy là kiểu `chon` (CHỌN MỘT — một người không vừa bình thường vừa
--      loãng xương), giá trị lưu là MỘT chuỗi như mọi ô chọn; `hien_thi:
--      "o_tick"` chỉ bảo màn điền vẽ thành ba ô tích xếp ngang thay vì hộp thả
--      xuống (tích ô này bỏ ô kia, bấm lại ô đang tích thì bỏ tích). Bản in in
--      nó như mọi ô chọn: "Kết luận nhanh — Tiền loãng xương" trong khung Kết
--      luận; ô chưa tích thì không in (luật "chỉ in ô đã điền").
--   3. GẮN mẫu vào dịch vụ DXA — chỉ khi dịch vụ ấy CHƯA được quản lý gắn mẫu
--      nào (ngoài mẫu CHUNG): gắn tay là quyết định của quản lý, không chồng lên.
--   4. Mẫu DXA phòng khám đã TỰ tạo (cùng mã DO_MAT_DO_XUONG — tên "Đo mật độ
--      xương" ở Cài đặt → Mẫu kết quả sinh ra đúng mã này) hoặc đã gắn cho dịch
--      vụ DXA: KHÔNG đè nội dung, chỉ THÊM ô `ket_luan_nhanh` vào mục Kết luận
--      (không có mục ấy thì thêm mục "Kết luận nhanh" ở cuối) bằng một phiên bản
--      mới; bản cũ → RETIRED.
--
-- PHIẾU CŨ KHÔNG HỎNG. Phiếu DXA đã điền đang ghim `KQ_CHUNG` (khoá ngoại 3 cột
-- tới đúng phiên bản) — không đụng tới; mở lại / in lại vẫn là mẫu CHUNG. Mẫu
-- CHUNG không đổi một chữ.
--
-- HÀM, để seed.sql gọi lại: trên DB dựng mới migration chạy TRƯỚC khi bảng giá
-- có dịch vụ (seed nạp sau) — bước gắn (3, 4) chỉ ăn khi bảng giá đã có.
-- Chạy lại được: ô đã có thì bỏ qua, gắn rồi thì thôi.

CREATE OR REPLACE FUNCTION public.dxa_ket_luan_nhanh()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE
  o_nhanh constant jsonb := $o$
    {"ma": "ket_luan_nhanh", "ten": "Kết luận nhanh", "kieu": "chon",
     "chon": ["Bình thường", "Tiền loãng xương", "Loãng xương"],
     "hien_thi": "o_tick"}
  $o$::jsonb;
  khung_moi jsonb;
  r record;
  vi_tri integer;
  n integer := 0;
BEGIN
  khung_moi := jsonb_build_array(
    jsonb_build_object('ma', 'ket_qua', 'ten', 'Mô tả / kết quả',
      'block', jsonb_build_array(jsonb_build_object(
        'ma', 'noi_dung', 'ten', 'Mô tả / kết quả', 'kieu', 'doan_van'))),
    jsonb_build_object('ma', 'ket_luan', 'ten', 'Kết luận',
      'block', jsonb_build_array(o_nhanh, jsonb_build_object(
        'ma', 'ket_luan', 'ten', 'Kết luận', 'kieu', 'doan_van'))),
    jsonb_build_object('ma', 'de_nghi', 'ten', 'Đề nghị',
      'block', jsonb_build_array(jsonb_build_object(
        'ma', 'de_nghi', 'ten', 'Đề nghị', 'kieu', 'doan_van'))));

  -- 1. Danh mục mẫu + bản 1 (chưa có bản nào của mã này).
  INSERT INTO ket_qua_mau (clinic_id, ma, nhom, ten)
  SELECT c.id, 'DO_MAT_DO_XUONG', 'Thăm dò chức năng', 'Kết quả đo mật độ xương'
    FROM clinic c
  ON CONFLICT (clinic_id, ma) DO NOTHING;

  INSERT INTO form_definition
      (clinic_id, form_id, version, ten, nhom, khung, trang_thai,
       xuat_ban_boi, xuat_ban_luc)
  SELECT k.clinic_id, 'KQ_DO_MAT_DO_XUONG', 1, k.ten, k.nhom, khung_moi,
         'PUBLISHED', NULL, now()
    FROM ket_qua_mau k
   WHERE k.ma = 'DO_MAT_DO_XUONG'
     AND NOT EXISTS (SELECT 1 FROM form_definition d
                      WHERE d.clinic_id = k.clinic_id
                        AND d.form_id = 'KQ_DO_MAT_DO_XUONG');
  GET DIAGNOSTICS vi_tri = ROW_COUNT;
  n := n + vi_tri;

  -- 3. Gắn cho dịch vụ DXA chưa có mẫu gắn tay (mẫu CHUNG không tính).
  INSERT INTO dich_vu_mau_ket_qua (clinic_id, service_code, mau)
  SELECT p.clinic_id, p.service_code, 'DO_MAT_DO_XUONG'
    FROM service_price p
    JOIN ket_qua_mau k ON k.clinic_id = p.clinic_id AND k.ma = 'DO_MAT_DO_XUONG'
   WHERE p."group" = 'dich_vu'
     AND (p.service_code = 'CLS_DO_MAT_DO_XUONG' OR p.ma_kiotviet = 'SP000134')
     AND NOT EXISTS (SELECT 1 FROM dich_vu_mau_ket_qua g
                      WHERE g.clinic_id = p.clinic_id
                        AND g.service_code = p.service_code
                        AND g.mau <> 'CHUNG')
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS vi_tri = ROW_COUNT;
  n := n + vi_tri;

  -- 4. Mẫu DXA đang dùng mà thiếu ô: thêm ô, xuất bản bản mới.
  FOR r IN
    SELECT d.clinic_id, d.form_id, d.version, d.ten, d.nhom, d.khung
      FROM form_definition d
     WHERE d.trang_thai = 'PUBLISHED'
       AND d.form_id <> 'KQ_CHUNG'
       AND (d.form_id = 'KQ_DO_MAT_DO_XUONG'
            OR d.form_id IN (
              SELECT 'KQ_' || g.mau
                FROM dich_vu_mau_ket_qua g
                JOIN service_price p ON p.clinic_id = g.clinic_id
                                    AND p.service_code = g.service_code
               WHERE g.clinic_id = d.clinic_id
                 AND p."group" = 'dich_vu'
                 AND (p.service_code = 'CLS_DO_MAT_DO_XUONG'
                      OR p.ma_kiotviet = 'SP000134')))
       AND NOT EXISTS (
             SELECT 1 FROM jsonb_array_elements(d.khung) m,
                           jsonb_array_elements(m -> 'block') o
              WHERE o ->> 'ma' = 'ket_luan_nhanh')
     FOR UPDATE
  LOOP
    SELECT i - 1 INTO vi_tri
      FROM jsonb_array_elements(r.khung) WITH ORDINALITY AS m(muc, i)
     WHERE muc ->> 'ma' = 'ket_luan'
     LIMIT 1;
    IF vi_tri IS NOT NULL THEN
      khung_moi := jsonb_set(
        r.khung, ARRAY[vi_tri::text, 'block'],
        jsonb_build_array(o_nhanh) || (r.khung -> vi_tri -> 'block'));
    ELSE
      khung_moi := r.khung || jsonb_build_array(jsonb_build_object(
        'ma', CASE WHEN EXISTS (SELECT 1 FROM jsonb_array_elements(r.khung) m
                                 WHERE m ->> 'ma' = 'ket_luan_nhanh')
                   THEN 'ket_luan_nhanh_2' ELSE 'ket_luan_nhanh' END,
        'ten', 'Kết luận nhanh',
        'block', jsonb_build_array(o_nhanh)));
    END IF;

    UPDATE form_definition SET trang_thai = 'RETIRED'
     WHERE clinic_id = r.clinic_id AND form_id = r.form_id
       AND version = r.version;
    INSERT INTO form_definition
        (clinic_id, form_id, version, ten, nhom, khung, trang_thai,
         xuat_ban_boi, xuat_ban_luc)
    SELECT r.clinic_id, r.form_id, max(x.version) + 1, r.ten, r.nhom,
           khung_moi, 'PUBLISHED', NULL, now()
      FROM form_definition x
     WHERE x.clinic_id = r.clinic_id AND x.form_id = r.form_id;
    n := n + 1;
  END LOOP;

  RETURN n;
END;
$fn$;

COMMENT ON FUNCTION public.dxa_ket_luan_nhanh() IS
'Mẫu kết quả Đo mật độ xương + ô "Kết luận nhanh" (Bình thường / Tiền loãng xương / Loãng xương), gắn cho dịch vụ DXA (29/09/2026). Chạy lại được; seed.sql gọi lại sau khi nạp bảng giá.';

SELECT public.dxa_ket_luan_nhanh();
