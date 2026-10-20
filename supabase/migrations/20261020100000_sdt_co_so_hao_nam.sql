-- SĐT in trên phiếu của cả hai cơ sở (Hào Nam, Kim Ngưu) = 0899 973 555
-- (Tuyền 20/10/2026). Không có màn sửa SĐT cơ sở; mọi phiếu in (phiếu khám,
-- phiếu kết quả, phiếu thu) đọc `clinic_location.phone`, nên sửa cột này là đủ.
-- Giữ kiểu "4 3 3" của số cũ. Chỉ chạm dòng đang lệch — áp lại là no-op.
UPDATE public.clinic_location
   SET phone = '0899 973 555'
 WHERE code IN ('HN', 'KN')
   AND phone IS DISTINCT FROM '0899 973 555';
