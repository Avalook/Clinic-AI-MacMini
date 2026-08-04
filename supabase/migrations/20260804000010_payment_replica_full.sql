-- `payment` phải bắn sự kiện realtime giống ba bảng cùng nhóm.
--
-- Màn check-out của Lễ tân đăng ký realtime trên `visit`, `work_item` và
-- `payment` — ba thứ quyết định một lượt khám đã đủ điều kiện đóng chưa. Ba
-- bảng kia đều đã là REPLICA IDENTITY FULL, riêng `payment` còn ở mặc định
-- (chỉ khoá chính).
--
-- VÌ SAO ĐIỀU ĐÓ QUAN TRỌNG. Với identity mặc định, bản ghi CŨ trong WAL chỉ
-- có khoá chính. Supabase Realtime phải chạy RLS trên bản ghi để quyết định có
-- đẩy cho subscriber hay không, nên với DELETE (và một số đường UPDATE) nó
-- không đủ dữ liệu để quyết định và im lặng bỏ qua.
--
-- "Im lặng bỏ qua" đúng là kiểu hỏng tệ nhất ở đây: không lỗi, không cảnh báo,
-- màn hình chỉ đơn giản là không đổi. Lễ tân sẽ tưởng thu ngân chưa thu tiền —
-- và bệnh nhân đứng chờ thêm cho tới nhịp mạch đập kế tiếp.
--
-- Cái giá là WAL to hơn cho mỗi lần ghi. Bảng này đang có 5 dòng và mỗi lượt
-- khám sinh nhiều nhất vài dòng, nên không đáng kể.

ALTER TABLE public.payment REPLICA IDENTITY FULL;

DO $verify$
DECLARE
    got "char";
BEGIN
    SELECT relreplident INTO got FROM pg_class
     WHERE oid = 'public.payment'::regclass;
    IF got <> 'f' THEN
        RAISE EXCEPTION 'payment.relreplident = % — mong đợi f (FULL)', got;
    END IF;
    RAISE NOTICE 'payment: REPLICA IDENTITY FULL, realtime bắn đủ mọi thao tác';
END
$verify$;
