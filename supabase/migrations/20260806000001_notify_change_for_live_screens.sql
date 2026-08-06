-- Báo thay đổi cho màn hình bằng LISTEN/NOTIFY, thay chỗ của Supabase Realtime.
--
-- VÌ SAO ĐỔI. Realtime đọc nhật ký WAL qua một replication slot, và tạo slot
-- cần quyền REPLICATION. Database cho thuê không cấp quyền ấy — đo trên Viettel
-- IDC 06/08/2026: pg_create_logical_replication_slot bị từ chối. Không phải
-- trục trặc cấu hình mà là chính sách, và AWS RDS hay Azure cũng như vậy.
--
-- NOTIFY thì là SQL thường, KHÔNG đòi quyền nào. Đổi sang nó là bỏ được một
-- ràng buộc về nhà cung cấp: hệ thống chạy được trên database thuê, trên
-- Postgres tự cài, ở đâu cũng thế.
--
-- ĐẶT Ở TRIGGER, KHÔNG Ở TẦNG DỊCH VỤ. Gọi pg_notify trong từng service thì
-- đúng cho tới lần đầu tiên có người thêm một đường ghi mới mà quên gọi — và
-- cái quên đó im lặng: màn hình chỉ đơn giản là không cập nhật nữa, không ai
-- thấy lỗi. Trigger thì không quên được. Đúng bậc thang của ADR-0003: chốt đặt
-- càng gần dữ liệu càng tốt.

CREATE OR REPLACE FUNCTION public.notify_row_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $$
DECLARE
    v_clinic uuid;
BEGIN
    -- DELETE thì dữ liệu nằm ở OLD. Không có dòng này, mọi lần xoá đều mất tin
    -- báo và màn hình giữ lại một hàng vừa biến mất.
    v_clinic := COALESCE(
        CASE WHEN TG_OP = 'DELETE' THEN OLD.clinic_id ELSE NEW.clinic_id END,
        NULL
    );

    IF v_clinic IS NOT NULL THEN
        -- TIN NGHÈO CÓ CHỦ Ý: chỉ tên bảng + phòng khám. Không gửi dữ liệu
        -- hàng, vì (1) NOTIFY có trần 8000 byte và một hàng bệnh án có thể
        -- vượt, làm HỎNG CẢ GIAO DỊCH GHI — tức là gửi kèm dữ liệu sẽ biến
        -- một tính năng hiển thị thành một lỗi mất bệnh án; và (2) đẩy dữ liệu
        -- qua đường này là mở một lối đọc nằm ngoài mọi lớp kiểm quyền của API.
        PERFORM pg_notify(
            'clinicai_changes',
            json_build_object('t', TG_TABLE_NAME, 'c', v_clinic)::text
        );
    END IF;

    RETURN NULL;  -- AFTER trigger: giá trị trả về không được dùng.
END;
$$;

COMMENT ON FUNCTION public.notify_row_change() IS
    'Bắn pg_notify(clinicai_changes) khi bảng có thay đổi. Tin chỉ gồm tên bảng '
    'và clinic_id — cố ý không kèm dữ liệu hàng (trần 8000 byte của NOTIFY, và '
    'để không mở lối đọc ngoài API).';

-- Gắn vào ĐÚNG những bảng có màn vẽ live — cùng danh sách với LIVE_TABLES
-- trong RealtimeRefresher.tsx. Thừa một bảng là mỗi lần ghi lại đánh thức mọi
-- màn hình cho một thay đổi không ai đang nhìn.
DO $$
DECLARE
    t text;
    bang text[] := ARRAY[
        'appointment', 'visit', 'work_item', 'work_item_event', 'payment',
        'lab_result', 'service_log', 'prescription', 'cskh_action',
        'staff_task', 'work_roster'
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
        -- Bảng phải có clinic_id thì tin báo mới lọc được theo phòng khám.
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
            'trg_notify_' || t, t);
    END LOOP;
END $$;
