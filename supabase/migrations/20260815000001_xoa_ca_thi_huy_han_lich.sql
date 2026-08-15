-- Xoá ca trực thì lịch hẹn của ca ấy phải CÓ CÁI KẾT THÚC.
--
-- CHUYỆN TUYỀN VỪA GẶP (15/08/2026). Xoá ca của bác sĩ → lịch 7:00 chủ nhật
-- rơi về "chờ xếp bác sĩ" nhưng vẫn là một lịch CÒN SỐNG đứng nguyên ở khung
-- ấy. Lưới đặt chỗ nói khung trống (0/2 — đúng, lịch không bác sĩ không chiếm
-- ghế của ai), nhưng bấm đặt lại cùng khung cho chính khách ấy với bác sĩ khác
-- thì `_patient_conflict` chặn: "khách ĐÃ có lịch lúc 7:00". Một lịch không
-- bao giờ kết thúc, chặn chính con đường sửa nó — "có sự kiện thì phải có kết
-- thúc, không sinh ra chạy vô tận" (Tuyền).
--
-- KẾT THÚC = HUỶ, với mã lý do riêng. `BAC_SI_DOI_LICH` tách khỏi ba mã BAO_*
-- (khách báo không đến — lỗi phía khách) và DAT_TRUNG (phòng khám đặt trùng):
-- ở đây khách không làm gì cả, phòng khám đổi ca bác sĩ nên chủ động huỷ để
-- đặt lại. Đếm chung với mã nào khác đều làm sai con số của mã đó.

ALTER TABLE public.appointment
    DROP CONSTRAINT IF EXISTS appointment_ly_do_huy_ma_check;

ALTER TABLE public.appointment
    ADD CONSTRAINT appointment_ly_do_huy_ma_check
    CHECK (ly_do_huy_ma IS NULL
           OR ly_do_huy_ma IN ('BAO_KHI_XAC_NHAN',
                               'BAO_KHI_NHAC_HEN',
                               'BAO_VAO_GIO_KHAM',
                               'DAT_TRUNG',
                               'BAC_SI_DOI_LICH',
                               'KHAC'));

COMMENT ON COLUMN public.appointment.ly_do_huy_ma IS
    'Mã lý do huỷ. Ba mã BAO_* là BA THỜI ĐIỂM khách báo không đến. DAT_TRUNG '
    'là dọn lịch phòng khám tự đặt trùng. BAC_SI_DOI_LICH là phòng khám chủ '
    'động huỷ vì ca trực của bác sĩ bị xoá/đổi — khách không làm gì cả, và '
    'lịch phải được huỷ hẳn để khung giờ đặt lại được cho khách ấy. '
    'Danh mục phải khớp LY_DO_HUY ở booking_service.py và lib/ly-do-huy.ts.';

-- DỌN NHỮNG LỊCH ĐANG KẸT Ở TRẠNG THÁI KHÔNG KẾT THÚC. Chúng sinh ra trong
-- khoảng 14–15/08 khi remove() mới chỉ gỡ bác sĩ mà chưa huỷ: còn sống, không
-- bác sĩ, mang vết bị gỡ — và đang chặn khách của chính chúng đặt lại đúng
-- khung. Huỷ đúng cách chúng ĐÁNG được huỷ từ đầu; vết `bac_si_da_go_id` giữ
-- nguyên để màn hình còn nói được "đổi từ ai".
UPDATE public.appointment
   SET status = 'CANCELLED',
       cancelled_at = now(),
       ly_do_huy_ma = 'BAC_SI_DOI_LICH'
 WHERE doctor_id IS NULL
   AND bac_si_da_go_id IS NOT NULL
   AND status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED');
