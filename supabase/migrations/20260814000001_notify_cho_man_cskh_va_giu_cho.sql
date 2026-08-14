-- Năm bảng ĐANG ĐƯỢC NGHE mà chưa bao giờ PHÁT tin.
--
-- ĐÂY LÀ MỘT BẢN VÁ NỐI VÀO CƠ CHẾ ĐÃ BỎ.
--
-- 06/08/2026 (20260806000001) hệ thống bỏ Supabase Realtime, chuyển sang
-- LISTEN/NOTIFY: một trigger trên mỗi bảng bắn `pg_notify` lúc COMMIT, FastAPI
-- nghe rồi đẩy SSE về trình duyệt. Lý do là quyền REPLICATION — database cho
-- thuê không cấp.
--
-- 09/08/2026 (20260809000009) thêm bốn bảng của màn chăm sóc — `tuong_tac_cskh`,
-- `tep_ket_qua`, `phan_hoi_khach`, `hen_goi_lai` — vào PUBLICATION
-- `supabase_realtime`. Nhưng publication là cơ chế của Supabase Realtime, thứ
-- đã bị thay ba ngày trước đó. Bốn bảng ấy được nối vào một đường ống không còn
-- ai đứng ở đầu kia.
--
-- Hệ quả đúng bằng câu cảnh báo mà chính migration ấy viết ra: *"Hai CSKH ngồi
-- cạnh nhau… người thứ nhất ghi 'đã liên hệ', màn người thứ hai vẫn sáng 'Làm
-- bước này'… khách nghe máy hai lần trong một buổi."* Đo trên prod 14/08: 11
-- bảng có trigger, bốn bảng này KHÔNG có bảng nào.
--
-- `RealtimeRefresher.tsx` vẫn nghe đủ bốn bảng suốt thời gian đó. Nghe một thứ
-- không phát thì im lặng — không lỗi, không cảnh báo, chỉ là màn hình chỉ tự
-- mới sau nhịp dự phòng 60 giây.
--
-- ── VÀ `slot_hold`, VÌ CÙNG MỘT CÂU HỎI ────────────────────────────────────
--
-- Tuyền 14/08/2026: *"mỗi một vị trí lịch nào mà người này click thì cũng sẽ
-- hiện realtime trên màn hình của người kia, cả 8 CSKH cùng làm cũng sẽ đều
-- hiện như vậy"*.
--
-- Màn đặt lịch đang hỏi lại mỗi 5 giây, nên người bên cạnh biết sau ~2,5 giây
-- trung bình. Có tin đẩy thì con số ấy xuống còn một vòng mạng. Nhịp 5s vẫn
-- giữ làm lưới an toàn — dòng SSE có thể rớt, và khi ấy im lặng là thứ tệ nhất
-- ở đúng màn này.
--
-- KHÔNG thêm `slot_hold` vào `LIVE_TABLES` của RealtimeRefresher: nó gọi
-- `router.refresh()` cho mọi tin, tức là dựng lại toàn bộ cây server component.
-- Tám CSKH bấm lướt qua các khung giờ sẽ thành một trận mưa render trên mọi tab
-- đang mở, cho một thay đổi mà chỉ màn đặt lịch quan tâm. Màn ấy tự nghe lấy
-- và chỉ hỏi lại một endpoint nhẹ — xem BookingHub.

DO $$
DECLARE
    t text;
    bang text[] := ARRAY[
        'tuong_tac_cskh', 'tep_ket_qua', 'phan_hoi_khach', 'hen_goi_lai',
        'slot_hold'
    ];
BEGIN
    FOREACH t IN ARRAY bang LOOP
        -- Bảng có thể chưa tồn tại ở một nhánh triển khai cũ; bỏ qua thay vì
        -- làm hỏng cả chuỗi migration.
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
             WHERE table_schema = 'public' AND table_name = t
        ) THEN
            RAISE NOTICE 'bo qua % — bang chua ton tai', t;
            CONTINUE;
        END IF;
        -- Tin báo lọc theo phòng khám, nên bảng phải có cột ấy.
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = t
               AND column_name = 'clinic_id'
        ) THEN
            RAISE NOTICE 'bo qua % — khong co cot clinic_id', t;
            CONTINUE;
        END IF;

        EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I',
                       'trg_notify_' || t, t);
        EXECUTE format(
            'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION public.notify_row_change()',
            'trg_notify_' || t, t
        );
        RAISE NOTICE 'da gan trigger notify cho %', t;
    END LOOP;
END $$;
