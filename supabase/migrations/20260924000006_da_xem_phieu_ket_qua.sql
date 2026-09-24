-- "Đã xem" cho kết quả dạng PHIẾU (điền ở phòng) — nợ nhóm 3 (Tuyền chốt 24/09/2026:
-- duyệt không bắt buộc; bác sĩ MỞ kết quả thì hệ thống TỰ ghi "đã xem lúc…").
-- Tệp kết quả đã có `tep_ket_qua.da_xem_*` (20260924000004); phiếu thì ghi trên
-- chính chỉ định. Chạy lại được.

ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS da_xem_ket_qua_luc timestamptz,
    ADD COLUMN IF NOT EXISTS da_xem_ket_qua_boi uuid REFERENCES public.staff (id);

COMMENT ON COLUMN public.service_order.da_xem_ket_qua_luc IS
'Lần ĐẦU bác sĩ / thư ký y khoa / BS siêu âm mở PHIẾU kết quả đã hoàn tất của chỉ định này (tự ghi). Duyệt cũng tính là đã xem.';
