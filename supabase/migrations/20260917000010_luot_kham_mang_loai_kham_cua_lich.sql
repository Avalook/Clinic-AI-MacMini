-- Lượt khám mở lúc check-in không mang loại khám của lịch hẹn → bàn khám báo
-- "Chưa gán dịch vụ" cho lịch đã đặt Nội tiết (bắt được khi thao tác thật
-- 17/09/2026). Code đã sửa ở BookingService._open_visit; đây điền lại cho các
-- lượt đã mở.
UPDATE public.visit v
   SET service_type_id = a.service_type_id, updated_at = now()
  FROM public.appointment a
 WHERE a.id = v.appointment_id
   AND a.clinic_id = v.clinic_id
   AND v.service_type_id IS NULL
   AND a.service_type_id IS NOT NULL
   AND v.status NOT IN ('FINALIZED', 'AMENDED');
