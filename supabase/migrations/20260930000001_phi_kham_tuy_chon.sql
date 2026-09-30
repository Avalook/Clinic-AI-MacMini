-- V2 (30/09/2026): dịch vụ khám con là tuỳ chọn. Khi chưa chọn, hoá đơn dùng
-- giá mặc định của loại khám; chưa cấu hình nghĩa là 0đ.
ALTER TABLE public.service_type
    ADD COLUMN IF NOT EXISTS gia_mac_dinh numeric NOT NULL DEFAULT 0;

-- Đồng Việt Nam được lưu theo số nguyên. Chuẩn hoá cả trường hợp migration
-- được chạy lại trên một database thử đã từng có cột ``numeric`` không scale.
ALTER TABLE public.service_type
    ALTER COLUMN gia_mac_dinh TYPE numeric
    USING gia_mac_dinh::numeric;

ALTER TABLE public.service_type
    DROP CONSTRAINT IF EXISTS service_type_gia_mac_dinh_khong_am;
ALTER TABLE public.service_type
    ADD CONSTRAINT service_type_gia_mac_dinh_khong_am
    CHECK (
        gia_mac_dinh BETWEEN 0 AND 1000000000
        AND gia_mac_dinh = trunc(gia_mac_dinh)
    );

COMMENT ON COLUMN public.service_type.gia_mac_dinh IS
'Phí khám dùng khi lượt chưa chọn dịch vụ khám con; mặc định 0đ.';
