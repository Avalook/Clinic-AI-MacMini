-- CHỮA DỮ LIỆU: chỗ chờ còn mở của lượt ĐÃ ĐÓNG (27/09/2026).
--
-- Đóng lượt (check-out) trước bản sửa cùng ngày không đụng `queue_entry`, nên
-- khách đã về vẫn nằm trong hàng bàn khám / phòng dịch vụ ("waiting"). Đo trên
-- prod 27/09: 4 chỗ. Code nay chuyển chúng sang `left` ngay lúc đóng lượt
-- (`checkout_service.close`); migration này dọn phần đã lỡ. Chạy lại được.

UPDATE public.queue_entry q
   SET status = 'left', updated_at = now(), version = q.version + 1
  FROM public.visit v
 WHERE v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id
   AND v.closed_at IS NOT NULL
   AND q.status IN ('blocked', 'waiting', 'called', 'serving');
