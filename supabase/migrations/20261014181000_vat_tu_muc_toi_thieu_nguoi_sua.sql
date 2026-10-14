-- Mức tối thiểu là dữ liệu Quản lý sửa trên màn: ghi ai/lúc sửa gần nhất.
ALTER TABLE public.vat_tu_ton ADD COLUMN IF NOT EXISTS muc_sua_boi uuid REFERENCES public.staff(id) ON DELETE RESTRICT;
ALTER TABLE public.vat_tu_ton ADD COLUMN IF NOT EXISTS muc_sua_luc timestamptz;
NOTIFY pgrst, 'reload schema';
