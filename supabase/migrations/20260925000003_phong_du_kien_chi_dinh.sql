-- Phòng DỰ KIẾN của chỉ định — chọn ở quầy lúc chốt dịch vụ (Tuyền 24/09/2026).
--
-- Tuyền: "ở chỗ thu ngân dịch vụ thì phải cho chọn phòng để chỉ định xem khách
-- đó khám ở đâu rồi mới chốt và thanh toán". Xếp phòng CHÍNH THỨC vẫn chỉ xảy
-- ra sau khi thu tiền (FinanceGate chặn AssignServiceRoom khi chưa trả) — đây
-- chỉ là ý định: dây H4 thu xong đọc cột này, xếp đúng phòng đã chọn nếu phòng
-- còn nhận khách, không thì tự chọn phòng vắng nhất như cũ.
-- Chạy lại được.

ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS phong_du_kien_id uuid
        REFERENCES public.clinic_room (id) ON DELETE SET NULL;

COMMENT ON COLUMN public.service_order.phong_du_kien_id IS
    'Phòng khách chọn ở quầy trước khi thu tiền; dây H4 dùng khi xếp phòng.';
