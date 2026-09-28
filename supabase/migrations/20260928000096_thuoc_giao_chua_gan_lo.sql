-- GIAO THUỐC KHÔNG CẦN LÔ — gán lô sau (Tuyền 28/09/2026).
--
-- "Chưa cần quan tâm lô nào, số lượng điền tay hay giá điền tay áp dụng bán
-- luôn, lô nhập và gán sau cũng được." Trước bản này quầy không giao được thuốc
-- khi kho chưa có lô còn hạn cùng đơn vị: `inventory_txn.drug_batch_id` NOT
-- NULL và CHECK tồn lô ≥ 0 buộc mọi lần giao trỏ vào một lô thật.
--
-- Cách giữ nguyên hai bất biến ấy: lần giao không lô KHÔNG ghi `inventory_txn`.
-- Nó tăng `prescription.dispensed_qty` (như mọi lần giao — người + giờ giao đã
-- có ràng buộc `prescription_cap_thi_co_dau_vet`) và ghi MỘT DÒNG vào sổ này.
-- Khi kho đã nhập lô, người có quyền nhà thuốc GÁN dòng ấy vào một lô → lúc đó
-- mới ghi DISPENSE vào `inventory_txn` (tồn lô giảm, CHECK ≥ 0 và hạn dùng được
-- kiểm ở đúng lúc ấy).
--
-- Hệ quả đã chấp nhận: cho tới khi gán, tồn vật lý của kho báo CAO hơn thực tế
-- đúng bằng tổng các dòng chưa gán — màn Kho thuốc hiện tổng ấy.

CREATE TABLE IF NOT EXISTS public.thuoc_giao_chua_gan_lo (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    prescription_id  uuid NOT NULL REFERENCES public.prescription(id)
                         ON DELETE RESTRICT,
    drug_catalog_id  uuid REFERENCES public.drug_catalog(id) ON DELETE RESTRICT,
    so_luong         numeric NOT NULL CHECK (so_luong > 0),
    giao_boi         uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    giao_luc         timestamptz NOT NULL DEFAULT now(),
    -- Gán lô: ba cột đi cùng nhau — có lô thì có lần ghi sổ kho, người, giờ.
    drug_batch_id    uuid REFERENCES public.drug_batch(id) ON DELETE RESTRICT,
    inventory_txn_id uuid,
    gan_boi          uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    gan_luc          timestamptz,
    CONSTRAINT thuoc_giao_chua_gan_lo_gan_du_bo CHECK (
        (drug_batch_id IS NULL AND inventory_txn_id IS NULL AND gan_luc IS NULL)
        OR (drug_batch_id IS NOT NULL AND inventory_txn_id IS NOT NULL
            AND gan_luc IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS thuoc_giao_chua_gan_lo_con_cho
    ON public.thuoc_giao_chua_gan_lo (clinic_id, giao_luc)
    WHERE drug_batch_id IS NULL;
CREATE INDEX IF NOT EXISTS thuoc_giao_chua_gan_lo_theo_don
    ON public.thuoc_giao_chua_gan_lo (prescription_id);

COMMENT ON TABLE public.thuoc_giao_chua_gan_lo IS
'Thuốc đã giao khách mà chưa gán lô kho (28/09/2026). Gán lô = ghi DISPENSE vào inventory_txn lúc ấy.';

ALTER TABLE public.thuoc_giao_chua_gan_lo ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS thuoc_giao_chua_gan_lo_select_own_clinic
    ON public.thuoc_giao_chua_gan_lo;
CREATE POLICY thuoc_giao_chua_gan_lo_select_own_clinic
    ON public.thuoc_giao_chua_gan_lo
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.thuoc_giao_chua_gan_lo TO service_role;
