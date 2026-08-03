-- Luật sức chứa của phòng khám mịn tới KHUNG 15 PHÚT. Bảng thì mịn tới GIỜ.
--
-- LUẬT KHÁCH HÀNG NÊU (Notion — "Tiêu chí của phòng khám theo bộ phận" → CSKH):
--
--                18:00      18:15     18:30     18:45+
--     BS Thành   10 ca      4 ca      4 ca      4 ca
--     BS khác     3 ca      4 ca      5 ca      3 ca
--
-- Bốn con số khác nhau bên trong MỘT giờ. slot_booking_override chỉ có
-- hour_start/hour_end (smallint 0–23), nên nó không thể ghi lại điều đó — không
-- phải "chưa ai nhập", mà là không có chỗ để nhập. Ba dòng override đang có
-- trên prod đều là `18 → 19`, một con số cho cả tiếng.
--
-- VÀ BA DÒNG ẤY CHỒNG LẤN NHAU. Cùng bác sĩ, cùng 18→19; hai dòng trùng hệt
-- nhau (tạo cách nhau 6 phút), dòng thứ ba phủ 03–09/08 với walkin_cap khác.
-- Resolver cũ sắp `ORDER BY date_start DESC LIMIT 1`, mà cả ba cùng date_start
-- ⇒ Postgres chọn dòng nào là KHÔNG XÁC ĐỊNH. Sức chứa thật của khung 18h hôm
-- nay phụ thuộc vào thứ tự đọc trang đĩa.
--
-- Migration này làm ba việc, và việc thứ ba mới là việc quan trọng:
--   1. đổi độ mịn sang PHÚT-TRONG-NGÀY;
--   2. dọn các dòng đang chồng lấn;
--   3. làm cho chồng lấn KHÔNG THỂ XẢY RA NỮA (ràng buộc EXCLUDE).
--
-- Sửa (1) mà không có (3) chỉ đổi một luật mơ hồ theo giờ thành một luật mơ hồ
-- theo phút.

-- ---------------------------------------------------------------------------
-- 1. Phút-trong-ngày thay cho giờ
-- ---------------------------------------------------------------------------
-- 0..1440, nửa mở [start, end) — cùng quy ước với hour_start/hour_end cũ, nên
-- backfill là phép nhân, không mất mát gì.

ALTER TABLE public.slot_booking_override
    ADD COLUMN IF NOT EXISTS minute_start integer,
    ADD COLUMN IF NOT EXISTS minute_end   integer;

UPDATE public.slot_booking_override
   SET minute_start = hour_start * 60,
       minute_end   = hour_end   * 60
 WHERE minute_start IS NULL;

-- ---------------------------------------------------------------------------
-- 2. Dọn chồng lấn TRƯỚC khi cấm nó
-- ---------------------------------------------------------------------------
-- Giữ dòng MỚI NHẤT trong mỗi nhóm chồng lấn: nó là ý định gần đây nhất của
-- người vận hành. Các dòng bị bỏ được ghi vào event_log — một luật sức chứa
-- biến mất không dấu vết là thứ không được phép, kể cả khi nó đang mâu thuẫn.
--
-- Lặp cho tới khi hết: bỏ một dòng có thể làm hai dòng còn lại thôi chồng nhau,
-- nên một lượt quét không đủ.

DO $dedupe$
DECLARE
    v_removed int := 0;
    v_round   int := 0;
    v_id      uuid;
