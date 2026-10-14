-- Chỉ điền ô chưa nạp; chạy lại không đè phân loại người dùng đã sửa.
UPDATE public.service_price SET kinh_doanh_vat_tu=(coalesce(unit_price,0)>0)
WHERE "group"='vat_tu' AND kinh_doanh_vat_tu IS NULL;
ALTER TABLE public.service_price ALTER COLUMN kinh_doanh_vat_tu SET DEFAULT false;
