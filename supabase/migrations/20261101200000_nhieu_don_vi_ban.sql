-- NHIỀU ĐƠN VỊ BÁN + GIÁ THEO ĐƠN VỊ cho thuốc (Tuyền 31/10/2026).
--
-- Khách đòi mua hộp mà danh mục chỉ có "gói 85.000đ": mỗi thuốc giờ có thêm các
-- đơn vị bán người dùng tự khai — đơn vị, hệ số về đơn vị gốc, giá riêng.
--
-- Đơn vị gốc vẫn là `drug_catalog.don_vi_ban`, giá gốc vẫn là `unit_price` (KHÔNG
-- đổi nghĩa). Mở rộng `thuoc_quy_doi` chứ không thêm bảng: hệ số "1 hộp = 30 gói"
-- lúc nhập và lúc bán là MỘT con số, hai bảng thì sớm muộn lệch nhau.
--
-- Dòng cũ của `thuoc_quy_doi` (đơn vị nhập đã nhớ) giữ `dang_ban = false`: nhập
-- và quy đổi lô vẫn dùng được, nhưng chưa bán theo đơn vị đó tới khi có giá.
--
-- `payment_bill_line.he_so` = hệ số LÚC THU của dòng bán theo đơn vị khác đơn vị
-- gốc: sửa hệ số ở danh mục sau đó không làm sai dòng đã thu (giao / khách trả).
-- NULL = bán theo đơn vị gốc, hoặc đơn vị chưa có trong bảng lúc thu.
--
-- Chỉ THÊM. Chạy lại được, không BEGIN/COMMIT.
-- Hoàn tác (nếu cần, trước khi có dữ liệu mới):
--   ALTER TABLE public.payment_bill_line DROP COLUMN IF EXISTS he_so;
--   ALTER TABLE public.drug_return DROP COLUMN IF EXISTS so_luong_ban;
--   ALTER TABLE public.thuoc_quy_doi DROP CONSTRAINT IF EXISTS thuoc_quy_doi_ban_phai_co_gia,
--       DROP COLUMN IF EXISTS gia, DROP COLUMN IF EXISTS dang_ban;
--   DROP FUNCTION IF EXISTS public.he_so_don_vi(uuid, uuid, text);
--   DROP FUNCTION IF EXISTS public.chuan_don_vi(text);

ALTER TABLE public.thuoc_quy_doi ADD COLUMN IF NOT EXISTS gia numeric(12,0);
ALTER TABLE public.thuoc_quy_doi ADD COLUMN IF NOT EXISTS dang_ban boolean NOT NULL DEFAULT false;

ALTER TABLE public.thuoc_quy_doi DROP CONSTRAINT IF EXISTS thuoc_quy_doi_gia_khong_am;
ALTER TABLE public.thuoc_quy_doi ADD CONSTRAINT thuoc_quy_doi_gia_khong_am
    CHECK (gia IS NULL OR gia >= 0);
-- Đang bán thì phải có giá LƯU RÕ: không tính ngầm hệ số × giá gốc lúc thu.
ALTER TABLE public.thuoc_quy_doi DROP CONSTRAINT IF EXISTS thuoc_quy_doi_ban_phai_co_gia;
ALTER TABLE public.thuoc_quy_doi ADD CONSTRAINT thuoc_quy_doi_ban_phai_co_gia
    CHECK (NOT dang_ban OR gia IS NOT NULL);

COMMENT ON TABLE public.thuoc_quy_doi IS
'Đơn vị khác đơn vị gốc của từng thuốc: "1 <don_vi> = <he_so> đơn vị gốc (don_vi_ban)". Dùng cho quy đổi lúc nhập (17/10/2026) và bán theo nhiều đơn vị (31/10/2026: gia, dang_ban).';
COMMENT ON COLUMN public.thuoc_quy_doi.gia IS
'Giá bán MỘT đơn vị này, lưu rõ. NULL = chưa bán theo đơn vị này (chỉ dùng để quy đổi).';
COMMENT ON COLUMN public.thuoc_quy_doi.dang_ban IS
'Quầy chọn được đơn vị này. Tắt = không bán mới, hệ số giữ nguyên cho lô và dòng cũ.';

ALTER TABLE public.payment_bill_line ADD COLUMN IF NOT EXISTS he_so numeric(12,3);
ALTER TABLE public.payment_bill_line DROP CONSTRAINT IF EXISTS payment_bill_line_he_so_duong;
ALTER TABLE public.payment_bill_line ADD CONSTRAINT payment_bill_line_he_so_duong
    CHECK (he_so IS NULL OR he_so > 0);
COMMENT ON COLUMN public.payment_bill_line.he_so IS
'Hệ số về đơn vị gốc lúc thu của dòng bán theo đơn vị khác đơn vị gốc. NULL = đơn vị gốc / đơn vị chưa khai.';

-- Khách trả ghi theo đơn vị LÔ (cột `returned_qty`, trigger đối chiếu sổ kho). Sổ nợ
-- và hoàn tiền cần số theo đơn vị ĐÃ BÁN: trả 15 gói của dòng 1 hộp (30 gói) = 0,5.
-- NULL = cùng đơn vị, dùng `returned_qty`.
ALTER TABLE public.drug_return ADD COLUMN IF NOT EXISTS so_luong_ban numeric;
ALTER TABLE public.drug_return DROP CONSTRAINT IF EXISTS drug_return_so_luong_ban_duong;
ALTER TABLE public.drug_return ADD CONSTRAINT drug_return_so_luong_ban_duong
    CHECK (so_luong_ban IS NULL OR so_luong_ban > 0);
COMMENT ON COLUMN public.drug_return.so_luong_ban IS
'Phần trả tính theo đơn vị đã bán của dòng đơn, khi dòng bán khác đơn vị lô. NULL = bằng returned_qty.';

-- Cùng cách so với `_don_vi()` ở backend: "Hộp", " hộp " là một đơn vị.
CREATE OR REPLACE FUNCTION public.chuan_don_vi(p_don_vi text)
RETURNS text
LANGUAGE sql STABLE
AS $$
    SELECT lower(btrim(regexp_replace(normalize(coalesce(p_don_vi, ''), NFC), '\s+', ' ', 'g')))
$$;

-- Hệ số đổi `p_don_vi` về đơn vị gốc của thuốc: 1 khi đúng đơn vị gốc, hệ số trong
-- bảng khi đã khai, NULL khi không đổi được (không đoán). Rỗng = NULL.
CREATE OR REPLACE FUNCTION public.he_so_don_vi(p_clinic uuid, p_thuoc uuid, p_don_vi text)
RETURNS numeric
LANGUAGE sql STABLE
AS $$
    SELECT CASE
        WHEN public.chuan_don_vi(p_don_vi) = '' THEN NULL
        WHEN public.chuan_don_vi(p_don_vi) = (
                 SELECT public.chuan_don_vi(c.don_vi_ban) FROM public.drug_catalog c
                  WHERE c.id = p_thuoc AND c.clinic_id = p_clinic) THEN 1
        ELSE (SELECT q.he_so FROM public.thuoc_quy_doi q
               WHERE q.clinic_id = p_clinic AND q.drug_catalog_id = p_thuoc
                 AND q.don_vi = public.chuan_don_vi(p_don_vi))
    END
$$;

NOTIFY pgrst, 'reload schema';
