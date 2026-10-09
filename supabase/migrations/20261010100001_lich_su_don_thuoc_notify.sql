-- Khung lịch sử đơn tự đọc cả hoàn tiền và ngày hẹn trên phiếu khám.
-- Chỉ nghe ở trình duyệt thì chưa đủ: các bảng này phải phát tin lúc COMMIT.
BEGIN;

DROP TRIGGER IF EXISTS trg_notify_payment_refund ON public.payment_refund;
CREATE TRIGGER trg_notify_payment_refund
AFTER INSERT OR UPDATE OR DELETE ON public.payment_refund
FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

DROP TRIGGER IF EXISTS trg_notify_payment_refund ON public.payment_refund;
DROP TRIGGER IF EXISTS trg_notify_payment_refund_line ON public.payment_refund_line;
CREATE TRIGGER trg_notify_payment_refund_line
AFTER INSERT OR UPDATE OR DELETE ON public.payment_refund_line
FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

DROP TRIGGER IF EXISTS trg_notify_phieu_kham_luot ON public.phieu_kham_luot;
CREATE TRIGGER trg_notify_phieu_kham_luot
AFTER INSERT OR UPDATE OR DELETE ON public.phieu_kham_luot
FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

NOTIFY pgrst, 'reload schema';
COMMIT;
