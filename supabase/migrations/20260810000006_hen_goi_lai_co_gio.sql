-- Hẹn gọi lại phải có GIỜ, không chỉ có ngày.
--
-- QUANG 10/08/2026: *"khách nói đang họp, gọi lại sau 5h… thêm 1 nút là gọi lại
-- vào lúc ... giờ và cho chọn giờ, sinh sự kiện thật để thông báo cho cskh gọi
-- lại cho không bị quên"*.
--
-- `hen_goi_lai.ngay_goi` là `date`. Với một lời hẹn kiểu "khách đang họp, 5h
-- chiều gọi lại" thì cả ngày hôm nay là câu trả lời sai: gọi lúc 9h sáng vẫn
-- đúng "ngày", và vẫn làm phiền đúng người mình vừa hứa sẽ không làm phiền.
--
-- CỘT MỚI CHO PHÉP NULL, cố ý. Những lời hẹn đã có trong bảng được đặt khi màn
-- hình chỉ hỏi ngày — gán bừa 00:00 cho chúng là bịa ra một thông tin chưa ai
-- từng nhập, và từ đó không phân biệt được "hẹn đầu giờ" với "không ai nói
-- giờ". NULL đọc đúng: chỉ hẹn tới ngày.

ALTER TABLE public.hen_goi_lai
    ADD COLUMN IF NOT EXISTS gio_goi time;

COMMENT ON COLUMN public.hen_goi_lai.gio_goi IS
    'Giờ hẹn gọi lại trong ngày `ngay_goi`, giờ phòng khám (Asia/Ho_Chi_Minh). '
    'NULL = chỉ hẹn tới ngày, không ai nói giờ — KHÔNG phải 00:00.';
