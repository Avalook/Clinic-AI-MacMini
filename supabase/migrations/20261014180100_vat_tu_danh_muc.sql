-- Chỉ metadata vật tư; kinh doanh là phân loại, không đổi luật bán (Tuyền chốt).
ALTER TABLE public.service_price ADD COLUMN IF NOT EXISTS loai_vat_tu text;
ALTER TABLE public.service_price ADD COLUMN IF NOT EXISTS gia_nhap_vat_tu numeric(12,0);
ALTER TABLE public.service_price ADD COLUMN IF NOT EXISTS ma_vach_vat_tu text;
ALTER TABLE public.service_price ADD COLUMN IF NOT EXISTS kinh_doanh_vat_tu boolean;
ALTER TABLE public.service_price ADD COLUMN IF NOT EXISTS can_duyet_nhap_vat_tu boolean NOT NULL DEFAULT false;
ALTER TABLE public.service_price DROP CONSTRAINT IF EXISTS vat_tu_loai_hop_le;
ALTER TABLE public.service_price ADD CONSTRAINT vat_tu_loai_hop_le CHECK (loai_vat_tu IS NULL OR loai_vat_tu IN ('VPP','VTYT'));
ALTER TABLE public.service_price DROP CONSTRAINT IF EXISTS vat_tu_gia_nhap_hop_le;
ALTER TABLE public.service_price ADD CONSTRAINT vat_tu_gia_nhap_hop_le CHECK (gia_nhap_vat_tu IS NULL OR (gia_nhap_vat_tu>=0 AND gia_nhap_vat_tu<>'NaN'::numeric));
ALTER TABLE public.service_price DROP CONSTRAINT IF EXISTS vat_tu_ma_vach_hop_le;
ALTER TABLE public.service_price ADD CONSTRAINT vat_tu_ma_vach_hop_le CHECK (ma_vach_vat_tu IS NULL OR length(ma_vach_vat_tu) BETWEEN 1 AND 120);
COMMENT ON COLUMN public.service_price.kinh_doanh_vat_tu IS 'Phân loại kinh doanh, không thêm điều kiện chặn bán. Luật bán giữ active/giá và duyệt cũ.';
NOTIFY pgrst, 'reload schema';
