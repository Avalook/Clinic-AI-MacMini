-- Realtime thật, và audit log đọc được bởi đúng những vai đã được mời vào màn.
--
-- BA VẤN ĐỀ ĐƯỢC SỬA Ở ĐÂY
--
-- 1. REALTIME CHƯA TỪNG BẬT (B2). RealtimeRefresher.tsx subscribe 20 bảng, còn
--    publication `supabase_realtime` chỉ có work_item + work_item_event
--    (20260803000003). Mười tám bảng còn lại — appointment, visit, payment,
--    lab_result — không phát ra sự kiện nào, nên "realtime" thực chất là
--    setInterval 25 giây. Cái pill xanh "Realtime +N cập nhật" ở màn Đặt lịch
--    đếm một dòng sự kiện không bao giờ tới.
--
--    Có `scripts/maintenance/enable_realtime_dynamic_tables.sql` làm đúng việc
--    này, nhưng nó nằm NGOÀI supabase/migrations/ nên `supabase db push` không
--    bao giờ chạy. Một thao tác phải-nhớ-chạy-tay là một thao tác sẽ quên.
--
--    KHÔNG publish tất cả. Mỗi bảng trong publication là một lần Realtime phải
--    chạy lại RLS cho từng subscriber trên từng thay đổi. Publish bảng mà không
--    màn nào vẽ live là trả giá CPU cho đúng 0 người. Danh sách dưới đây là các
--    bảng mà một màn hình đang mở PHẢI thấy đổi trong vòng một giây; phần còn
--    lại (patient, pregnancy, staff, work_session…) đổi theo nhịp hành chính và
--    poll 60 giây là đủ.
--
-- 2. AUDIT LOG DÙNG SAI NGUỒN QUYỀN (B3). Policy cũ hỏi
--    `current_staff_department() = 'MANAGEMENT'`, tức đọc staff.primary_department
--    — thuộc tính TOÀN CỤC của một con người. Cả hệ thống còn lại đã chuyển sang
--    clinic_membership.role, thuộc tính của người đó TRONG MỘT PHÒNG KHÁM
--    (identity.py: "A doctor may be MANAGEMENT at clinic A and DOCTOR at clinic
--    B"). Hệ quả: ai mang nhãn MANAGEMENT toàn cục đọc được audit của phòng khám
--    mà họ chỉ là bác sĩ.
--
-- 3. HAI PHẦN BA SỐ VAI ĐƯỢC VÀO MÀN NHÌN THẤY BẢNG RỖNG (D3). roles.ts mở
--    /audit-log cho CSKH + MANAGEMENT + TRUONG_CA, RLS chỉ cho MANAGEMENT. CSKH
--    và Trưởng ca bấm vào, thấy danh sách trống, không có lỗi nào giải thích.
--    Sửa ở phía RLS chứ không phải thu hẹp nav: xem lại-ai-đã-làm-gì là việc vận
--    hành, và đó đúng là ba vai vận hành.

-- KHÔNG có `\set ON_ERROR_STOP on` ở đây, và đó không phải thiếu sót.
--
-- `\set` là lệnh của psql, không phải SQL. `supabase db push` gửi thẳng nội dung
-- file xuống server, nên dòng đó thành `syntax error at or near "\"` và migration
-- đổ trước khi chạy được câu lệnh nào. Các fixture trong supabase/fixtures/ dùng
-- nó hợp lệ vì chúng chạy qua `psql -f`; migration thì không.
--
-- Dừng-khi-lỗi vẫn có: db push chạy mỗi migration trong một transaction và huỷ
-- toàn bộ khi có lỗi. Không cần khai báo gì thêm.

-- ---------------------------------------------------------------------------
-- 1. event_log: tenant-scoped theo VAI TRONG PHÒNG KHÁM
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS event_log_select_management ON public.event_log;
DROP POLICY IF EXISTS event_log_select_ops ON public.event_log;

CREATE POLICY event_log_select_ops
    ON public.event_log
    FOR SELECT
    TO authenticated
    USING (
        clinic_id IN (
            SELECT public.current_clinic_ids_for_roles(
                ARRAY['MANAGEMENT', 'TRUONG_CA', 'CSKH']
            )
        )
    );

COMMENT ON POLICY event_log_select_ops ON public.event_log IS
    'Vai VẬN HÀNH (Quản lý / Trưởng ca / CSKH) đọc audit của CHÍNH phòng khám '
    'mình đang là thành viên. Thay policy cũ dựa trên staff.primary_department, '
    'vốn là thuộc tính toàn cục và bỏ qua ranh giới tenant.';

-- current_staff_department() không còn người dùng nào sau thay đổi này. Giữ lại
-- hàm (có thể còn snippet/script gọi) nhưng gỡ quyền chạy của `authenticated`:
-- một hàm SECURITY DEFINER đọc bảng staff mà không ai cần thì không nên để mở.
REVOKE EXECUTE ON FUNCTION public.current_staff_department() FROM authenticated;

COMMENT ON FUNCTION public.current_staff_department() IS
    'DEPRECATED (20260803000004). primary_department là vai TOÀN CỤC; phân quyền '
    'phải hỏi clinic_membership.role qua current_clinic_ids_for_roles(). Không '
    'dùng trong policy mới.';

-- ---------------------------------------------------------------------------
-- 2. Realtime publication cho các bảng thật sự vẽ live
-- ---------------------------------------------------------------------------
-- ADD TABLE không idempotent (lỗi nếu đã có), nên kiểm pg_publication_tables
-- trước. Migration phải chạy lại được trên database đã áp dụng một phần.

DO $realtime$
DECLARE
    t text;
    live_tables text[] := ARRAY[
        -- Lịch hẹn + buổi khám: bàn lễ tân, bảng tuần, lưới đặt lịch.
        'appointment',
        'visit',
        -- Workflow kernel: đã có từ 20260803000003, liệt kê lại cho đủ danh sách
        -- (khối IF bên dưới bỏ qua nếu đã publish).
        'work_item',
        'work_item_event',
        -- Tiền + kết quả: bàn thu ngân, hàng đợi xét nghiệm, duyệt kết quả.
        'payment',
        'lab_result',
        'service_log',
        'prescription',
        -- Việc của người: hàng đợi CSKH, ca trực, bảng nhiệm vụ.
        'cskh_action',
        'staff_task',
        'work_roster'
    ];
BEGIN
    FOREACH t IN ARRAY live_tables LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables
             WHERE pubname = 'supabase_realtime'
               AND schemaname = 'public'
               AND tablename = t
        ) THEN
            EXECUTE format(
                'ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', t
            );
            RAISE NOTICE 'realtime: published %', t;
        END IF;
    END LOOP;
