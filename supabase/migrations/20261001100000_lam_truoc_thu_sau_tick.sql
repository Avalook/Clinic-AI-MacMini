-- THU TRƯỚC KHI LÀM + tick "Làm trước – thu sau" theo LƯỢT (Tuyền 30/09/2026).
--
-- V10 cho MỌI lượt làm trước, thu sau. Tuyền đổi ý: mặc định phải thu trước
-- (dây nối `thu_truoc_khi_lam`, mặc định BẬT — không cần dòng dữ liệu, mặc định
-- nằm trong code `services/day_noi.py`); chỉ lượt được tick "Làm trước – thu
-- sau" mới xếp phòng / bắt đầu làm khi chưa thu.
--
-- NULL = không tick. Bật ghi người + giờ; bỏ tick đặt lại NULL (lịch sử ở sổ sự
-- kiện `visit.defer_payment_set` / `visit.defer_payment_cleared`).

ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS lam_truoc_thu_sau_luc timestamptz,
    ADD COLUMN IF NOT EXISTS lam_truoc_thu_sau_boi uuid REFERENCES public.staff (id);

-- Có người thì phải có giờ (giờ không người được: tài khoản hệ thống).
ALTER TABLE public.visit
    DROP CONSTRAINT IF EXISTS visit_lam_truoc_thu_sau_co_gio;
ALTER TABLE public.visit
    ADD CONSTRAINT visit_lam_truoc_thu_sau_co_gio
    CHECK (lam_truoc_thu_sau_boi IS NULL OR lam_truoc_thu_sau_luc IS NOT NULL);

COMMENT ON COLUMN public.visit.lam_truoc_thu_sau_luc IS
'Tick "Làm trước – thu sau" lúc nào (NULL = không tick). Dây thu_truoc_khi_lam BẬT: chỉ lượt có tick mới làm khi chưa thu.';
COMMENT ON COLUMN public.visit.lam_truoc_thu_sau_boi IS
'Ai tick "Làm trước – thu sau".';
