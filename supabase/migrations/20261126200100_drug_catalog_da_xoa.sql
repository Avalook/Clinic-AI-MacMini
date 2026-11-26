-- PR B (26/11/2026, Tuyền: "lưu vào đâu đó trước đã rồi xoá"): nút Xoá ở Danh mục
-- thuốc. Chỉ thuốc CHƯA TỪNG được dùng (không đơn, lô, phiếu kho, kiểm kê, hoá đơn…)
-- mới xoá được. Trước khi xoá thật, chụp NGUYÊN dòng `drug_catalog` + các dòng định
-- nghĩa đi kèm (`thuoc_quy_doi`, `drug_ma_vach`) vào bảng này, kèm ai xoá, lúc nào,
-- vì sao. KHÔI PHỤC = dựng lại đúng các dòng ấy (cùng id) từ bản chụp — hoàn tác.
--
-- KHÔNG có khoá ngoại tới `drug_catalog`: bản chụp sống sau khi thuốc đã xoá, và
-- nút Xoá đếm mọi khoá ngoại tới thuốc như "đã được dùng".
-- Chạy lại nhiều lần được: IF NOT EXISTS / DROP … IF EXISTS.

CREATE TABLE IF NOT EXISTS public.drug_catalog_da_xoa (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    drug_catalog_id  uuid NOT NULL,
    ten              text NOT NULL,
    ban_chup         jsonb NOT NULL,
    quy_doi          jsonb NOT NULL DEFAULT '[]'::jsonb,
    ma_vach          jsonb NOT NULL DEFAULT '[]'::jsonb,
    ly_do            text NOT NULL,
    xoa_boi          uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    xoa_luc          timestamptz NOT NULL DEFAULT now(),
    khoi_phuc_boi    uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    khoi_phuc_luc    timestamptz,
    CONSTRAINT drug_catalog_da_xoa_ly_do CHECK (length(btrim(ly_do)) BETWEEN 1 AND 500),
    CONSTRAINT drug_catalog_da_xoa_khoi_phuc_day_du
        CHECK ((khoi_phuc_luc IS NULL) = (khoi_phuc_boi IS NULL))
);

-- Một thuốc chỉ có MỘT bản chụp chưa khôi phục (xoá → khôi phục → xoá lại = bản mới).
CREATE UNIQUE INDEX IF NOT EXISTS uq_drug_catalog_da_xoa_chua_khoi_phuc
    ON public.drug_catalog_da_xoa (drug_catalog_id)
    WHERE khoi_phuc_luc IS NULL;

CREATE INDEX IF NOT EXISTS drug_catalog_da_xoa_theo_luc
    ON public.drug_catalog_da_xoa (clinic_id, xoa_luc DESC);

ALTER TABLE public.drug_catalog_da_xoa ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS drug_catalog_da_xoa_select_own_clinic ON public.drug_catalog_da_xoa;
CREATE POLICY drug_catalog_da_xoa_select_own_clinic
    ON public.drug_catalog_da_xoa FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT, INSERT, UPDATE ON public.drug_catalog_da_xoa TO service_role;
GRANT SELECT ON public.drug_catalog_da_xoa TO authenticated;
