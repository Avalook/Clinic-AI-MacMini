-- Liệu trình — chính sách tiền KHI DỪNG (Tuyền chốt 30/10/2026).
--
-- Quản lý chọn ở /settings/day-noi (dây `lieu_trinh_dung_tinh_gia_le`):
--   GIA_GOI (mặc định) — buổi đã làm + buổi đang kê tính đơn giá gói, hoàn phần
--                        trả trước chưa dùng theo đơn giá gói;
--   GIA_LE             — phá gói: mọi buổi đã dùng tính lại giá lẻ, hoàn = đã trả
--                        − tổng giá lẻ (âm → chỉ HIỆN số khách còn thiếu).
-- Đổi dây chỉ áp cho lần dừng SAU: lệnh dừng chụp chính sách lúc bấm vào đây.
-- Mở lại không xoá (hoàn tác "mở lại" = dừng lại ĐÚNG lần cũ, cùng chính sách).
-- Liệu trình dừng trước migration này: NULL = tính theo giá gói như cũ.
ALTER TABLE public.lieu_trinh
    ADD COLUMN IF NOT EXISTS chinh_sach_dung text
        CHECK (chinh_sach_dung IS NULL OR chinh_sach_dung IN ('GIA_GOI', 'GIA_LE'));
COMMENT ON COLUMN public.lieu_trinh.chinh_sach_dung IS
'Chính sách tiền của lần dừng gần nhất (chụp từ dây lieu_trinh_dung_tinh_gia_le lúc bấm Dừng). NULL = giá gói.';
