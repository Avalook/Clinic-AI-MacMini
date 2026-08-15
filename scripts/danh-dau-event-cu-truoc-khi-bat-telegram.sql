-- Chạy MỘT LẦN, NGAY TRƯỚC khi bật notification-relay lần đầu.
--
-- Vì sao bắt buộc: relay đọc mọi dòng `event_log` có `event_published = FALSE`
-- từ CŨ NHẤT trở đi. Cờ ấy chưa từng được ai đánh dấu (relay tắt từ 09/08 —
-- "ngắt cái tele đã"), nên đến 15/08 đã tồn ~1.164 dòng trên prod. Bật relay
-- mà không chạy file này là nhóm Telegram nhận hàng trăm tin về những lịch
-- hẹn của NHIỀU NGÀY TRƯỚC — ngay trong mấy vòng poll đầu tiên.
--
-- Đánh dấu = "coi như đã đưa tin" cho mọi sự kiện SINH RA TRƯỚC lúc bật.
-- Không xoá gì: event_log vẫn nguyên vẹn cho Lịch sử thao tác và audit.
-- Sự kiện sinh ra SAU lúc chạy file này sẽ được relay đưa tin bình thường.
--
-- Cờ này chỉ của notification-relay — POS dùng bảng pos_outbox riêng
-- (ADR-0010), không đi qua đây.

UPDATE public.event_log
   SET event_published = TRUE
 WHERE event_published = FALSE;
