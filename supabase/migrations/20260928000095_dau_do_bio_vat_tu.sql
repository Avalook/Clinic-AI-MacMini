-- ĐẦU DÒ BIO — vật tư bán ở quầy thuốc (C2, đợt 3, 27/09/2026).
--
-- Phòng khám: tập máy Bio / đo trương lực cơ sàn chậu "chưa bao gồm đầu dò" —
-- khách mua đầu dò riêng ở quầy. KiotViet có hai mã (nhóm "Nguyên liệu tiêu
-- hao"), danh mục kho chưa có → quầy không bán được.
--   SP000152  Đầu dò Bio 1 lần       300.000đ / cái
--   SP000153  Đầu dò Bio nhiều lần   900.000đ / cái
--
-- Vào `drug_catalog` (danh mục kho duy nhất của quầy thuốc, cùng khuôn
-- 20260925000014): KHÔNG thêm cột loại hàng — nhóm KiotViet ghi ở `group_label`.
-- Lô / tồn KHÔNG nạp: nhà thuốc nhập ở Kho thuốc. Chưa có lô thì quầy vẫn thu
-- được tiền, bước giao hàng bị chặn tới khi nhập lô (luật kho sẵn có).
--
-- Gói trong MỘT hàm, như 20260925000014: migration gọi trên DB đang chạy (đã có
-- nhân sự); seed.sql gọi lại SAU `chuan_hoa_danh_muc_thuoc_kiotviet()` — hàm ấy
-- TẮT mọi mặt hàng ngoài 82 mã chuẩn, nên thêm trước nó là bị tắt lại.
-- Chạy lại được: tìm theo mã hàng, rồi theo tên (khoá `(clinic_id, name_raw)`);
-- có rồi thì cập nhật giá / đơn vị / nhóm và bật lại, không đẻ dòng trùng.

CREATE OR REPLACE FUNCTION public.them_dau_do_bio()
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $fn$
DECLARE
  c record;
  r record;
  id_co uuid;
  n integer := 0;
BEGIN
  FOR c IN SELECT DISTINCT d.clinic_id AS id FROM public.drug_catalog d LOOP
    FOR r IN
      SELECT * FROM (VALUES
        ('Đầu dò Bio 1 lần', 'SP000152', 300000::numeric),
        ('Đầu dò Bio nhiều lần', 'SP000153', 900000::numeric)
      ) AS v(ten, ma_hang, gia)
    LOOP
      SELECT d.id INTO id_co
        FROM public.drug_catalog d
       WHERE d.clinic_id = c.id
         AND (d.ma_hang = r.ma_hang OR d.name_raw = r.ten)
       ORDER BY (d.ma_hang = r.ma_hang) DESC NULLS LAST, d.created_at, d.id
       LIMIT 1;
      IF id_co IS NULL THEN
        INSERT INTO drug_catalog
            (clinic_id, name_raw, name_base, group_label, unit_price,
             needs_review, is_active, ma_hang, don_vi_ban, luu_y)
        VALUES (c.id, r.ten, r.ten, 'Nguyên liệu tiêu hao', r.gia,
                false, true, r.ma_hang, 'cái',
                'Vật tư dùng kèm máy Bio (tập / đo trương lực cơ sàn chậu).')
        ON CONFLICT (clinic_id, name_raw) DO NOTHING;
      ELSE
        UPDATE public.drug_catalog
           SET name_raw = r.ten, name_base = r.ten,
               group_label = 'Nguyên liệu tiêu hao', unit_price = r.gia,
               is_active = true, ma_hang = r.ma_hang, don_vi_ban = 'cái'
         WHERE id = id_co;
      END IF;
      n := n + 1;
    END LOOP;
  END LOOP;
  RETURN n;
END;
$fn$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.staff) THEN
    PERFORM public.them_dau_do_bio();
  END IF;
END;
$$;
