-- HOÀN TÁC DỊCH VỤ ĐÃ ĐÓNG TẠI QUẦY (làm thêm tại quầy, Tuyền 01/10/2026).
--
-- Hoàn tất phiếu kết quả ở Đo sinh hiệu / Tiếp đón = dịch vụ làm thêm xong (lệnh
-- StartService + CompleteService có sẵn). Sửa lại / hoàn tác kết quả thì dịch vụ
-- về lại "chờ làm": lần làm quầy đã đóng chuyển INTERRUPTED với lý do hệ thống
-- RESULT_UNDONE (không xoá — vẫn đọc được là đã có lần ấy).
--
-- Chỉ MỞ RỘNG ràng buộc: mọi dòng cũ vẫn hợp lệ. Chạy lại được.

ALTER TABLE public.service_execution_attempt
    DROP CONSTRAINT IF EXISTS service_execution_attempt_reason_code;
ALTER TABLE public.service_execution_attempt
    ADD CONSTRAINT service_execution_attempt_reason_code CHECK (
        interruption_reason_code IS NULL
        OR interruption_reason_code IN ('EQUIPMENT_FAILURE', 'PATIENT_REQUEST',
            'CLINICAL_SAFETY', 'TECHNICAL_FAILURE', 'STAFF_UNAVAILABLE', 'OTHER',
            'PATIENT_MOVED', 'STARTED_IN_ERROR', 'RESULT_UNDONE'));
