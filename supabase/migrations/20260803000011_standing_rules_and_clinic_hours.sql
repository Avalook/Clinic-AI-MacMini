-- Hai thứ khiến phòng khám thứ hai không mở được, và khiến Dr4Women vẫn sai.
--
-- (1) LUẬT THƯỜNG TRỰC KHÔNG CÓ CHỖ Ở.
--
-- Luật Dr4Women (Notion → CSKH) là luật ĐỨNG YÊN, không phải ngoại lệ:
--
--                18:00     18:15     18:30     18:45+
--     BS Thành   10 ca     4 ca      4 ca      4 ca
--     BS khác     3 ca     4 ca      5 ca      3 ca
--
-- Ba tầng hiện có không tầng nào nói được nó:
--   Tầng 1  clinic.settings.booking   một số cho cả phòng khám, không có giờ
--   Tầng 2  doctor_booking_override   có weekday, KHÔNG có khoảng phút, và
--                                     doctor_id NOT NULL nên không nói được
--                                     "các bác sĩ khác"
--   Tầng 3  slot_booking_override     có khoảng phút, nhưng bắt buộc khoảng
--                                     NGÀY và trần 90 ngày — nó là ngoại lệ
--                                     tạm thời, đúng như thiết kế của nó
--
-- Hệ quả: luật chính của phòng khám phải nhập lại mỗi 90 ngày, mãi mãi. Quên
-- một lần thì sức chứa ÂM THẦM rơi về mặc định — không lỗi, không cảnh báo.
--
-- KHÔNG THÊM TẦNG THỨ TƯ. Tầng 2 chỉ thiếu đúng hai thứ mà tầng 3 đã có: cho
-- phép doctor_id NULL, và một khoảng phút. Thêm vào là bảng Notion ở trên thành
-- sáu dòng vĩnh viễn, còn tầng 3 quay về đúng việc của nó ("hôm nay BS bận,
-- giảm còn 2").
--
-- (2) GIỜ MỞ CỬA NẰM TRONG MÃ, Ở HAI CHỖ, VỚI HAI GIÁ TRỊ KHÁC NHAU.
--
--     BookingHub.tsx:120   T2–T6 17:00–22:00   ← lưới đặt lịch
--     lib/roster.ts:153    T2–T6 17:00–23:00   ← đăng ký ca trực
--
-- Đây không phải chuyện của phòng khám thứ hai. NGAY BÂY GIỜ bác sĩ đăng ký
-- được ca 22:00–23:00 mà CSKH không đặt lịch vào được: một tiếng mỗi tối biến
-- mất giữa hai file. Và chừng nào giờ mở cửa còn là hằng số trong bundle thì
-- phòng khám thứ hai không thể có giờ khác — đó là chốt chặn thật sự duy nhất
-- của việc đa phòng khám.

-- ---------------------------------------------------------------------------
-- 1. Tầng 2 trở thành tầng LUẬT THƯỜNG TRỰC
-- ---------------------------------------------------------------------------

ALTER TABLE public.doctor_booking_override
    ALTER COLUMN doctor_id DROP NOT NULL;

ALTER TABLE public.doctor_booking_override
    ADD COLUMN IF NOT EXISTS minute_start integer,
    ADD COLUMN IF NOT EXISTS minute_end   integer;

COMMENT ON COLUMN public.doctor_booking_override.doctor_id IS
    'NULL = áp cho MỌI bác sĩ. Luật riêng của một bác sĩ đè lên luật chung — '
    'cùng quy tắc ưu tiên với slot_booking_override.';
COMMENT ON COLUMN public.doctor_booking_override.minute_start IS
    'Phút-trong-ngày (giờ VN). NULL = áp cho cả ngày. Nửa mở [start, end).';

ALTER TABLE public.doctor_booking_override
    DROP CONSTRAINT IF EXISTS doctor_override_minute_range;
ALTER TABLE public.doctor_booking_override
    ADD CONSTRAINT doctor_override_minute_range
    CHECK (
        -- Cả hai NULL (cả ngày) hoặc cả hai có giá trị. Một nửa khoảng là một
        -- luật không đọc được.
        (minute_start IS NULL) = (minute_end IS NULL)
        AND (minute_start IS NULL OR (
                minute_start BETWEEN 0 AND 1439
            AND minute_end   BETWEEN 1 AND 1440
            AND minute_end > minute_start
            AND minute_start % 5 = 0
            AND minute_end   % 5 = 0))
    );

-- UNIQUE cũ (clinic, doctor, weekday, effective_from) hỏng theo hai đường khi
-- doctor_id thành nullable: NULL không bằng NULL nên hai luật "mọi bác sĩ"
-- trùng nhau lọt lưới, và nó không biết gì về khoảng phút.
--
-- Thay bằng EXCLUDE — cùng lý do như slot_booking_override: hai luật cùng phủ
-- một khung thì không phải "luật nào thắng", mà là không có luật nào.
ALTER TABLE public.doctor_booking_override
    DROP CONSTRAINT IF EXISTS doctor_booking_override_clinic_id_doctor_id_weekday_effecti_key;
ALTER TABLE public.doctor_booking_override
    DROP CONSTRAINT IF EXISTS doctor_override_no_overlap;
ALTER TABLE public.doctor_booking_override
    ADD CONSTRAINT doctor_override_no_overlap
    EXCLUDE USING gist (
        clinic_id WITH =,
        (coalesce(doctor_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        (coalesce(weekday, -1)) WITH =,
        daterange(effective_from, effective_to, '[]') WITH &&,
        int4range(coalesce(minute_start, 0), coalesce(minute_end, 1440)) WITH &&
    );

-- ---------------------------------------------------------------------------
-- 2. Giờ mở cửa thành cấu hình của từng phòng khám
-- ---------------------------------------------------------------------------
-- Theo THỨ, không phải "ngày thường / cuối tuần": hai file mã cũ đều giả định
-- cách chia đó, và nó đúng cho Dr4Women chứ không đúng cho mọi phòng khám. Bảy
-- khoá cho bảy thứ nói được mọi lịch, kể cả ngày nghỉ (open = close).
--
-- Giá trị seed lấy theo lib/roster.ts (17:00–23:00 / 08:00–23:00) chứ KHÔNG
-- theo BookingHub (…–22:00): ca trực là thứ đã có dữ liệu thật, còn lưới đặt
-- lịch là thứ vẽ ra. Chọn con số mà thực tế đang chạy.

UPDATE public.clinic
   SET settings = jsonb_set(
           settings, '{hours}',
           '{
              "0": {"open": "08:00", "close": "23:00"},
              "1": {"open": "17:00", "close": "23:00"},
              "2": {"open": "17:00", "close": "23:00"},
              "3": {"open": "17:00", "close": "23:00"},
              "4": {"open": "17:00", "close": "23:00"},
              "5": {"open": "17:00", "close": "23:00"},
              "6": {"open": "08:00", "close": "23:00"}
            }'::jsonb,
           true),
       updated_at = now()
 WHERE NOT (settings ? 'hours');

COMMENT ON COLUMN public.clinic.settings IS
    'Cấu hình phòng khám. Khoá: booking (slot_minutes/regular_cap/walkin_cap), '
    'hours (giờ mở cửa theo thứ 0=CN..6=T7), display (bảng TV), feature_mode. '
    'hours chuyển vào đây ở 20260803000011 — trước đó nó là hằng số trong mã, '
    'ở hai file, với hai giá trị khác nhau.';

-- Đọc giờ mở cửa của một ngày. Trả về NULL khi phòng khám đóng cửa hôm đó.
CREATE OR REPLACE FUNCTION public.clinic_hours_for_date(
    p_clinic_id uuid,
    p_date date
)
RETURNS TABLE (open_minute integer, close_minute integer)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
    SELECT
        (split_part(h ->> 'open',  ':', 1)::int * 60
       + split_part(h ->> 'open',  ':', 2)::int),
        (split_part(h ->> 'close', ':', 1)::int * 60
       + split_part(h ->> 'close', ':', 2)::int)
      FROM public.clinic c
      CROSS JOIN LATERAL (
          SELECT c.settings #> ARRAY['hours', EXTRACT(DOW FROM p_date)::int::text] AS h
      ) x
     WHERE c.id = p_clinic_id
       AND x.h IS NOT NULL
       AND x.h ->> 'open' <> x.h ->> 'close';
$function$;

COMMENT ON FUNCTION public.clinic_hours_for_date(uuid, date) IS
    'Giờ mở cửa của phòng khám trong một ngày, tính bằng phút-trong-ngày. '
    'Không trả dòng nào = đóng cửa hôm đó (open = close).';

REVOKE ALL ON FUNCTION public.clinic_hours_for_date(uuid, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.clinic_hours_for_date(uuid, date)
    TO authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 3. Resolver đọc thêm khoảng phút ở tầng 2
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.resolve_effective_cap(
    p_clinic_id uuid,
    p_doctor_id uuid,
    p_slot_start timestamptz
)
RETURNS TABLE (slot_minutes integer, regular_cap integer, walkin_cap integer)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_local        timestamp;
    v_date         date;
    v_minute       integer;
    v_weekday      smallint;
    v_slot_regular integer;
    v_slot_walkin  integer;
    v_doc_minutes  integer;
    v_doc_regular  integer;
    v_doc_walkin   integer;
    v_cl_minutes   integer;
    v_cl_regular   integer;
    v_cl_walkin    integer;
BEGIN
    v_local   := p_slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh';
    v_date    := v_local::date;
    v_minute  := EXTRACT(HOUR FROM v_local)::int * 60
               + EXTRACT(MINUTE FROM v_local)::int;
    v_weekday := EXTRACT(DOW FROM v_local)::smallint;

    -- Tầng 3 — ngoại lệ TẠM THỜI (có khoảng ngày, có lý do bắt buộc).
    SELECT s.regular_cap, s.walkin_cap
      INTO v_slot_regular, v_slot_walkin
      FROM public.slot_booking_override s
     WHERE s.clinic_id = p_clinic_id
       AND (s.doctor_id = p_doctor_id OR s.doctor_id IS NULL)
       AND v_date BETWEEN s.date_start AND s.date_end
       AND v_minute >= s.minute_start AND v_minute < s.minute_end
     ORDER BY s.doctor_id IS NULL
     LIMIT 1;

    -- Tầng 2 — luật THƯỜNG TRỰC. Bốn mức cụ-thể-dần, và ORDER BY nói ra thứ tự
    -- đó thay vì để nó phụ thuộc dòng nào được đọc trước:
    --   bác sĩ + thứ  >  bác sĩ  >  thứ  >  mọi lúc
    -- Khoảng phút NULL = cả ngày, nên luật cả-ngày vẫn phủ được phần giờ mà
    -- không luật theo-khung nào chạm tới.
    SELECT d.slot_minutes, d.regular_cap, d.walkin_cap
      INTO v_doc_minutes, v_doc_regular, v_doc_walkin
      FROM public.doctor_booking_override d
     WHERE d.clinic_id = p_clinic_id
       AND (d.doctor_id = p_doctor_id OR d.doctor_id IS NULL)
       AND d.effective_from <= v_date
       AND (d.effective_to IS NULL OR d.effective_to >= v_date)
       AND (d.weekday IS NULL OR d.weekday = v_weekday)
       AND (d.minute_start IS NULL
            OR (v_minute >= d.minute_start AND v_minute < d.minute_end))
     ORDER BY d.doctor_id IS NULL,      -- luật riêng trước luật chung
              d.weekday IS NULL,        -- luật theo thứ trước luật mọi thứ
              d.minute_start IS NULL,   -- luật theo khung trước luật cả ngày
              d.effective_from DESC
     LIMIT 1;

    -- Tầng 1 — mặc định phòng khám.
    SELECT p.slot_minutes, p.regular_cap, p.walkin_cap
      INTO v_cl_minutes, v_cl_regular, v_cl_walkin
      FROM public.clinic_booking_policy(p_clinic_id) p;

    RETURN QUERY SELECT
        coalesce(v_doc_minutes, v_cl_minutes),
        coalesce(v_slot_regular, v_doc_regular, v_cl_regular),
        coalesce(v_slot_walkin,  v_doc_walkin,  v_cl_walkin);
END;
$function$;

COMMENT ON FUNCTION public.resolve_effective_cap(uuid, uuid, timestamptz) IS
  'Sức chứa hiệu lực, 3 tầng: ngoại lệ tạm thời (slot_booking_override) -> '
  'luật thường trực (doctor_booking_override, có khoảng phút từ 20260803000011) '
  '-> mặc định phòng khám. Mỗi tầng chọn dòng CỤ THỂ NHẤT.';

DO $verify$
BEGIN
    PERFORM public.resolve_effective_cap(
        (SELECT id FROM public.clinic LIMIT 1), NULL, now());
    IF NOT EXISTS (SELECT 1 FROM public.clinic WHERE settings ? 'hours') THEN
        RAISE EXCEPTION 'clinic.settings.hours chưa được seed';
    END IF;
    RAISE NOTICE 'luật thường trực + giờ mở cửa: sẵn sàng';
END
$verify$;
