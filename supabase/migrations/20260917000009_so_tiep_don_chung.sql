-- SỐ TIẾP ĐÓN CHUNG CỦA QUẦY (Tuyền chốt 17/09/2026): "là số chung, khi nào vào
-- quầy bác sĩ nào thì lại số riêng sau".
--
-- Hai con số, hai việc:
--   · `so_tiep_don` — số lễ tân gọi ở quầy, MỘT dãy cho cả cơ sở trong ngày,
--     theo thứ tự check-in. Cấp đúng lúc lịch chuyển sang CHECKED_IN.
--   · `queue_number` — số riêng của từng bác sĩ (20260812000001), dùng ở hàng
--     chờ phòng khám. Không đổi.
--
-- Cấp bằng trigger BEFORE (INSERT OR UPDATE) thay vì sửa `check_in_appointment`:
-- mọi đường chuyển sang CHECKED_IN (nút Check-in, vãng lai tự check-in, ghi
-- thẳng) đều đi qua đây. Khoá advisory theo đúng phạm vi đánh số (phòng khám,
-- cơ sở, ngày) để hai quầy bấm cùng lúc không ra trùng số. Hoàn tác check-in
-- giữ nguyên số đã cấp — số đã gọi thì không tái sử dụng.

ALTER TABLE public.appointment ADD COLUMN IF NOT EXISTS so_tiep_don integer;

COMMENT ON COLUMN public.appointment.so_tiep_don IS
'Số tiếp đón chung của quầy trong ngày (theo cơ sở), cấp lúc check-in. Số riêng theo bác sĩ là queue_number.';

CREATE OR REPLACE FUNCTION public.cap_so_tiep_don()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    ngay date;
    co_so text;
BEGIN
    IF NEW.status <> 'CHECKED_IN' OR NEW.so_tiep_don IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'CHECKED_IN' THEN
        RETURN NEW;
    END IF;

    ngay := (NEW.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    co_so := coalesce(NEW.location_id::text, '~none~');

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            'clinicai:tiep-don:' || NEW.clinic_id::text || ':' || co_so
            || ':' || ngay::text, 0
        )
    );

    SELECT coalesce(max(a.so_tiep_don), 0) + 1
      INTO NEW.so_tiep_don
      FROM public.appointment AS a
     WHERE a.clinic_id = NEW.clinic_id
       AND coalesce(a.location_id::text, '~none~') = co_so
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = ngay
       AND a.id <> NEW.id;

    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_cap_so_tiep_don ON public.appointment;
CREATE TRIGGER trg_cap_so_tiep_don
    BEFORE INSERT OR UPDATE OF status ON public.appointment
    FOR EACH ROW EXECUTE FUNCTION public.cap_so_tiep_don();

-- Lịch ĐÃ check-in hôm nay trước bản này: cấp theo giờ check-in của lượt khám.
WITH thu_tu AS (
    SELECT a.id,
           row_number() OVER (
               PARTITION BY a.clinic_id, a.location_id,
                            (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               ORDER BY coalesce(v.checked_in_at, a.updated_at), a.id
           ) AS so
      FROM public.appointment a
      LEFT JOIN public.visit v ON v.appointment_id = a.id AND v.clinic_id = a.clinic_id
     WHERE a.so_tiep_don IS NULL
       AND a.status IN ('CHECKED_IN', 'COMPLETED')
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
)
UPDATE public.appointment a
   SET so_tiep_don = t.so
  FROM thu_tu t
 WHERE a.id = t.id;
