-- C.3 — luật giờ khám thành cấu hình của từng phòng khám.
--
-- "Mỗi bác sĩ × khung 15 phút có 3 chỗ: 2 đặt trước + 1 vãng lai" là luật của
-- Dr4Women, không phải luật của y khoa. Nó đang được viết cứng ở BA nơi, bằng
-- ba ngôn ngữ khác nhau:
--
--   booking_service.py:47-49      SLOT_MINUTES / REGULAR_CAP / WALKIN_CAP
--   lib/slot-capacity.ts:9-13     SLOT_MIN / REGULAR_CAP / WALKIN_CAP
--   20260731000002:81-84          floor(epoch / 900), CASE WHEN walkin THEN 1 ELSE 2
--
-- Phòng khám thứ hai dùng khung 30 phút thì không dùng được sản phẩm, và cách
-- sửa "nhanh" là sửa ba chỗ rồi deploy lại cho tất cả mọi người — tức là phòng
-- khám #1 cũng đổi theo. Từ migration này, ba con số nằm ở clinic.settings và
-- người ĐẾM là hàm này; sửa cho một phòng khám là một lần UPDATE, không deploy.
--
-- Vì sao có CHECK constraint chứ không chỉ đọc cẩn thận: cái giá của một giá trị
-- sai không trả ở lúc ghi mà ở 8 giờ sáng ngày khám, khi lễ tân không đặt được
-- lịch nào và không ai biết tại sao. Chặn ở lúc ghi thì người sai là người sửa.

-- ---------------------------------------------------------------------------
-- 1. Validator — dùng cho CHECK, nên phải IMMUTABLE
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.clinic_policy_int_ok(
    p_obj jsonb, p_key text, p_min integer, p_max integer
)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
AS $function$
DECLARE
    v jsonb := p_obj -> p_key;
BEGIN
    -- Vắng mặt là hợp lệ: phòng khám chỉ khai cái nó muốn khác mặc định.
    IF v IS NULL OR jsonb_typeof(v) = 'null' THEN
        RETURN true;
    END IF;
    -- '15' (chuỗi) trông giống 15 trong Postgres nhưng không giống trong
    -- JavaScript. Chặn ở đây để hai bên đọc ra cùng một thứ.
    IF jsonb_typeof(v) <> 'number' THEN
        RETURN false;
    END IF;
    IF (p_obj ->> p_key)::numeric <> floor((p_obj ->> p_key)::numeric) THEN
        RETURN false;
    END IF;
    RETURN (p_obj ->> p_key)::numeric BETWEEN p_min AND p_max;
END
$function$;

