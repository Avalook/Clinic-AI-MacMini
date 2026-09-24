-- Thu QR / chuyển khoản KHÔNG bắt buộc mã giao dịch (Tuyền 24/09/2026: "lúc thanh
-- toán mà chọn qr hoặc chuyển khoản thì không được bắt buộc điền mã mới cho
-- thanh toán xong nhé, open đi").
--
-- Trước: lần chờ xác minh chỉ thành PAID khi có mã giao dịch ngân hàng
-- (contract A2 "mã là bằng chứng"). Nay mã là TUỲ CHỌN — có thì vẫn lưu và vẫn
-- chống xác minh hai lần bằng hai mã khác nhau (ở service); người bấm "đã nhận
-- tiền" (`confirmed_by`, bắt buộc) là dấu vết. Mã đã ghi thì vẫn không sửa được
-- (trigger trg_payment_cycle_guard giữ nguyên).
--
-- Chạy lại được.

ALTER TABLE public.payment_cycle DROP CONSTRAINT IF EXISTS payment_cycle_dien_tu_co_ma;
