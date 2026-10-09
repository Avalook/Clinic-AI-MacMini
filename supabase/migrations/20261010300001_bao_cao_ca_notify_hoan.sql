-- Báo cáo ca phải cập nhật khi hoàn tiền đổi trạng thái/số tiền.
-- Chỉ thêm kênh báo tin nội bộ; không đổi RLS hoặc quyền đọc bảng.
DROP TRIGGER IF EXISTS trg_notify_payment_refund ON public.payment_refund;
CREATE TRIGGER trg_notify_payment_refund
AFTER INSERT OR UPDATE OR DELETE ON public.payment_refund
FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
