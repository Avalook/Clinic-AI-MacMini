-- Quầy thu thuốc bỏ tick (khách không lấy) được cả dòng bác sĩ kê THIẾU số lượng
-- (Tuyền 16/11). Trước: số mua chỉ ghi được khi đã có số kê → quầy phải gõ số giả mới
-- bỏ tick được, nút Tạo bill bị khoá vì dòng "chưa có số lượng".
-- Chỉ nới: thêm trường hợp số mua = 0 khi chưa có số kê. Không đụng dữ liệu.
-- `prescription_khong_cap_qua_mua` vẫn đúng: coalesce(0, NULL) = 0 → không giao được.
-- Hoàn tác: chạy lại định nghĩa ở 20261018200000_thuoc_mua_vuot_ke_chi_nhac.sql (chỉ
-- được khi không còn dòng purchased_qty = 0 AND quantity_num IS NULL).
BEGIN;
ALTER TABLE public.prescription DROP CONSTRAINT IF EXISTS prescription_purchased_qty_check;
ALTER TABLE public.prescription ADD CONSTRAINT prescription_purchased_qty_check
    CHECK (
        purchased_qty IS NULL
        OR purchased_qty = 0
        OR (quantity_num IS NOT NULL AND purchased_qty >= 0)
    );
COMMIT;
