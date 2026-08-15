-- Đánh thức relay Telegram NGAY khi có sự kiện — thay vì chờ vòng poll 30s.
--
-- Tuyền 15/08/2026: "có cho realtime được không". Đường realtime của nhà đã
-- có sẵn (notify_row_change → pg_notify('clinicai_changes') → SSE cho màn
-- hình); relay chỉ cần NGHE cùng kênh ấy. Trigger này gắn nó cho event_log.
--
-- CHỈ INSERT, KHÔNG UPDATE — và đây là chỗ dễ hỏng nhất nếu ai "dọn dẹp"
-- cho giống các bảng khác: relay xử lý xong thì UPDATE event_published=TRUE
-- lên chính bảng này. Nghe cả UPDATE là relay tự đánh thức mình sau mỗi lần
-- gửi — một vòng lặp poll rỗng vô tận, mỗi tin gửi đi kèm một cú quét thừa.
--
-- Nhịp poll 30s của relay VẪN GIỮ: nó là lưới an toàn cho lúc connection
-- LISTEN rớt — notify là tối ưu độ trễ, không phải chỗ dựa duy nhất.

DROP TRIGGER IF EXISTS trg_notify_event_log ON public.event_log;
CREATE TRIGGER trg_notify_event_log
    AFTER INSERT ON public.event_log
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
