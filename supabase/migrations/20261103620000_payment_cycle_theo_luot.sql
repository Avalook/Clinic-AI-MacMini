-- Chỉ mục (clinic_id, visit_id) cho payment_cycle.
--
-- Bảng chỉ có hai chỉ mục MỘT PHẦN theo lượt (thuốc đã thu / dịch vụ chờ xác
-- minh), nên câu "các lần thu dịch vụ của lượt X" không có đường vào: bảng quầy
-- thu (`cashier_board_service._CU_CO_THE_NO_KHAM`, vế max(created_at)) quét tuần
-- tự cả bảng cho từng lượt cũ — prod 03/11: 882 lượt × 0,29 ms = 257 ms trong
-- 444 ms của câu bảng (tb 545 ms, max 6,5 s cộng dồn). Bảng ~1.600 dòng, tạo
-- chỉ mục tức thì; không cần CONCURRENTLY.

CREATE INDEX IF NOT EXISTS idx_payment_cycle_luot
    ON public.payment_cycle (clinic_id, visit_id);
