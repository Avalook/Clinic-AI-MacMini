-- Lịch hẹn nhớ bác sĩ vừa bị gỡ khỏi nó.
--
-- Tuyền chốt 14/08/2026: quản lý gỡ ca trực của một bác sĩ thì lịch hẹn của
-- khách phải BỎ LUÔN bác sĩ ấy — *"còn để lại làm gì"* — và rơi về hàng "Chờ
-- xếp bác sĩ" để có người xếp lại.
--
-- VÌ SAO CẦN HAI CỘT NÀY, KHÔNG CHỈ ĐẶT doctor_id = NULL.
--
-- Đặt NULL rồi thôi là XOÁ MẤT MỘT SỰ THẬT: khách đã được hẹn với một bác sĩ
-- cụ thể, và CSKH sắp phải gọi giải thích. Không có tên người cũ thì câu gọi
-- chỉ còn là "lịch của chị bị đổi" — không nói được đổi từ ai, và người trực
-- không biết khách đang chờ gặp ai.
--
-- Nặng hơn: cảnh báo "bác sĩ đã đổi lịch làm việc" ở màn Quản lý khách hàng
-- xưa nay dựa vào việc lịch CÓ bác sĩ mà bác sĩ ấy không còn ca. Gỡ bác sĩ ra
-- là điều kiện ấy sai, và cảnh báo TỰ TẮT — đúng lúc nó cần thiết nhất. Hai
-- cột này giữ cho nó nói tiếp được, và nói rõ hơn: đổi từ ai.
--
-- `bo_bac_si_luc` tách riêng chứ không suy từ `updated_at`: một lịch còn được
-- sửa vì nhiều lý do khác, và trộn hai câu chuyện vào một mốc thời gian là mất
-- cả hai.

ALTER TABLE public.appointment
  ADD COLUMN IF NOT EXISTS bac_si_da_go_id uuid REFERENCES public.staff(id),
  ADD COLUMN IF NOT EXISTS bo_bac_si_luc   timestamptz;

COMMENT ON COLUMN public.appointment.bac_si_da_go_id IS
    'Bác sĩ từng phụ trách lịch này, bị gỡ khi ca trực của họ bị xoá. Giữ lại '
    'để CSKH gọi báo khách biết đổi từ ai, và để cảnh báo "bác sĩ đã đổi lịch" '
    'còn nói được sau khi doctor_id đã về NULL.';

COMMENT ON COLUMN public.appointment.bo_bac_si_luc IS
    'Lúc bác sĩ bị gỡ khỏi lịch này. Tách khỏi updated_at vì lịch còn được sửa '
    'vì nhiều lý do khác.';

-- Tra "những lịch đang chờ xếp lại vì bác sĩ nghỉ" — màn Chờ xếp bác sĩ và
-- cảnh báo ở màn khách hàng đều hỏi câu này. Chỉ đánh chỉ mục phần có dữ liệu:
-- tuyệt đại đa số lịch không bao giờ bị gỡ bác sĩ.
CREATE INDEX IF NOT EXISTS idx_appointment_bac_si_da_go
    ON public.appointment (clinic_id, slot_start)
 WHERE bac_si_da_go_id IS NOT NULL AND doctor_id IS NULL;
