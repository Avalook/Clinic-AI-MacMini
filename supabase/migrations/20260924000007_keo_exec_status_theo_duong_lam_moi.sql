-- Kéo cột cũ `exec_status` theo `execution_status` cho các chỉ định đã làm bằng
-- đường làm mới (Slice 5) TRƯỚC bản vá 23/09/2026 22:00.
--
-- Bấm thật: phòng bấm Xong mà Bàn khám vẫn ghi "Chờ ở phòng" và không hiện nút
-- xem kết quả — Bàn khám, trưởng ca, xem lượt, hàng "chờ bác sĩ quyết" và vài
-- view SQL đọc `exec_status`, còn đường làm mới chỉ ghi `execution_status`. Từ
-- bản vá, `ServiceExecutionService._doi_trang_thai` ghi cả hai; migration này
-- chữa các dòng đã lệch trước đó. Chỉ đụng dòng đã qua nháp và có phòng (đúng
-- ràng buộc của cột cũ). Chạy lại được.

UPDATE public.service_order
   SET exec_status = CASE execution_status
                       WHEN 'IN_PROGRESS' THEN 'in_progress'
                       WHEN 'COMPLETED' THEN 'performed'
                     END,
       updated_at = now()
 WHERE execution_status IN ('IN_PROGRESS', 'COMPLETED')
   AND exec_status IN ('authorized', 'assigned', 'in_progress')
   AND exec_status IS DISTINCT FROM CASE execution_status
                                      WHEN 'IN_PROGRESS' THEN 'in_progress'
                                      WHEN 'COMPLETED' THEN 'performed'
                                    END
   AND room_id IS NOT NULL;
