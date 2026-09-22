-- Service Lifecycle v1 — nháp chỉ định không mang trạng thái Selection
-- (review PR #178, 22/09/2026).
--
-- SELECTION §2: nháp là NULL — khách chỉ quyết trên chỉ định chính thức. Ghim ở
-- DB để không đường ghi nào (kể cả code cũ hay SQL tay) đặt được lựa chọn của
-- khách lên một nháp bác sĩ chưa duyệt.
--
-- Không backfill: chưa đường ghi nào đặt selection_status cho nháp, nên dòng
-- hiện có đều thoả. Nếu có dòng vi phạm, ADD CONSTRAINT dừng migration — đó là
-- dữ liệu cần người xem, không tự sửa.
--
-- Chạy lại được.

ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_draft_khong_co_selection;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_draft_khong_co_selection CHECK (
        exec_status <> 'draft' OR selection_status IS NULL);
