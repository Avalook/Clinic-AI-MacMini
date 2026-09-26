-- Dịch vụ BẮT BUỘC (Tuyền 25/09/2026 — P2): lúc chỉ định, bác sĩ tick "Bắt buộc"
-- cạnh từng dịch vụ (mặc định KHÔNG). Ở quầy thanh toán dịch vụ, dịch vụ bắt buộc
-- KHÔNG bỏ chọn được — muốn bỏ phải quay lại người chỉ định bỏ tick (hoặc huỷ).
-- Không buộc thu tiền ngay, không chặn khách về: chỉ chặn việc BỎ dịch vụ.
--
-- Chặn ở máy chủ (service_selection_service, cùng giao dịch, dòng đã khoá FOR
-- UPDATE) + ràng buộc bên dưới: bắt buộc thì không thể ở trạng thái khách-không-làm.
-- Chạy lại được.

ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS bat_buoc boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.service_order.bat_buoc IS
'Bác sĩ đánh dấu dịch vụ bắt buộc — quầy thu không bỏ chọn được (P2, 25/09/2026).';
