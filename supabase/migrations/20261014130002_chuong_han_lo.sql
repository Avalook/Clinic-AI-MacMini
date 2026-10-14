-- Chuông tự động hạn lô không gán người bấm giả. Chuông cũ vẫn bắt người gọi.
UPDATE public.clinic
   SET settings = coalesce(settings, '{}'::jsonb)
                  || '{"pharmacy_expiry_warning_days":60}'::jsonb
 WHERE NOT coalesce(settings, '{}'::jsonb) ? 'pharmacy_expiry_warning_days';
ALTER TABLE public.thong_bao ALTER COLUMN nguoi_goi_staff_id DROP NOT NULL;
ALTER TABLE public.thong_bao DROP CONSTRAINT IF EXISTS thong_bao_nguoi_goi_hoac_han_lo;
ALTER TABLE public.thong_bao ADD CONSTRAINT thong_bao_nguoi_goi_hoac_han_lo
    CHECK (nguoi_goi_staff_id IS NOT NULL OR nguon = 'lo_thuoc_han');
INSERT INTO public.day_nhan_thong_bao (clinic_id, su_kien, vai, bac_si_chinh, bat)
SELECT id, 'pharmacy.expiry_checked', ARRAY['PHARMACIST','MANAGEMENT'], false, true
FROM public.clinic ON CONFLICT (clinic_id, su_kien) DO NOTHING;
NOTIFY pgrst, 'reload schema';
