-- Khách có hẹn đến MUỘN chiếm một ghế vãng lai của khung họ thật sự có mặt.
--
-- Luật Quang mô tả: "khách đặt lịch mà không đến trong khung của mình thì
-- thành khách vãng lai của khung tiếp theo, và chiếm một suất vãng lai của
-- khung đó."
--
-- Nửa HIỂN THỊ đã làm (services/queue_order.py: người đến muộn rơi xuống làn 1,
-- xếp theo giờ tới nơi). Nửa THI HÀNH thì chưa: sức chứa vẫn đếm ghế vãng lai
-- bằng đúng số lịch có `booking_channel = 'WALK_IN'` đặt vào khung. Hệ quả trên
-- quầy: khung 18:15 có một ghế vãng lai, một người hẹn 18:00 tới lúc 18:20 —
-- hệ thống vẫn mời lễ tân nhận thêm một khách vãng lai nữa, và bác sĩ nhận hai
-- người trong một chỗ.
--
-- "Khung TIẾP THEO" ở đây hiểu là KHUNG HỌ THẬT SỰ CÓ MẶT. Người hẹn 18:00 mà
-- 18:45 mới tới thì ngồi ở khung 18:45; trừ ghế của khung 18:15 — một khung đã
-- trôi qua — không mô tả được cái gì đang xảy ra trong phòng chờ.
--
-- Ranh giới "muộn" không cần khai lại ở đây: cửa sổ đúng giờ dài đúng bằng
-- khung (clinic_policy.grace_ms_from_slot_minutes), nên "check-in rơi vào một
-- khung SAU khung của mình" và "đến muộn" là cùng một câu.

-- ---------------------------------------------------------------------------
-- 1. Đếm ghế đã dùng — MỘT nguồn cho cả ba nơi hỏi
-- ---------------------------------------------------------------------------
-- Ba chỗ cùng cần con số này: trigger (chặn), booking_service (câu tiếng Việt
-- cho lễ tân), capacity_service (tô màu ô lịch). Trước đây mỗi nơi tự đếm bằng
-- SQL riêng — ba bản chép tay của một luật, và luật vừa đổi.
--
-- SECURITY DEFINER vì nó phải đọc `visit`, mà `visit` có RLS: người gọi là lễ
-- tân đang ghi một dòng `appointment`. Hàm chỉ trả về MỘT SỐ ĐẾM, không trả
-- dòng nào, nên không có gì rò ra ngoài phạm vi phòng khám đã truyền vào.

