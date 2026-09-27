-- Bảng CÒN LẠI chưa phát tin cho dòng SSE — chuông thông báo (27/09/2026).
--
-- BỐI CẢNH. Bốn màn (chuông thông báo, trưởng ca, check-out, lịch hẹn) vẫn tự
-- đăng ký `postgres_changes` của Supabase Realtime. Đường ấy không chạy được
-- trên Postgres của mình: Realtime cần replication slot với plugin wal2json, và
-- Postgres từ chối — "library wal2json may not be used as an output plugin".
-- Đo trên prod 27/09: ~8.600 dòng ERROR mỗi ngày, và bốn màn ấy chưa từng nhận
-- một tin tức thời nào — chúng sống bằng nhịp dự phòng của riêng mình.
--
-- Cùng đợt này, bốn màn chuyển sang dòng tin chuẩn của hệ thống: trigger
-- `notify_row_change` → pg_notify('clinicai_changes') → FastAPI SSE →
-- RealtimeRefresher → SU_KIEN_BANG (20260806000001). Mọi bảng các màn ấy nghe
-- đều đã có trigger `trg_notify_*` — TRỪ `thong_bao`, nguồn của chuông: cuộc
-- gọi KHẨN của trưởng ca tới một bộ phận. Thiếu nó thì chuông đỏ chờ tới nhịp
-- poll 20 giây, đúng loại việc không được chờ.
--
-- TIN VẪN NGHÈO như mọi bảng khác: chỉ tên bảng + clinic_id (xem
-- notify_row_change). KHÔNG có tiêu đề, nội dung, người nhận — `thong_bao` có
-- thể gọi tới MỘT người, và broker phát theo phòng khám tới mọi màn đang mở.
-- Chuông nghe tin rồi tự đọc lại qua API, nơi lọc đúng người nhận.
--
-- Nghe cả UPDATE: "đã đọc" / "đã xử lý" đổi dòng dùng chung của cả bộ phận,
-- nên chuông của người cùng vai phải thôi đỏ ngay khi một người đã nhận việc.

DO $$
DECLARE
    t text;
    bang text[] := ARRAY['thong_bao'];
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
