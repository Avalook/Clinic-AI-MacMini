-- LÀM DỊCH VỤ KHÔNG THEO THỨ TỰ (V4, Tuyền 30/09/2026 — "mở hết").
--
-- Trước đây phòng B bấm Bắt đầu khi khách còn "đang làm" ở phòng A thì nhận 409
-- PATIENT_BUSY cứng (prod 29/09: 23 lần trong một ngày). Nay phòng B hỏi tại chỗ
-- "Khách đang ở phòng A — chuyển sang đây?" rồi, trong CÙNG giao dịch, dừng lần
-- làm ở phòng A với lý do mới PATIENT_MOVED. Thêm một lối thoát nữa: "Huỷ bắt đầu
-- nhầm" — lần làm vừa mở mà chưa điền gì đóng với lý do STARTED_IN_ERROR.
--
-- Cả hai là lý do HỆ THỐNG ghi (không có trong danh sách người chọn khi bấm Dừng).
-- Chỉ MỞ RỘNG ràng buộc: mọi dòng cũ vẫn hợp lệ. Chạy lại được.

ALTER TABLE public.service_execution_attempt
    DROP CONSTRAINT IF EXISTS service_execution_attempt_reason_code;
ALTER TABLE public.service_execution_attempt
    ADD CONSTRAINT service_execution_attempt_reason_code CHECK (
        interruption_reason_code IS NULL
        OR interruption_reason_code IN ('EQUIPMENT_FAILURE', 'PATIENT_REQUEST',
            'CLINICAL_SAFETY', 'TECHNICAL_FAILURE', 'STAFF_UNAVAILABLE', 'OTHER',
            'PATIENT_MOVED', 'STARTED_IN_ERROR'));
