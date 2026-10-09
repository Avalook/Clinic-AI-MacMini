-- Ô TUỲ CHỌN + ĐƠN VỊ cho mẫu kết quả (Tuyền 09/10/2026).
--
-- Gốc: mọi mẫu đều có ô "Đề nghị" để trống, nên lần Hoàn tất nào cũng in "Còn 1
-- mục trống: Đề nghị (chỉ nhắc)" — nhân viên tưởng đó là lỗi chặn. Và bản in
-- không có đơn vị: "89.6" thay vì "89.6 mm" — `goi_y` từng gánh cả đơn vị lẫn
-- gợi ý ("tuần + ngày", "PSV cm/s | EDV cm/s | RI", "± grams") nên không in
-- thẳng được.
--
-- Hai khoá mới của MỘT Ô (kiểm ở `phieu_kham/kiem_khung_mau.py`):
--   tuy_chon: true  → không tính vào "còn trống" (`form_engine_service._con_trong`).
--   don_vi: "mm"    → màn nhập hiện bên phải ô, bản in nối " mm" sau giá trị.
--
-- Việc của migration: với MỌI mẫu kết quả (`KQ_%`) ĐANG DÙNG của mọi phòng khám,
-- ra phiên bản mới DỰNG TỪ KHUNG ĐANG DÙNG TRONG DB (không từ JSON seed — quản lý
-- có thể đã sửa mẫu trên màn; dựng từ seed là đè mất). Chỉ đổi hai chỗ:
--   - ô ma = 'de_nghi'                          → tuy_chon = true;
--   - ô chữ ngắn / số có goi_y là ĐƠN VỊ THUẦN  → don_vi = goi_y (goi_y giữ nguyên).
-- Mẫu không có gì để đổi thì KHÔNG ra phiên bản mới. Bản cũ → RETIRED như
-- `FormEngineService.xuat_ban` (cùng khoá tư vấn theo mẫu — người đang bấm Xuất
-- bản trên màn chạy nối tiếp, không chèn trùng số bản). Phiếu đã điền ghim bản
-- cũ: không chữ nào của chúng đổi.
--
-- `xuat_ban_boi` CHÉP từ bản trước: nội dung vẫn là của người đã duyệt nó (chỉ
-- thêm hai cờ). Để NULL là đánh dấu "hệ thống dựng" — migration mẫu sau này chỉ
-- đè bản NULL (vd 20260926000004) và sẽ đè mất mẫu quản lý đã sửa.
--
-- Bảy phiếu khám (form không mang `KQ_`) có khung và luật khác (`khung.py`) —
-- không đụng. Chạy lại được: khung đã đủ cờ thì bỏ qua.

CREATE OR REPLACE FUNCTION public.o_tuy_chon_don_vi(o jsonb)
RETURNS jsonb
LANGUAGE sql
IMMUTABLE
SET search_path = public
AS $fn$
  SELECT CASE
    WHEN jsonb_typeof(o) IS DISTINCT FROM 'object' THEN o
    ELSE o
      || CASE WHEN o ->> 'ma' = 'de_nghi' AND NOT (o ? 'tuy_chon')
              THEN '{"tuy_chon": true}'::jsonb ELSE '{}'::jsonb END
      || CASE WHEN NOT (o ? 'don_vi')
               AND coalesce(o ->> 'kieu', '') IN ('text', 'so')
               AND o ->> 'goi_y' IN ('mm', 'cm', 'cm/s', 'chu kỳ/phút', 'lần/phút',
                                     'điểm', '%', 'ml', 'gram', 'grams')
              THEN jsonb_build_object('don_vi', o ->> 'goi_y') ELSE '{}'::jsonb END
  END
$fn$;

COMMENT ON FUNCTION public.o_tuy_chon_don_vi(jsonb) IS
'Một ô mẫu kết quả: de_nghi → tuy_chon; goi_y là đơn vị thuần → don_vi (09/10/2026).';

