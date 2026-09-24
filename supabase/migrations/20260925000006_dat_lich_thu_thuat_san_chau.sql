-- Đặt lịch THỦ THUẬT + SÀN CHẬU CHUYÊN SÂU (Tuyền 24/09/2026: "sao đặt lịch lại
-- chỉ có 5 dịch vụ, mình đã thêm thủ thuật và Sàn chậu chuyên sâu rồi").
--
-- 22/09 bảy PHIẾU khám đã có (NT/HMVS/PK/SK/NK + THU_THUAT + SAN_CHAU — migration
-- 20260924000008), dây H2 "đi thẳng phòng" cũng đã chờ sẵn hai mã này
-- (20260924000002). Chỉ thiếu LOẠI KHÁM để đặt lịch: Thủ thuật còn tắt từ đợt
-- "chỉ năm dịch vụ" (20260917000006), Sàn chậu chưa từng có dòng.
--
-- Tiền khám tra THEO TÊN loại khám trong bảng giá (bill_service._kham) → đổi tên
-- loại khám phải đổi tên dòng KHAM_* theo cặp. Giá Sàn chậu theo đúng tiền lệ
-- các dòng tiền khám khác: GIÁ GIẢ ĐỊNH, phòng khám sửa ở Bảng giá. Lịch đi
-- thẳng phòng thật (có chỉ định mang sang) KHÔNG tính tiền khám — dòng giá chỉ
-- dùng khi khách mới rơi về bác sĩ chính.
--
-- Chạy lại được.

-- Trigger `service_type_form_code_exists` đòi mã phiếu có trong danh mục phiếu
-- của phòng khám — 22/09 hai phiếu mới chỉ vào bảng định nghĩa v5, chưa vào đây.
INSERT INTO public.clinical_form_catalogue (clinic_id, form_code, title, is_active)
SELECT c.id, v.ma, v.ten, true
  FROM public.clinic c
 CROSS JOIN (VALUES ('THU_THUAT', 'Phiếu thủ thuật'),
                    ('SAN_CHAU', 'Phiếu sàn chậu chuyên sâu')) AS v(ma, ten)
 WHERE NOT EXISTS (SELECT 1 FROM public.clinical_form_catalogue f
                    WHERE f.clinic_id = c.id AND f.form_code = v.ma);

UPDATE public.clinical_form_catalogue
   SET is_active = true, updated_at = now()
 WHERE form_code IN ('THU_THUAT', 'SAN_CHAU') AND NOT is_active;

UPDATE public.service_type
   SET name = 'Thủ thuật', is_active = true, form_code = 'THU_THUAT',
       di_thang_phong = true, qua_tu_van = false
 WHERE code = 'THU_THUAT'
   AND (name, is_active, form_code, di_thang_phong, qua_tu_van)
       IS DISTINCT FROM ('Thủ thuật', true, 'THU_THUAT', true, false);

INSERT INTO public.service_type
    (clinic_id, code, name, default_duration_minutes, is_active, form_code,
     qua_tu_van, di_thang_phong)
SELECT c.id, 'SAN_CHAU', 'Sàn chậu chuyên sâu', 30, true, 'SAN_CHAU', false, true
  FROM public.clinic c
ON CONFLICT (clinic_id, code) DO NOTHING;

UPDATE public.service_price
   SET name = 'Thủ thuật', active = true, updated_at = now()
 WHERE "group" = 'dich_vu' AND service_code = 'KHAM_THU_THUAT'
   AND (name, active) IS DISTINCT FROM ('Thủ thuật', true);

-- Dòng giá tiền khám thiếu thì thêm (prod có KHAM_THU_THUAT từ đợt nạp giá tay
-- 17/09; database dựng mới thì không có dòng nào).
INSERT INTO public.service_price
    (clinic_id, service_code, name, "group", unit_price, active, category,
     billing_owner)
SELECT c.id, v.ma, v.ten, 'dich_vu', 300000, true,
       'Tiền khám · GIÁ GIẢ ĐỊNH 24/09/2026 — phòng khám cần sửa', 'CLINIC'
  FROM public.clinic c
 CROSS JOIN (VALUES ('KHAM_THU_THUAT', 'Thủ thuật'),
                    ('KHAM_SAN_CHAU', 'Sàn chậu chuyên sâu')) AS v(ma, ten)
ON CONFLICT (clinic_id, "group", service_code) DO NOTHING;
