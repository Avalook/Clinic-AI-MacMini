-- Tắt dây "khách quen vào thẳng bác sĩ chính" (H1) — Tuyền 25/09/2026:
-- "cứ qua bác sĩ tư vấn như bình thường, nào điều dưỡng đo sinh hiệu ấn bỏ qua
-- bác sĩ tư vấn thì vào bác sĩ chính luôn".
--
-- Sáng 25/09 Tuyền thử một khách đo sinh hiệu xong mà không thấy ở hàng tư vấn:
-- khách ấy từng được chính bác sĩ ấy khám → dây này (mặc định BẬT) xếp thẳng
-- bác sĩ chính. Code đổi mặc định sang TẮT (`day_noi.py`); ở đây tắt nốt phòng
-- khám nào đã LƯU giá trị bật. Cũ thì OFF, không xoá — quản lý bật lại được ở
-- Cài đặt → Dây nối. Chạy lại được.

UPDATE public.day_nghiep_vu
   SET gia_tri = 'false'::jsonb, sua_luc = now()
 WHERE ma = 'h1_khach_quen_vao_thang_bs'
   AND gia_tri IS DISTINCT FROM 'false'::jsonb;