CREATE OR REPLACE FUNCTION public.khung_tuy_chon_don_vi(khung jsonb)
RETURNS jsonb
LANGUAGE sql
IMMUTABLE
SET search_path = public
AS $fn$
  SELECT CASE
    WHEN jsonb_typeof(khung) IS DISTINCT FROM 'array' THEN khung
    ELSE coalesce((
      SELECT jsonb_agg(
               CASE WHEN jsonb_typeof(m -> 'block') = 'array'
                    THEN jsonb_set(m, '{block}', coalesce((
                           SELECT jsonb_agg(public.o_tuy_chon_don_vi(o) ORDER BY i)
                             FROM jsonb_array_elements(m -> 'block')
                                  WITH ORDINALITY AS b(o, i)), '[]'::jsonb))
                    ELSE m END
               ORDER BY mi)
        FROM jsonb_array_elements(khung) WITH ORDINALITY AS x(m, mi)), '[]'::jsonb)
  END
$fn$;

COMMENT ON FUNCTION public.khung_tuy_chon_don_vi(jsonb) IS
'Cả khung mẫu kết quả qua o_tuy_chon_don_vi — giữ nguyên thứ tự mục / ô (09/10/2026).';

CREATE OR REPLACE FUNCTION public.mau_ket_qua_tuy_chon_don_vi()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE
  r record;
  hien record;
  khung_moi jsonb;
  n integer := 0;
BEGIN
  FOR r IN
    SELECT d.clinic_id, d.form_id
      FROM form_definition d
     WHERE d.trang_thai = 'PUBLISHED'
       AND d.form_id LIKE 'KQ\_%'
       AND public.khung_tuy_chon_don_vi(d.khung) IS DISTINCT FROM d.khung
     ORDER BY d.clinic_id, d.form_id
  LOOP
    -- Cùng khoá với `FormEngineService.xuat_ban`, rồi ĐỌC LẠI bản đang dùng:
    -- người vừa xuất bản trên màn thì dựng từ bản của họ.
    PERFORM pg_advisory_xact_lock(
      hashtext('bieu_mau:' || r.clinic_id::text || ':' || r.form_id));
    SELECT d.version, d.ten, d.nhom, d.khung, d.xuat_ban_boi INTO hien
      FROM form_definition d
     WHERE d.clinic_id = r.clinic_id AND d.form_id = r.form_id
       AND d.trang_thai = 'PUBLISHED'
     FOR UPDATE;
    IF NOT FOUND THEN
      CONTINUE;
    END IF;
    khung_moi := public.khung_tuy_chon_don_vi(hien.khung);
    IF khung_moi IS NOT DISTINCT FROM hien.khung THEN
      CONTINUE;
    END IF;

    UPDATE form_definition SET trang_thai = 'RETIRED'
     WHERE clinic_id = r.clinic_id AND form_id = r.form_id
       AND trang_thai = 'PUBLISHED';
    INSERT INTO form_definition
        (clinic_id, form_id, version, ten, nhom, khung, trang_thai,
         xuat_ban_boi, xuat_ban_luc)
    SELECT r.clinic_id, r.form_id, max(x.version) + 1, hien.ten, hien.nhom,
           khung_moi, 'PUBLISHED', hien.xuat_ban_boi, now()
      FROM form_definition x
     WHERE x.clinic_id = r.clinic_id AND x.form_id = r.form_id;
    n := n + 1;
  END LOOP;
  RETURN n;
END;
$fn$;

COMMENT ON FUNCTION public.mau_ket_qua_tuy_chon_don_vi() IS
'Mọi mẫu KQ_ đang dùng: ra phiên bản mới có tuy_chon (Đề nghị) + don_vi (từ goi_y đơn vị thuần), dựng từ khung trong DB. Chạy lại được (09/10/2026).';

SELECT public.mau_ket_qua_tuy_chon_don_vi();
