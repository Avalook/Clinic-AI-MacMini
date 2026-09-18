-- Áp LẠI luật "chỉ năm dịch vụ khám" (20260807000007) — 17/09/2026.
--
-- VÌ SAO PHẢI ÁP LẠI: trên VPS mới (16/09) database được dựng bằng migration
-- rồi MỚI nạp supabase/seed.sql. Seed là bản dump từ tháng 6, chứa đủ 14 dịch vụ
-- đều đang bật với tên cũ — nó ghi đè kết quả của 20260807000007 trong khi sổ
-- migration vẫn ghi "đã áp". Màn đặt lịch CSKH vì thế hiện FREE, Sản 2/3, Tiền
-- hôn nhân… (Tuyền bắt được 17/09). seed.sql đã được sửa cùng lúc để không tái
-- phát; migration này sửa dữ liệu đang chạy. Chạy lại bao nhiêu lần cũng vậy.

UPDATE public.service_type
   SET is_active = FALSE
 WHERE code NOT IN ('PHU_KHOA', 'SAN_1', 'NOI_TIET_TINH_DUC',
                    'NAM_KHOA', 'HIEM_MUON');

UPDATE public.service_type SET is_active = TRUE, name = 'Phụ khoa',
       form_code = 'PK'   WHERE code = 'PHU_KHOA';
UPDATE public.service_type SET is_active = TRUE, name = 'Sản khoa',
       form_code = 'SK'   WHERE code = 'SAN_1';
UPDATE public.service_type SET is_active = TRUE, name = 'Nội tiết',
       form_code = 'NT'   WHERE code = 'NOI_TIET_TINH_DUC';
UPDATE public.service_type SET is_active = TRUE, name = 'Nam khoa',
       form_code = 'NK'   WHERE code = 'NAM_KHOA';
UPDATE public.service_type SET is_active = TRUE, name = 'Hiếm muộn / Vô sinh',
       form_code = 'HMVS' WHERE code = 'HIEM_MUON';

-- Thu ngân tra tiền khám THEO TÊN dịch vụ (cashier_board_service: price_dv
-- theo norm_name(service_type.name)). Đổi tên dịch vụ mà không đổi tên dòng giá
-- thì nút Thu tiền bị khoá vì "thiếu giá". Đổi theo cặp.
UPDATE public.service_price SET name = 'Sản khoa', updated_at = now()
 WHERE service_code = 'KHAM_SAN_1';
UPDATE public.service_price SET name = 'Nội tiết', updated_at = now()
 WHERE service_code = 'KHAM_NOI_TIET_TINH_DUC';
UPDATE public.service_price SET name = 'Hiếm muộn / Vô sinh', updated_at = now()
 WHERE service_code = 'KHAM_HIEM_MUON';

-- Giá khám của các dịch vụ đã ẩn: tắt theo (ẩn chứ không xoá).
UPDATE public.service_price SET active = FALSE, updated_at = now()
 WHERE service_code IN ('KHAM_SAN_2', 'KHAM_SAN_3', 'KHAM_NPDH',
                        'KHAM_HO_SO_SINH', 'KHAM_TIEN_HON_NHAN',
                        'KHAM_TU_VAN_CHUYEN_SAU', 'KHAM_THU_THUAT',
                        'KHAM_KHAM_TIEN_SAN');
