-- ĐƠN VỊ MẸ = ĐƠN VỊ KÊ MẶC ĐỊNH của một thuốc (kế hoạch
-- docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 14 C1, mục 16 PR A — 26/11/2026).
--
-- Bác sĩ nghĩ "1 hộp", kho đếm "viên". Đơn vị mẹ là một dòng của `thuoc_quy_doi`
-- được đánh dấu `mac_dinh_ke`; không dòng nào có cờ thì mẹ = đơn vị gốc
-- (`drug_catalog.don_vi_ban`) như trước.
--
-- LUẬT MỚI: ô đơn vị của dòng đơn để TRỐNG = đơn vị MẸ (trước đây = gốc). Chưa thuốc
-- nào có cờ nên mọi số hiện tại giữ nguyên nghĩa. Bản Python của luật:
-- `BangDonVi.don_vi_dong` (services/don_vi_thuoc.py) — hai bên phải đi cùng nhau.
--
-- Chỉ THÊM một cột + một chỉ mục + thay thân hàm `he_so_don_vi` (nhánh chữ rỗng).
-- Chạy lại được, không BEGIN/COMMIT.
-- Hoàn tác (trước khi có cờ nào được bật):
--   DROP INDEX IF EXISTS public.thuoc_quy_doi_mot_don_vi_me;
--   ALTER TABLE public.thuoc_quy_doi DROP CONSTRAINT IF EXISTS thuoc_quy_doi_me_phai_dang_ban,
--       DROP COLUMN IF EXISTS mac_dinh_ke;
--   rồi áp lại thân `he_so_don_vi` của 20261101400000_gan_lo_tu_kho_theo_quy_doi.sql.

ALTER TABLE public.thuoc_quy_doi
    ADD COLUMN IF NOT EXISTS mac_dinh_ke boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN public.thuoc_quy_doi.mac_dinh_ke IS
'Đơn vị MẸ = đơn vị kê mặc định (26/11/2026). Dòng đơn để trống đơn vị hiểu theo đơn vị này. Không dòng nào bật = mẹ là đơn vị gốc.';

-- Mẹ là đơn vị bác sĩ kê hằng ngày: phải đang bán (nên có giá — `ban_phai_co_gia`).
ALTER TABLE public.thuoc_quy_doi DROP CONSTRAINT IF EXISTS thuoc_quy_doi_me_phai_dang_ban;
ALTER TABLE public.thuoc_quy_doi ADD CONSTRAINT thuoc_quy_doi_me_phai_dang_ban
    CHECK (NOT mac_dinh_ke OR dang_ban);

-- Một thuốc tối đa MỘT đơn vị mẹ — ép ở đây (hai người cùng bật hai đơn vị: người
-- sau bị từ chối), không ở Python.
CREATE UNIQUE INDEX IF NOT EXISTS thuoc_quy_doi_mot_don_vi_me
    ON public.thuoc_quy_doi (clinic_id, drug_catalog_id) WHERE mac_dinh_ke;

-- Hệ số đổi `p_don_vi` về đơn vị gốc. Thân giống bản 20261101400000, chỉ khác nhánh
-- chữ RỖNG: trước trả NULL; nay trả hệ số của đơn vị mẹ nếu thuốc có cờ, không có cờ
-- thì vẫn NULL (người gọi `coalesce(…, 1)` = đơn vị gốc, như cũ).
CREATE OR REPLACE FUNCTION public.he_so_don_vi(p_clinic uuid, p_thuoc uuid, p_don_vi text)
RETURNS numeric
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    c text := public.chuan_don_vi(p_don_vi);
    kd text := public.bo_dau_don_vi(p_don_vi);
    goc text;
    n integer;
    hs numeric;
BEGIN
    IF c = '' THEN
        SELECT q.he_so INTO hs FROM public.thuoc_quy_doi q
         WHERE q.clinic_id = p_clinic AND q.drug_catalog_id = p_thuoc AND q.mac_dinh_ke;
        RETURN hs;
    END IF;
    SELECT public.chuan_don_vi(d.don_vi_ban) INTO goc
      FROM public.drug_catalog d
     WHERE d.id = p_thuoc AND d.clinic_id = p_clinic;
    IF c = goc THEN
        RETURN 1;
    END IF;
    SELECT q.he_so INTO hs FROM public.thuoc_quy_doi q
     WHERE q.clinic_id = p_clinic AND q.drug_catalog_id = p_thuoc AND q.don_vi = c;
    IF FOUND THEN
        RETURN hs;
    END IF;
    FOR buoc IN 1..3 LOOP
        SELECT count(*), max(k.he_so) INTO n, hs
          FROM (SELECT goc AS don_vi, 1::numeric AS he_so WHERE coalesce(goc, '') <> ''
                UNION ALL
                SELECT q.don_vi, q.he_so FROM public.thuoc_quy_doi q
                 WHERE q.clinic_id = p_clinic AND q.drug_catalog_id = p_thuoc) k
         WHERE CASE buoc
                   WHEN 1 THEN public.bo_dau_don_vi(k.don_vi) = kd
                   WHEN 2 THEN public.bo_dau_don_vi(k.don_vi) = split_part(kd, ' ', 1)
                   ELSE length(kd) <= 2 AND public.bo_dau_don_vi(k.don_vi) LIKE kd || '%'
               END;
        IF n = 1 THEN
            RETURN hs;
        ELSIF n > 1 THEN
            RETURN NULL;
        END IF;
    END LOOP;
    RETURN NULL;
END $$;

NOTIFY pgrst, 'reload schema';