CREATE OR REPLACE FUNCTION public.clinic_booking_policy_is_valid(p_settings jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
AS $function$
DECLARE
    booking jsonb;
    minutes integer;
BEGIN
    booking := p_settings -> 'booking';
    IF booking IS NULL OR jsonb_typeof(booking) = 'null' THEN
        RETURN true;
    END IF;
    IF jsonb_typeof(booking) <> 'object' THEN
        RETURN false;
    END IF;

    -- Trần 100 không phải để dạy phòng khám cách làm việc. Nó để bắt cái lỗi
    -- gõ nhầm ô: 200 ở ô "số chỗ mỗi khung" gần như luôn là số khác bị dán vào.
    IF NOT public.clinic_policy_int_ok(booking, 'slot_minutes', 1, 60) THEN
        RETURN false;
    END IF;
    IF NOT public.clinic_policy_int_ok(booking, 'regular_cap', 1, 100) THEN
        RETURN false;
    END IF;
    IF NOT public.clinic_policy_int_ok(booking, 'walkin_cap', 0, 100) THEN
        RETURN false;
    END IF;

    -- Khung được cắt bằng cách làm tròn xuống trên epoch UTC. Việt Nam lệch một
    -- số giờ chẵn, nên lưới UTC trùng lưới giờ địa phương KHI VÀ CHỈ KHI độ dài
    -- khung chia hết 60 phút. Khung 45 phút sẽ trượt dần qua từng giờ và ô lễ
    -- tân nhìn thấy không còn là ô database đếm.
    minutes := (booking ->> 'slot_minutes')::integer;
    IF minutes IS NOT NULL AND 60 % minutes <> 0 THEN
        RETURN false;
    END IF;

    RETURN true;
END
$function$;

COMMENT ON FUNCTION public.clinic_booking_policy_is_valid(jsonb) IS
  'CHECK cho clinic.settings->booking: số nguyên, trong khoảng, và khung chia hết 60.';

-- ---------------------------------------------------------------------------
-- 2. Điền cho các phòng khám đang có, rồi mới khoá bằng CHECK
-- ---------------------------------------------------------------------------
--
-- Ghi hẳn ba con số ra thay vì để trống và dựa vào mặc định: sau bước này,
-- "phòng khám này chạy khung mấy phút" trả lời được bằng một câu SELECT, không
-- phải bằng cách đọc mã nguồn của ba service.

UPDATE public.clinic
   SET settings = jsonb_set(
           settings,
           '{booking}',
           coalesce(settings -> 'booking', '{}'::jsonb)
             || jsonb_build_object(
                  'slot_minutes',
                  coalesce(settings #> '{booking,slot_minutes}', to_jsonb(15)),
                  'regular_cap',
                  coalesce(settings #> '{booking,regular_cap}', to_jsonb(2)),
                  'walkin_cap',
                  coalesce(settings #> '{booking,walkin_cap}', to_jsonb(1))
                ),
           true
       )
 WHERE NOT (settings -> 'booking' ?& ARRAY['slot_minutes', 'regular_cap', 'walkin_cap'])
    OR settings -> 'booking' IS NULL;

ALTER TABLE public.clinic
    ALTER COLUMN settings
    SET DEFAULT '{"booking": {"slot_minutes": 15, "regular_cap": 2, "walkin_cap": 1}}'::jsonb;

ALTER TABLE public.clinic
    DROP CONSTRAINT IF EXISTS clinic_booking_policy_valid;
ALTER TABLE public.clinic
    ADD CONSTRAINT clinic_booking_policy_valid
    CHECK (public.clinic_booking_policy_is_valid(settings));

-- ---------------------------------------------------------------------------
-- 3. Người đọc — một hàm, ba người gọi
-- ---------------------------------------------------------------------------
--
-- SECURITY DEFINER vì trigger enforce_slot_capacity chạy dưới quyền người gọi,
-- và người gọi không cần (không nên) đọc được clinic.settings — A.5 đã bỏ
-- `settings` khỏi GRANT cho `authenticated` đúng vì lý do đó.
--
-- Luôn trả đúng 1 hàng, kể cả khi clinic_id không tồn tại: subquery vô hướng
-- trả NULL rồi coalesce đỡ. Một trigger im lặng bỏ qua vì SELECT ... INTO không
-- tìm thấy hàng nào là cách tệ nhất để mất một hàng rào an toàn.

CREATE OR REPLACE FUNCTION public.clinic_booking_policy(p_clinic_id uuid)
RETURNS TABLE (slot_minutes integer, regular_cap integer, walkin_cap integer)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
    SELECT coalesce((b ->> 'slot_minutes')::integer, 15),
           coalesce((b ->> 'regular_cap')::integer, 2),
           coalesce((b ->> 'walkin_cap')::integer, 1)
      FROM (
            SELECT (SELECT c.settings -> 'booking'
                      FROM public.clinic AS c
                     WHERE c.id = p_clinic_id) AS b
           ) AS s;
$function$;

COMMENT ON FUNCTION public.clinic_booking_policy(uuid) IS
  'Luật đặt lịch của một phòng khám (C.3). Nguồn duy nhất cho cả trigger lẫn '
  'clinic_policy.py. Thiếu cấu hình thì trả mặc định 15/2/1 của Dr4Women.';

-- ---------------------------------------------------------------------------
-- 4. Enforcer thật sự — CAP-01, giờ đọc luật thay vì mang sẵn luật
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.enforce_slot_capacity()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    dead         text[] := ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'];
    none         text   := '~none~';   -- sentinel for a NULL (unassigned) doctor
    bucket_start timestamptz;
    bucket_end   timestamptz;
    v_walkin     boolean;
    v_minutes    integer;
    v_seconds    integer;
    cap          integer;
    live_count   integer;
    lock_key     bigint;
BEGIN
    -- A dead booking never holds a seat.
    IF NEW.status = ANY (dead) THEN
        RETURN NEW;
    END IF;

    v_walkin := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';

    SELECT p.slot_minutes,
           CASE WHEN v_walkin THEN p.walkin_cap ELSE p.regular_cap END
      INTO v_minutes, cap
      FROM public.clinic_booking_policy(NEW.clinic_id) AS p;

    -- Bucket floored on the UTC epoch; length now comes from the clinic.
    v_seconds    := v_minutes * 60;
    bucket_start := to_timestamp(
        floor(extract(epoch FROM NEW.slot_start) / v_seconds) * v_seconds);
    bucket_end   := bucket_start + make_interval(mins => v_minutes);

    -- Serialize concurrent bookings for the SAME (clinic, doctor, bucket, kind).
    -- The clinic belongs in the key for the same reason it belongs in the count
    -- below: two clinics booking at 09:00 are not competing for anything.
    lock_key := hashtextextended(
        NEW.clinic_id::text || '|'
        || coalesce(NEW.doctor_id::text, none) || '|'
        || to_char(bucket_start, 'YYYYMMDDHH24MI') || '|'
        || (CASE WHEN v_walkin THEN 'w' ELSE 'r' END),
        0);
    PERFORM pg_advisory_xact_lock(lock_key);

    SELECT count(*) INTO live_count
    FROM public.appointment a
    WHERE a.id <> NEW.id
      AND a.clinic_id = NEW.clinic_id
      AND coalesce(a.doctor_id::text, none) = coalesce(NEW.doctor_id::text, none)
      AND a.slot_start >= bucket_start
      AND a.slot_start <  bucket_end
      AND NOT (a.status = ANY (dead))
      AND (upper(coalesce(a.booking_channel, '')) = 'WALK_IN') = v_walkin;

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
  'CAP-01 per (clinic, doctor, bucket, walk-in/booked). Độ dài khung và số chỗ '
  'đọc từ clinic_booking_policy(clinic_id), không viết cứng.';
