-- Lý do làm lại — cột ghi chú KHÔNG BẮT BUỘC cho một lần hoàn tác.
--
-- Câu hỏi nghiệm thu của phòng khám (Đặng Dương, 17/08/2026): *"nếu nút đó
-- có cơ chế giống undo thì có phần ghi chú để ghi thông tin (ví dụ: lý do
-- làm lại) để nhân sự dễ báo cáo và quản lý nắm được thông tin không?"*
--
-- Giữ nguyên chốt của Quang 10/08 ("click vào nút tròn là tự back lại,
-- không cần xác nhận"): hoàn tác vẫn MỘT cú bấm, không hộp thoại chặn.
-- Lý do ghi SAU, tuỳ tâm — ai cần báo cáo thì có chỗ; ai đang vội thì
-- không bị một ô nhập bắt đứng lại. Dòng sổ vẫn không bao giờ bị xoá.

ALTER TABLE public.tuong_tac_cskh
    ADD COLUMN IF NOT EXISTS ly_do_hoan_tac text;

COMMENT ON COLUMN public.tuong_tac_cskh.ly_do_hoan_tac IS
    'Lý do làm lại (tuỳ chọn), ghi SAU khi hoàn tác — chỉ có nghĩa khi '
    'huy_luc khác NULL. Hoàn tác vẫn một cú bấm, không hộp thoại.';
