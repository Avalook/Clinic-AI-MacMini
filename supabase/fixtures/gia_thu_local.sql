-- GIÁ THỬ — CHỈ LOCAL/DEMO (batch pilot 18/09/2026). KHÔNG PHẢI GIÁ DR4WOMEN.
--
-- Vì sao: bảng service_price local có 39 dòng nhưng unit_price đều rỗng, và
-- không có dòng giá nào cho 5 dịch vụ khám → màn Thu ngân báo "chưa có giá —
-- chưa thu được" cho mọi khách, không kiểm được bước thu tiền đầu-cuối.
-- Giá thật do phòng khám nhập ở Cấu hình; fixture này chỉ lấp chỗ rỗng
-- (không đè giá đã có) và dùng số tròn 100.000đ để không ai nhầm là giá thật.
-- Không bao giờ nạp vào prod: scripts/dev-up.sh chỉ chạy trên máy local.

DO $$
BEGIN
    UPDATE public.service_price
       SET unit_price = 100000, updated_at = now()
     WHERE clinic_id = 'a0000000-0000-4000-8000-000000000001'
       AND "group" = 'dich_vu'
       AND unit_price IS NULL;

    INSERT INTO public.service_price (clinic_id, "group", service_code, name, unit_price)
    VALUES
      ('a0000000-0000-4000-8000-000000000001', 'dich_vu', 'DEMO_KHAM_NAM_KHOA', 'Nam khoa', 100000),
      ('a0000000-0000-4000-8000-000000000001', 'dich_vu', 'DEMO_KHAM_PHU_KHOA', 'Phụ khoa', 100000),
      ('a0000000-0000-4000-8000-000000000001', 'dich_vu', 'DEMO_KHAM_SAN_KHOA', 'Sản khoa', 100000),
      ('a0000000-0000-4000-8000-000000000001', 'dich_vu', 'DEMO_KHAM_NOI_TIET', 'Nội tiết', 100000),
      ('a0000000-0000-4000-8000-000000000001', 'dich_vu', 'DEMO_KHAM_HIEM_MUON', 'Hiếm muộn / Vô sinh', 100000)
    ON CONFLICT (clinic_id, "group", service_code) DO NOTHING;
END $$;
