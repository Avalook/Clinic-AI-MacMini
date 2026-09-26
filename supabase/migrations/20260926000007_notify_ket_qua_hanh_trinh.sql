-- TIN THỜI GIAN THỰC cho kết quả và hành trình (26/09/2026 — lát 4 bản giao diện mẫu).
--
-- Phòng dịch vụ nhập xong phiếu kết quả mà bàn bác sĩ không biết: `form_instance`
-- chưa bắn tin nên màn bác sĩ đợi nhịp dự phòng 60 giây. `luot_dong_thoi_gian` do
-- người đưa tin ghi SAU giao dịch gốc — trang dựng lại theo tin của giao dịch gốc
-- có thể chưa thấy dòng hành trình mới; tin của chính bảng này vá kẽ đó.
--
-- `form_instance` CHỈ báo khi đổi TRẠNG THÁI (tạo / xoá / DRAFT→READY / mở sửa):
-- tự lưu nháp ghi dòng này liên tục, báo mỗi lần là mọi tab đang mở dựng lại trang
-- theo nhịp gõ phím. Tin vẫn nghèo như mọi bảng khác (tên bảng + phòng khám).

DROP TRIGGER IF EXISTS trg_notify_form_instance ON public.form_instance;
CREATE TRIGGER trg_notify_form_instance
    AFTER INSERT OR DELETE OR UPDATE OF trang_thai, dang_sua ON public.form_instance
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

DROP TRIGGER IF EXISTS trg_notify_luot_dong_thoi_gian ON public.luot_dong_thoi_gian;
CREATE TRIGGER trg_notify_luot_dong_thoi_gian
    AFTER INSERT ON public.luot_dong_thoi_gian
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
