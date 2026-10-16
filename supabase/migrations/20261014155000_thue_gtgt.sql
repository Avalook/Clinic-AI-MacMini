-- THUẾ GTGT CHO KẾ TOÁN (G5b · Tuyền 14/10/2026, Q16 "open tối đa", K1).
--
-- Giá trong bảng giá ĐÃ GỒM thuế; khi xuất hoá đơn kế toán tách ngược. Thuế suất
-- đặt theo NHÓM (dịch vụ / thuốc / vật tư) hoặc TỪNG mặt hàng, % tự nhập, hoặc
-- KCT (không chịu thuế) / KKKNT (không kê khai nộp thuế); sửa tay từng dòng lúc
-- xuất (không lưu ở đây — gửi kèm lệnh xuất). Ưu tiên: dòng > mặt hàng > nhóm.
--
-- THUẾ KHÔNG CHẠM VẬN HÀNH: quầy thu, hoá đơn, báo cáo ngày không đọc các cột
-- này. Tên cột có tiền tố `thue_` để không trùng cột vật tư G8a (service_price).
-- Chạy lại được.

-- Chuỗi hợp lệ: "KCT" | "KKKNT" | số 0–100 có tối đa 2 chữ số thập phân.
CREATE OR REPLACE FUNCTION public.thue_suat_hop_le(ma text)
RETURNS boolean
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE
        WHEN ma IS NULL THEN true
        WHEN ma IN ('KCT', 'KKKNT') THEN true
        WHEN ma ~ '^[0-9]{1,3}(\.[0-9]{1,2})?$' THEN ma::numeric <= 100
        ELSE false
    END
$$;

ALTER TABLE public.service_price
    ADD COLUMN IF NOT EXISTS thue_suat_ma text;
ALTER TABLE public.service_price
    DROP CONSTRAINT IF EXISTS service_price_thue_suat_hop_le;
ALTER TABLE public.service_price
    ADD CONSTRAINT service_price_thue_suat_hop_le
    CHECK (public.thue_suat_hop_le(thue_suat_ma));
COMMENT ON COLUMN public.service_price.thue_suat_ma IS
'Thuế GTGT của mặt hàng (KCT | KKKNT | % ). NULL = theo nhóm. Chỉ kế toán đọc/ghi; vận hành không đụng (14/10/2026).';

ALTER TABLE public.drug_catalog
    ADD COLUMN IF NOT EXISTS thue_suat_ma text;
ALTER TABLE public.drug_catalog
    DROP CONSTRAINT IF EXISTS drug_catalog_thue_suat_hop_le;
ALTER TABLE public.drug_catalog
    ADD CONSTRAINT drug_catalog_thue_suat_hop_le
    CHECK (public.thue_suat_hop_le(thue_suat_ma));
COMMENT ON COLUMN public.drug_catalog.thue_suat_ma IS
'Thuế GTGT của thuốc (KCT | KKKNT | % ). NULL = theo nhóm Thuốc (14/10/2026).';

-- Thuế suất theo NHÓM mặt hàng của từng phòng khám.
CREATE TABLE IF NOT EXISTS public.thue_suat_nhom (
    clinic_id    uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    nhom         text NOT NULL CHECK (nhom IN ('DICH_VU', 'THUOC', 'VAT_TU')),
    thue_suat_ma text NOT NULL CHECK (public.thue_suat_hop_le(thue_suat_ma)),
    sua_boi      uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    sua_luc      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, nhom)
);
COMMENT ON TABLE public.thue_suat_nhom IS
'Thuế GTGT theo nhóm Dịch vụ / Thuốc / Vật tư (kế toán đặt, 14/10/2026). Không có dòng = chưa đặt.';

ALTER TABLE public.thue_suat_nhom ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS thue_suat_nhom_select_own_clinic ON public.thue_suat_nhom;
CREATE POLICY thue_suat_nhom_select_own_clinic ON public.thue_suat_nhom
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON public.thue_suat_nhom TO service_role;

-- Quyền ĐẶT thuế (khối Kế toán — Quản lý cấp cho người cụ thể).
INSERT INTO public.capability
    (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('accounting.tax.manage', 'Đặt thuế suất GTGT (nhóm, mặt hàng)',
     'ke_toan', 'accounting', 'financial', false)
ON CONFLICT (ma) DO NOTHING;

SELECT public.cap_quyen_cho_moi_thanh_vien();
