-- Chín bảng đang phát realtime cho đúng không người nghe. Năm trong đó là hồ sơ
-- lâm sàng.
--
-- PHÁT HIỆN RA THẾ NÀO. Sau khi 20260803000004 publish 11 bảng mà giao diện thật
-- sự vẽ live, đếm lại publication trên prod ra 20. Chín bảng dôi ra:
--
--     patient · clinical_record · clinical_form_response · ultrasound_record
--     patient_medical_profile · pregnancy · cskh_log · staff · work_session
--
-- Không migration nào thêm chúng. Chúng vào publication bằng tay — hoặc qua
-- `scripts/maintenance/enable_realtime_dynamic_tables.sql` (nằm ngoài
-- supabase/migrations/, nên không ai biết nó đã chạy hay chưa), hoặc bằng vài cú
-- bấm trong dashboard Supabase. Đúng kiểu thay đổi mà CLAUDE.md cấm: "Never edit
-- schema by hand in the dashboard."
--
-- HAI CÁI GIÁ, VÀ CÁI THỨ HAI MỚI ĐÁNG NÓI.
--
-- 1. CPU. Realtime chạy lại RLS cho TỪNG subscriber trên TỪNG thay đổi của mỗi
--    bảng được publish. Chín bảng không ai nghe là công việc đó lặp lại suốt
--    ngày để không đưa dữ liệu cho ai cả.
--
-- 2. PII đi qua một dịch vụ không cần thấy nó. patient, clinical_record,
--    ultrasound_record, patient_medical_profile, pregnancy — nội dung từng dòng
--    được đẩy vào Realtime để nó quyết định gửi cho ai. RLS chặn đúng ở bước
--    cuối, nên đây KHÔNG phải lỗ rò: không ai nhận được gì. Nhưng dữ liệu bệnh
--    nhân rời khỏi Postgres và đi qua một tầng nữa mà không phục vụ mục đích
--    nào. Bề mặt tiếp xúc nhỏ nhất là bề mặt không tồn tại.
--
-- ĐÃ KIỂM TRƯỚC KHI GỠ: toàn bộ mã client chỉ subscribe hai bảng ngoài
-- RealtimeRefresher — work_roster (NotificationContext) và staff_task
-- (TasksRealtime). Cả hai nằm trong danh sách 11 bảng và KHÔNG bị gỡ ở đây.
--
-- Muốn cho một màn hình nghe lại bảng nào: thêm vào LIVE_TABLES trong
-- RealtimeRefresher.tsx VÀ vào một migration. Test
-- test_realtime_publication_matches_client giữ hai danh sách đó khớp nhau, nên
-- lệch một bên sẽ đỏ chứ không im lặng như lần này.

DO $unpublish$
DECLARE
    t text;
    unwatched text[] := ARRAY[
        'patient',
        'clinical_record',
        'clinical_form_response',
        'ultrasound_record',
        'patient_medical_profile',
        'pregnancy',
        'cskh_log',
        'staff',
        'work_session'
    ];
BEGIN
    FOREACH t IN ARRAY unwatched LOOP
        IF EXISTS (
            SELECT 1 FROM pg_publication_tables
             WHERE pubname = 'supabase_realtime'
               AND schemaname = 'public'
               AND tablename = t
        ) THEN
            EXECUTE format(
                'ALTER PUBLICATION supabase_realtime DROP TABLE public.%I', t
            );
            RAISE NOTICE 'realtime: unpublished %', t;
        END IF;
    END LOOP;
END
$unpublish$;

-- REPLICA IDENTITY trả về mặc định cho các bảng vừa gỡ.
--
-- FULL đưa TOÀN BỘ dòng cũ vào WAL trên mỗi UPDATE/DELETE. Với bảng còn phát
-- realtime và có filter thì đó là cái giá phải trả (xem 20260803000004). Với
-- bảng không còn phát thì nó chỉ làm WAL to ra — và với bảng bệnh án, nó ghi
-- thêm một bản sao đầy đủ của mỗi dòng vào nhật ký giao dịch mà không ai đọc.
DO $replica$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['patient','clinical_record','ultrasound_record',
                             'patient_medical_profile','pregnancy','staff',
                             'work_session','cskh_log','clinical_form_response']
    LOOP
        IF EXISTS (
            SELECT 1 FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relname = t
               AND c.relreplident = 'f'
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.%I REPLICA IDENTITY DEFAULT', t
            );
            RAISE NOTICE 'replica identity: % → DEFAULT', t;
        END IF;
    END LOOP;
END
$replica$;