BEGIN
    LOOP
        v_round := v_round + 1;
        EXIT WHEN v_round > 50;  -- chặn vòng lặp vô hạn nếu logic sai

        SELECT a.id INTO v_id
          FROM public.slot_booking_override a
          JOIN public.slot_booking_override b
            ON b.id <> a.id
           AND b.clinic_id = a.clinic_id
           AND coalesce(b.doctor_id, '00000000-0000-0000-0000-000000000000'::uuid)
             = coalesce(a.doctor_id, '00000000-0000-0000-0000-000000000000'::uuid)
           AND daterange(b.date_start, b.date_end, '[]')
            && daterange(a.date_start, a.date_end, '[]')
           AND int4range(b.minute_start, b.minute_end)
            && int4range(a.minute_start, a.minute_end)
           -- Bỏ dòng CŨ hơn: b mới hơn a.
           AND (b.created_at, b.id) > (a.created_at, a.id)
         LIMIT 1;

        EXIT WHEN v_id IS NULL;

        INSERT INTO public.event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        SELECT s.clinic_id,
               'booking_override.slot_superseded',
               'booking_override',
               s.id::text,
               jsonb_build_object(
                   'doctor_id',    s.doctor_id,
                   'date_start',   s.date_start,
                   'date_end',     s.date_end,
                   'minute_start', s.minute_start,
                   'minute_end',   s.minute_end,
                   'regular_cap',  s.regular_cap,
                   'walkin_cap',   s.walkin_cap,
                   'reason',       s.reason,
                   'why_removed',  'chồng lấn với một override mới hơn; '
                                   'trước đây luật nào thắng là không xác định'
               ),
               jsonb_build_object('origin', 'migration:20260803000009'),
               'migration:20260803000009',
               FALSE
          FROM public.slot_booking_override s
         WHERE s.id = v_id;

        DELETE FROM public.slot_booking_override WHERE id = v_id;
        v_removed := v_removed + 1;
    END LOOP;

    RAISE NOTICE 'slot_booking_override: gỡ % dòng chồng lấn', v_removed;
END
$dedupe$;

-- ---------------------------------------------------------------------------
-- 3. Ràng buộc + bỏ cột giờ
-- ---------------------------------------------------------------------------

ALTER TABLE public.slot_booking_override
    ALTER COLUMN minute_start SET NOT NULL,
    ALTER COLUMN minute_end   SET NOT NULL;

ALTER TABLE public.slot_booking_override
    DROP CONSTRAINT IF EXISTS slot_override_hour_range;
ALTER TABLE public.slot_booking_override
    DROP CONSTRAINT IF EXISTS slot_override_minute_range;
ALTER TABLE public.slot_booking_override
    ADD CONSTRAINT slot_override_minute_range
    CHECK (minute_start BETWEEN 0 AND 1439
       AND minute_end   BETWEEN 1 AND 1440
       AND minute_end > minute_start
       -- Bội số 5: lưới khung giờ chia hết 60 (5/10/15/20/30/60), nên một mốc
       -- không phải bội số 5 chắc chắn cắt ngang một khung và tạo ra vùng mà
       -- không luật nào phủ.
       AND minute_start % 5 = 0
       AND minute_end   % 5 = 0);

-- KHÔNG CÓ HAI LUẬT CHO CÙNG MỘT KHUNG. Đây là phần khiến "tự tránh mọi ngoại
-- lệ" thành sự thật của database chứ không phải kỷ luật của người nhập:
-- INSERT chồng lấn sẽ bị TỪ CHỐI ngay, thay vì được nhận rồi để resolver bốc
-- thăm lúc đọc.
--
-- coalesce(doctor_id, …0): NULL không bằng NULL trong toán tử `=`, nên hai luật
-- "mọi bác sĩ" chồng nhau sẽ lọt lưới nếu so trực tiếp. Quy NULL về một UUID
-- canh chừng để chúng nằm chung một nhóm.
--
-- Luật RIÊNG cho một bác sĩ VẪN được phép chồng lên luật "mọi bác sĩ" — đó là
-- ngoại lệ hợp lệ, và resolver xử lý bằng thứ tự ưu tiên rõ ràng bên dưới.
ALTER TABLE public.slot_booking_override
    DROP CONSTRAINT IF EXISTS slot_override_no_overlap;
