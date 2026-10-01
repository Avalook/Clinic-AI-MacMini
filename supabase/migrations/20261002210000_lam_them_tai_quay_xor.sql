-- Chỉ định thuộc đúng MỘT nguồn: phiên bác sĩ HOẶC thao tác làm thêm tại quầy.
-- Migration chạy lại được: thay ràng buộc cũ (OR) bằng XOR rồi kiểm dữ liệu có sẵn.
ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_phien_hoac_quay;

ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_phien_hoac_quay
    CHECK (
        (consultation_id IS NOT NULL AND nguon_lam_them IS NULL)
        OR
        (consultation_id IS NULL AND nguon_lam_them IS NOT NULL)
    ) NOT VALID;

ALTER TABLE public.service_order
    VALIDATE CONSTRAINT service_order_phien_hoac_quay;
