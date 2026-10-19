-- Số bác sĩ kê và số khách mua là hai đại lượng riêng. Quầy được bán vượt kê,
-- nhưng chỉ giao trong số đã mua. Giữ nguyên số kê để đối chiếu/cảnh báo.
BEGIN;
ALTER TABLE public.prescription DROP CONSTRAINT IF EXISTS prescription_purchased_qty_check;
ALTER TABLE public.prescription ADD CONSTRAINT prescription_purchased_qty_check
    CHECK (purchased_qty IS NULL OR (quantity_num IS NOT NULL AND purchased_qty >= 0));
ALTER TABLE public.prescription DROP CONSTRAINT IF EXISTS prescription_khong_cap_qua_ke;
ALTER TABLE public.prescription DROP CONSTRAINT IF EXISTS prescription_khong_cap_qua_mua;
ALTER TABLE public.prescription ADD CONSTRAINT prescription_khong_cap_qua_mua
    CHECK (coalesce(purchased_qty, quantity_num) IS NULL
           OR dispensed_qty <= coalesce(purchased_qty, quantity_num));
-- Trạng thái đủ/chưa đủ phải so với số mua; đơn cũ chưa có số mua dùng số kê.
ALTER TABLE public.prescription DROP COLUMN dispense_status;
ALTER TABLE public.prescription ADD COLUMN dispense_status text GENERATED ALWAYS AS (
    CASE WHEN dispensed_qty = 0 AND refusal_reason IS NOT NULL THEN 'TU_CHOI'
         WHEN dispensed_qty = 0 THEN 'CHUA_CAP'
         WHEN coalesce(purchased_qty, quantity_num) IS NOT NULL
              AND dispensed_qty >= coalesce(purchased_qty, quantity_num) THEN 'CAP_DU'
         ELSE 'CAP_MOT_PHAN' END
) STORED;
COMMENT ON COLUMN public.prescription.dispense_status IS
    'Trạng thái giao theo số khách mua; đơn cũ chưa ghi số mua dùng số kê.';
COMMIT;
