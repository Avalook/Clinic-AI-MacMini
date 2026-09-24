-- SỐ BOOKING — cấp NGAY LÚC ĐẶT (Tuyền chốt 23/09/2026, luồng chuẩn bước 4):
-- "khi khách đặt online thì lập tức có 1 số thứ tự booking theo thời gian thực,
-- khi đến phòng khám thì số này được đứng cạnh số check-in của khách".
--
-- Ba con số, ba việc:
--   · `so_booking`  — thứ tự ĐẶT LỊCH trong ngày hẹn, cả phòng khám. Cấp lúc
--                     tạo lịch (mới).
--   · `so_tiep_don` — số quầy gọi, theo thứ tự CHECK-IN (20260917000009).
--   · `queue_number`— số riêng từng bác sĩ ở hàng chờ phòng khám.
--
-- Đánh số theo NGÀY HẸN: khách hẹn ngày 25 nhận số 1, 2, 3… theo thứ tự ai đặt
-- trước. Đổi lịch sang NGÀY KHÁC thì nhận số mới của ngày ấy (số cũ không tái
-- dùng, để hai khách không cùng một số trong một ngày). Đổi giờ trong cùng ngày
-- giữ nguyên số. Huỷ giữ nguyên số — số đã báo khách thì không cấp lại.
--
-- Cấp bằng trigger BEFORE để MỌI đường tạo lịch (CSKH, vãng lai, đặt từ lượt
-- trước, ghi thẳng) đều có số, không cần sửa từng đường. Khoá advisory theo
-- (phòng khám, ngày) để hai người đặt cùng lúc không ra trùng số.

ALTER TABLE public.appointment ADD COLUMN IF NOT EXISTS so_booking integer;

COMMENT ON COLUMN public.appointment.so_booking IS
'Số thứ tự đặt lịch trong ngày hẹn (cả phòng khám), cấp lúc tạo lịch. Khác so_tiep_don (cấp lúc check-in).';

CREATE OR REPLACE FUNCTION public.cap_so_booking()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    ngay date;
BEGIN
    ngay := (NEW.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    IF TG_OP = 'INSERT' THEN
        IF NEW.so_booking IS NOT NULL THEN
            RETURN NEW;
        END IF;
    ELSIF (OLD.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = ngay
          AND NEW.so_booking IS NOT NULL THEN
        -- Đổi giờ trong cùng ngày: giữ số.
        RETURN NEW;
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            'clinicai:booking:' || NEW.clinic_id::text || ':' || ngay::text, 0
        )
    );

    SELECT coalesce(max(a.so_booking), 0) + 1
      INTO NEW.so_booking
      FROM public.appointment AS a
     WHERE a.clinic_id = NEW.clinic_id
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = ngay
       AND a.id <> NEW.id;

    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_cap_so_booking ON public.appointment;
CREATE TRIGGER trg_cap_so_booking
    BEFORE INSERT OR UPDATE OF slot_start ON public.appointment
    FOR EACH ROW EXECUTE FUNCTION public.cap_so_booking();

-- Lịch từ HÔM NAY trở đi đã có trước bản này: cấp theo thứ tự đặt (created_at).
-- Lịch đã qua không cần số. Chạy lại không đổi số đã cấp (chỉ dòng còn trống).
WITH thu_tu AS (
    SELECT a.id,
           coalesce((
               SELECT max(b.so_booking)
                 FROM public.appointment b
                WHERE b.clinic_id = a.clinic_id
                  AND (b.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                      = (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           ), 0)
           + row_number() OVER (
               PARTITION BY a.clinic_id,
                            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               ORDER BY a.created_at, a.id
           ) AS so
      FROM public.appointment a
     WHERE a.so_booking IS NULL
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           >= (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
)
UPDATE public.appointment a
   SET so_booking = t.so
  FROM thu_tu t
 WHERE a.id = t.id;