ALTER TABLE public.slot_booking_override
    ADD CONSTRAINT slot_override_no_overlap
    EXCLUDE USING gist (
        clinic_id WITH =,
        (coalesce(doctor_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        daterange(date_start, date_end, '[]') WITH &&,
        int4range(minute_start, minute_end) WITH &&
    );

ALTER TABLE public.slot_booking_override
    DROP COLUMN IF EXISTS hour_start,
    DROP COLUMN IF EXISTS hour_end;

DROP INDEX IF EXISTS idx_slot_override_lookup;
CREATE INDEX IF NOT EXISTS idx_slot_override_lookup
    ON public.slot_booking_override
       (clinic_id, date_start, date_end, minute_start, minute_end);

COMMENT ON TABLE public.slot_booking_override IS
  'C.4 Tầng 3: ngoại lệ sức chứa theo (bác sĩ × khoảng ngày × khoảng PHÚT). '
  'Độ mịn phút chứ không phải giờ, vì luật phòng khám khác nhau giữa 18:00 và '
  '18:15. doctor_id NULL = áp cho mọi bác sĩ. Ràng buộc EXCLUDE cấm hai luật '
  'cùng phủ một khung — không có "luật nào thắng", chỉ có một luật.';

COMMENT ON COLUMN public.slot_booking_override.minute_start IS
  'Phút-trong-ngày (giờ VN), 0..1439. Nửa mở [minute_start, minute_end).';

-- ---------------------------------------------------------------------------
-- 4. Resolver: khớp theo phút, và thứ tự ưu tiên KHÔNG còn phụ thuộc may rủi
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
    v_local   timestamp;
    v_date    date;
    v_minute  integer;
    v_weekday smallint;
    v_slot    record;
    v_doc     record;
    v_clinic  record;
BEGIN
    v_local   := p_slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh';
    v_date    := v_local::date;
    -- Phút-trong-ngày của MỐC BẮT ĐẦU khung. Một khung thuộc về luật nào là do
    -- điểm bắt đầu của nó quyết định — không cần override trùng khít biên khung,
    -- và không có khung nào rơi vào hai luật.
    v_minute  := EXTRACT(HOUR FROM v_local)::int * 60
               + EXTRACT(MINUTE FROM v_local)::int;
    v_weekday := EXTRACT(DOW FROM v_local)::smallint;

    -- Tầng 3. Ràng buộc EXCLUDE bảo đảm tối đa MỘT dòng cho mỗi nhóm
    -- (bác sĩ cụ thể / mọi bác sĩ), nên `doctor_id IS NULL` ở ORDER BY là thứ
    -- tự ưu tiên thật sự, không phải cách phá thế hoà như trước.
    SELECT s.regular_cap, s.walkin_cap
      INTO v_slot
      FROM public.slot_booking_override s
     WHERE s.clinic_id = p_clinic_id
       AND (s.doctor_id = p_doctor_id OR s.doctor_id IS NULL)
       AND v_date BETWEEN s.date_start AND s.date_end
       AND v_minute >= s.minute_start AND v_minute < s.minute_end
     ORDER BY s.doctor_id IS NULL   -- FALSE trước: luật riêng thắng luật chung
     LIMIT 1;

    IF p_doctor_id IS NOT NULL THEN
        SELECT d.slot_minutes, d.regular_cap, d.walkin_cap
          INTO v_doc
          FROM public.doctor_booking_override d
         WHERE d.clinic_id = p_clinic_id
           AND d.doctor_id = p_doctor_id
           AND d.effective_from <= v_date
           AND (d.effective_to IS NULL OR d.effective_to >= v_date)
           AND (d.weekday IS NULL OR d.weekday = v_weekday)
         ORDER BY d.weekday IS NULL,
                  d.effective_from DESC
         LIMIT 1;
    END IF;

    SELECT p.slot_minutes, p.regular_cap, p.walkin_cap
      INTO v_clinic
      FROM public.clinic_booking_policy(p_clinic_id) p;

    RETURN QUERY SELECT
        coalesce(v_doc.slot_minutes, v_clinic.slot_minutes),
        coalesce(v_slot.regular_cap, v_doc.regular_cap, v_clinic.regular_cap),
        coalesce(v_slot.walkin_cap,  v_doc.walkin_cap,  v_clinic.walkin_cap);
END;
$function$;

COMMENT ON FUNCTION public.resolve_effective_cap(uuid, uuid, timestamptz) IS
  'C.4: sức chứa hiệu lực, 3 tầng — slot_override (mịn tới phút) -> '
  'doctor_override -> clinic_booking_policy. Khung thuộc luật nào là do mốc '
  'BẮT ĐẦU của nó quyết định; EXCLUDE bảo đảm không quá một luật khớp.';