CREATE OR REPLACE FUNCTION public.slot_seats_used(
    p_clinic_id            uuid,
    p_doctor_id            uuid,
    p_bucket_start         timestamptz,
    p_bucket_end           timestamptz,
    p_walkin               boolean,
    p_exclude_appointment  uuid DEFAULT NULL,
    -- Lọc theo CƠ SỞ, giữ nguyên hành vi hôm nay của lưới đặt lịch.
    --
    -- Trigger truyền NULL (đếm mọi cơ sở): một bác sĩ không ở hai nơi cùng lúc,
    -- nên trần của họ là trần chung. Lưới thì truyền cơ sở đang xem, vì nó đang
    -- vẽ lịch của một cơ sở. HAI CON SỐ ẤY CÓ THỂ LỆCH NHAU — lưới nói còn chỗ
    -- trong khi trigger từ chối, nếu bác sĩ đã kín ở cơ sở khác. Đó là chuyện
    -- có từ trước migration này; ghi ra đây để nó không còn im lặng, và để lần
    -- sửa nó là một quyết định chứ không phải một tác dụng phụ.
    p_location_id          uuid DEFAULT NULL
)
RETURNS integer
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
    SELECT count(*)::integer
      FROM public.appointment a
     WHERE a.clinic_id = p_clinic_id
       AND a.id IS DISTINCT FROM p_exclude_appointment
       AND a.location_id IS NOT DISTINCT FROM
           coalesce(p_location_id, a.location_id)
       -- Cùng cách so bác sĩ mà trigger dùng: NULL khớp NULL (hàng "chưa phân
       -- bác sĩ" là một hàng riêng, có sức chứa riêng).
       AND coalesce(a.doctor_id::text, '~none~')
           = coalesce(p_doctor_id::text, '~none~')
       AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')
       AND CASE WHEN p_walkin THEN
                -- Ghế vãng lai: khách vãng lai đặt vào khung này …
                (upper(coalesce(a.booking_channel, '')) = 'WALK_IN'
                 AND a.slot_start >= p_bucket_start
                 AND a.slot_start <  p_bucket_end)
                -- … CỘNG khách có hẹn đến muộn, có mặt trong khung này.
             OR (upper(coalesce(a.booking_channel, '')) <> 'WALK_IN'
                 AND a.slot_start < p_bucket_start
                 AND EXISTS (
                     SELECT 1
                       FROM public.visit v
                      WHERE v.appointment_id = a.id
                        AND v.checked_in_at >= p_bucket_start
                        AND v.checked_in_at <  p_bucket_end))
           ELSE
                -- Ghế đặt hẹn: KHÔNG đổi. Người đến muộn vẫn giữ ghế đặt hẹn
                -- của khung cũ — họ đã đặt nó từ trước, và trả lại ghế ấy cho
                -- người khác vào lúc này thì không ai dùng được nữa.
                (upper(coalesce(a.booking_channel, '')) <> 'WALK_IN'
                 AND a.slot_start >= p_bucket_start
                 AND a.slot_start <  p_bucket_end)
           END
$function$;

COMMENT ON FUNCTION public.slot_seats_used(
    uuid, uuid, timestamptz, timestamptz, boolean, uuid, uuid) IS
  'Số ghế đã dùng của một khung. Ghế vãng lai tính CẢ khách có hẹn đến muộn '
  'đang có mặt trong khung (20260807000001). Nguồn DUY NHẤT cho trigger sức '
  'chứa, booking_service và capacity_service.';

-- ---------------------------------------------------------------------------
-- 2. Trigger dùng chung phép đếm ấy
-- ---------------------------------------------------------------------------
-- Kèm một sửa lỗi bắt buộc phải đi cùng: TRẢ VỀ SỚM KHI DÒNG ĐÃ GIỮ GHẾ.
--
-- Trigger chạy BEFORE UPDATE OF (slot_start, doctor_id, booking_channel,
-- status). Cột `status` khiến MỌI bước vòng đời — check-in, khám xong — chạy
-- lại phép đếm. Trước đây vô hại: dòng tự loại mình ra (`a.id <> NEW.id`) nên
-- số đếm luôn nhỏ hơn trần ít nhất một.
--
-- Với phép đếm mới thì KHÔNG còn vô hại. Một khách vãng lai đã ngồi trong
-- khung, rồi một người có hẹn đến muộn bước vào cùng khung: số ghế vãng lai đã
-- dùng thành 2 trên trần 1. Từ lúc đó, đổi trạng thái dòng vãng lai kia — kể
-- cả "khám xong" — sẽ bị chính trigger này từ chối, dù nó chẳng đòi ghế nào.
--
-- Luật đúng: chỉ kiểm khi dòng ĐANG ĐÒI một ghế. Dòng còn sống mà không đổi
-- ba cột định vị ghế thì nó đã giữ ghế từ trước. Dòng vừa sống lại từ
-- CANCELLED/NO_SHOW thì có đòi ghế, và vẫn bị kiểm.

CREATE OR REPLACE FUNCTION public.enforce_slot_capacity()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    dead         text[] := ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'];
    none         text   := '~none~';
    bucket_start timestamptz;
    bucket_end   timestamptz;
    v_walkin     boolean;
    v_minutes    integer;
    v_seconds    integer;
    cap          integer;
    live_count   integer;
    lock_key     bigint;
BEGIN
    IF NEW.status = ANY (dead) THEN
        RETURN NEW;
    END IF;

    -- Đã giữ ghế từ trước → không đòi ghế mới → không kiểm. Xem ghi chú trên.
    IF TG_OP = 'UPDATE'
       AND NOT (OLD.status = ANY (dead))
       AND OLD.slot_start = NEW.slot_start
       AND OLD.doctor_id IS NOT DISTINCT FROM NEW.doctor_id
       AND upper(coalesce(OLD.booking_channel, ''))
           = upper(coalesce(NEW.booking_channel, ''))
    THEN
        RETURN NEW;
    END IF;

    v_walkin := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';

    -- C.4: resolve from 3-tier override stack instead of clinic-only.
    SELECT p.slot_minutes,
           CASE WHEN v_walkin THEN p.walkin_cap ELSE p.regular_cap END
      INTO v_minutes, cap
      FROM public.resolve_effective_cap(
               NEW.clinic_id, NEW.doctor_id, NEW.slot_start) AS p;

    v_seconds    := v_minutes * 60;
    bucket_start := to_timestamp(
        floor(extract(epoch FROM NEW.slot_start) / v_seconds) * v_seconds);
    bucket_end   := bucket_start + make_interval(mins => v_minutes);

    lock_key := hashtextextended(
        NEW.clinic_id::text || '|'
        || coalesce(NEW.doctor_id::text, none) || '|'
        || to_char(bucket_start, 'YYYYMMDDHH24MI') || '|'
        || (CASE WHEN v_walkin THEN 'w' ELSE 'r' END),
        0);
    PERFORM pg_advisory_xact_lock(lock_key);

    live_count := public.slot_seats_used(
        NEW.clinic_id, NEW.doctor_id, bucket_start, bucket_end,
        v_walkin, NEW.id);

    IF live_count >= cap THEN
        RAISE EXCEPTION
            'Khung giờ đã đầy: tối đa % chỗ % cho bác sĩ này trong khung % phút.',
            cap,
            CASE WHEN v_walkin THEN 'vãng lai' ELSE 'lịch hẹn' END,
            v_minutes
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.enforce_slot_capacity() IS
  'Trần số chỗ mỗi khung mỗi bác sĩ. Đếm bằng slot_seats_used() — ghế vãng lai '
  'tính cả khách có hẹn đến muộn. Bỏ qua khi dòng đã giữ ghế từ trước '
  '(20260807000001).';

-- Trigger đã gắn ở 20260803000010; CREATE OR REPLACE FUNCTION ở trên là đủ.
-- Vẫn khẳng định lại để migration này tự đứng được trên một database trần.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
         WHERE tgrelid = 'public.appointment'::regclass
           AND tgname = 'trg_enforce_slot_capacity'
    ) THEN
        RAISE EXCEPTION 'trg_enforce_slot_capacity chưa gắn — dừng lại.';
    END IF;
END $$;