END
$realtime$;

-- REPLICA IDENTITY FULL chỉ cho bảng mà client lọc theo cột KHÔNG phải khoá
-- chính. Mặc định (DEFAULT) chỉ đưa khoá chính vào WAL cho UPDATE/DELETE, nên
-- một filter `clinic_id=eq.…` sẽ âm thầm trượt ở sự kiện DELETE và người dùng
-- thấy một dòng đã xoá nằm lại trên bảng.
--
-- FULL làm WAL to hơn, nên KHÔNG rải đại trà: chỉ các bảng mà UI có filter.
ALTER TABLE public.appointment  REPLICA IDENTITY FULL;
ALTER TABLE public.visit        REPLICA IDENTITY FULL;
ALTER TABLE public.work_item    REPLICA IDENTITY FULL;
ALTER TABLE public.staff_task   REPLICA IDENTITY FULL;

-- ---------------------------------------------------------------------------
-- 3. appointment.notes — ô "Ghi chú" ở màn đặt lịch chưa từng có chỗ để lưu
-- ---------------------------------------------------------------------------
-- BookingHub.tsx gửi `notes` trong body POST, /api/appointments không khai báo
-- trường đó nên nó rơi ở tầng đầu tiên, và appointment cũng không có cột nào để
-- nhận. CSKH gõ ghi chú, bấm lưu, hệ thống báo thành công, chữ biến mất.
--
-- Ghi chú đặt lịch là thông tin vận hành ("khách xin giờ linh động", "khách yêu
-- cầu BS Thành"), KHÔNG phải ghi chép lâm sàng — bệnh án có chỗ riêng và có luật
-- riêng (TT13/2011/TT-BYT). Đặt ở đây, đọc được bởi cùng những vai đọc được
-- lịch hẹn.

ALTER TABLE public.appointment
    ADD COLUMN IF NOT EXISTS notes text;

COMMENT ON COLUMN public.appointment.notes IS
    'Ghi chú vận hành khi đặt lịch (CSKH/Lễ tân nhập). KHÔNG phải ghi chép lâm '
    'sàng — bệnh án nằm ở clinical_record.';

-- ---------------------------------------------------------------------------
-- 4. is_walkin và booking_channel: hai cột, một sự thật, chỉ một cái được thi hành
-- ---------------------------------------------------------------------------
-- appointment có CẢ `is_walkin boolean` lẫn `booking_channel text`. Cả hai
-- trigger sức chứa (20260714000002 và 20260803000001) chỉ đọc booking_channel:
--
--     v_walkin := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';
--
-- Nhưng scheduling_service.py — đường tạo lịch của agent LangGraph — chỉ ghi
-- `is_walkin`, để booking_channel NULL. Nghĩa là một lịch vãng lai do agent tạo
-- được trigger đếm vào NHÓM ĐẶT TRƯỚC. Hai cột cùng nói một việc, chỉ một cái
-- có hiệu lực, và đường ghi vào chúng lại khác nhau.
--
-- Chuẩn hoá về booking_channel (cột mà trigger thi hành), rồi ràng buộc để hai
-- cột không được mâu thuẫn nữa.

UPDATE public.appointment
   SET booking_channel = 'WALK_IN'
 WHERE is_walkin
   AND coalesce(upper(booking_channel), '') <> 'WALK_IN';

UPDATE public.appointment
   SET is_walkin = TRUE
 WHERE NOT is_walkin
   AND upper(coalesce(booking_channel, '')) = 'WALK_IN';

-- NOT VALID: ràng buộc mọi dòng MỚI, không quét lại lịch sử. Hai lệnh UPDATE ở
-- trên đã dọn hiện trạng; nếu còn sót dòng cũ nào không hợp lệ thì đó là dữ
-- liệu cần người xem, không phải lý do để migration đổ.
ALTER TABLE public.appointment
    DROP CONSTRAINT IF EXISTS appointment_walkin_channel_agree;
ALTER TABLE public.appointment
    ADD CONSTRAINT appointment_walkin_channel_agree
    CHECK (is_walkin = (upper(coalesce(booking_channel, '')) = 'WALK_IN'))
    NOT VALID;

COMMENT ON CONSTRAINT appointment_walkin_channel_agree ON public.appointment IS
    'booking_channel là nguồn sự thật (trigger sức chứa đọc nó). is_walkin là '
    'cột tiện đọc và phải khớp — không được để hai cột nói hai chuyện.';

-- ---------------------------------------------------------------------------
-- 5. Chỉ mục cho đường đọc audit log
-- ---------------------------------------------------------------------------
-- Màn /audit-log đọc 200 dòng mới nhất của MỘT phòng khám. Không có chỉ mục
-- này thì Postgres quét toàn bảng append-only rồi sort — chi phí tăng đều theo
-- tuổi đời hệ thống, và đó đúng là bảng lớn nhanh nhất.

CREATE INDEX IF NOT EXISTS idx_event_log_clinic_occurred
    ON public.event_log (clinic_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_work_item_event_clinic_occurred
    ON public.work_item_event (clinic_id, occurred_at DESC);
