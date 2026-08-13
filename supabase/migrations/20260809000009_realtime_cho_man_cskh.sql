-- Bốn bảng của màn chăm sóc phải phát realtime.
--
-- CHUYỆN SẼ XẢY RA NẾU KHÔNG. Hai CSKH ngồi cạnh nhau cùng mở màn Quản lý
-- khách hàng. Người thứ nhất gọi cho chị Lan, ghi "đã liên hệ" — màn người thứ
-- hai vẫn sáng "Làm bước này", vì nó chỉ nạp lại khi chính người đó thao tác.
-- Người thứ hai gọi lần nữa. Khách nghe máy hai lần trong một buổi, và đó đúng
-- là thứ chuỗi bước sinh ra để chống.
--
-- `RealtimeRefresher` đã nghe bốn bảng này từ cùng ngày, nhưng NGHE THÔI KHÔNG
-- ĐỦ: Postgres chỉ phát thay đổi của bảng nằm trong publication. Thiếu ở đây
-- thì danh sách bên kia im lặng vô dụng — không lỗi, không cảnh báo, chỉ là
-- màn hình không bao giờ tự mới.

-- CÁCH VIẾT THEO ĐÚNG KHUÔN 20260803000004 (`live_tables text[] := ARRAY[…]`).
-- Không phải cho đẹp: `test_realtime_publication_matches_client` đọc migration
-- bằng biểu thức chính quy để đối chiếu với danh sách ở RealtimeRefresher.tsx,
-- và nó chỉ hiểu hai cách viết đã có. Đẻ ra cách thứ ba là bài kiểm ấy im lặng
-- bỏ qua bảng mới — đúng thứ nó sinh ra để chống.
DO $$
DECLARE
    live_tables text[] := ARRAY[
        'tuong_tac_cskh', 'tep_ket_qua', 'phan_hoi_khach', 'hen_goi_lai'
    ];
    ten text;
BEGIN
    FOREACH ten IN ARRAY live_tables LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables
             WHERE pubname = 'supabase_realtime'
               AND schemaname = 'public'
               AND tablename = ten
        ) THEN
            EXECUTE format(
                'ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', ten
            );
            RAISE NOTICE 'Đã thêm % vào publication realtime.', ten;
        END IF;
    END LOOP;
END $$;
