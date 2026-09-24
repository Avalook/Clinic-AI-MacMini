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

INSERT INTO public.service_type
    (clinic_id, code, name, default_duration_minutes, is_active, form_code,
     qua_tu_van, di_thang_phong)
SELECT c.id, 'SAN_CHAU', 'Sàn chậu chuyên sâu', 30, true, 'SAN_CHAU', false, true
  FROM public.clinic c
ON CONFLICT (clinic_id, code) DO NOTHING;

-- Luôn đưa CẢ HAI về đúng trạng thái — kể cả khi chạy lại sau 20260807000007 /
-- 20260917000006 (hai migration "chỉ năm dịch vụ" tắt mọi mã ngoài năm mã lõi).
UPDATE public.service_type st
   SET name = v.ten, is_active = true, form_code = v.ma,
       di_thang_phong = true, qua_tu_van = false
  FROM (VALUES ('THU_THUAT', 'Thủ thuật'),
               ('SAN_CHAU', 'Sàn chậu chuyên sâu')) AS v(ma, ten)
 WHERE st.code = v.ma
   AND (st.name, st.is_active, st.form_code, st.di_thang_phong, st.qua_tu_van)
       IS DISTINCT FROM (v.ten, true, v.ma, true, false);

UPDATE public.service_price
   SET name = 'Thủ thuật', active = true, updated_at = now()
 WHERE "group" = 'dich_vu' AND service_code = 'KHAM_THU_THUAT'
   AND (name, active) IS DISTINCT FROM ('Thủ thuật', true);

-- Dòng giá tiền khám thiếu thì thêm — CHỈ cho phòng khám đang tính tiền khám
-- bằng các dòng KHAM_* (prod: nạp tay 17/09). Database dựng mới không có dòng
-- KHAM_* nào thì không thêm: chốt kiểm của 20260916000004 (chạy lại trên CI)
-- đếm mọi dịch vụ active thiếu bước và chỉ chừa khám phụ khoa.
INSERT INTO public.service_price
    (clinic_id, service_code, name, "group", unit_price, active, category,
     billing_owner)
SELECT c.id, v.ma, v.ten, 'dich_vu', 300000, true,
       'Tiền khám · GIÁ GIẢ ĐỊNH 24/09/2026 — phòng khám cần sửa', 'CLINIC'
  FROM public.clinic c
 CROSS JOIN (VALUES ('KHAM_THU_THUAT', 'Thủ thuật'),
                    ('KHAM_SAN_CHAU', 'Sàn chậu chuyên sâu')) AS v(ma, ten)
 WHERE EXISTS (SELECT 1 FROM public.service_price p
                WHERE p.clinic_id = c.id AND p."group" = 'dich_vu'
                  AND p.service_code LIKE 'KHAM\_%'
                  AND p.service_code NOT IN ('KHAM_THU_THUAT', 'KHAM_SAN_CHAU'))
ON CONFLICT (clinic_id, "group", service_code) DO NOTHING;
