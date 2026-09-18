-- ĐỔI BÁC SĨ CHO KHÁCH ĐÃ CÓ MẶT KHÔNG BỊ TRẦN SỨC CHỨA CHẶN (15/09/2026).
--
-- Tuyền chốt: bác sĩ chính nghỉ giữa chừng thì trưởng ca chuyển lượt cho bác sĩ
-- khác (doi_bac_si_service). Đổi `appointment.doctor_id` của một lịch đã
-- CHECKED_IN làm trigger sức chứa đòi một ghế ở khung của bác sĩ nhận — ở tuần
-- đã công bố mà khung ấy đầy thì việc chuyển giao bị từ chối, trong khi khách
-- đang ngồi trong phòng khám. Bản này miễn kiểm cho lịch đã có mặt.

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

    v_walkin := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';

    -- LỊCH HẸN chưa phân bác sĩ → chưa chiếm ghế của ai → không kiểm.
    -- KHÁCH VÃNG LAI thì vẫn kiểm (20260808000002).
    IF NEW.doctor_id IS NULL AND NOT v_walkin THEN
        RETURN NEW;
    END IF;

    -- LỊCH HẸN vào tuần CHƯA CÔNG BỐ lịch trực → nhận, đối soát lúc công bố.
    IF NOT v_walkin
       AND NOT public.tuan_lich_truc_da_cong_bo(NEW.clinic_id, NEW.slot_start)
    THEN
        RETURN NEW;
    END IF;

    -- KHÁCH ĐÃ CÓ MẶT (CHECKED_IN/COMPLETED) đổi bác sĩ/giờ → không đòi ghế
    -- (20260915000017). Trưởng ca chuyển bác sĩ giữa lượt vì bác sĩ chính nghỉ
    -- không được bị trần của bác sĩ nhận chặn: khách đang ngồi trong phòng
    -- khám, thứ tự khám theo giờ check-in, không phải theo ghế.
    IF TG_OP = 'UPDATE'
       AND NEW.status IN ('CHECKED_IN', 'COMPLETED')
       AND OLD.status = NEW.status
    THEN
        RETURN NEW;
    END IF;

    -- Đã giữ ghế từ trước → không đòi ghế mới → không kiểm.
    IF TG_OP = 'UPDATE'
       AND NOT (OLD.status = ANY (dead))
       AND OLD.slot_start = NEW.slot_start
       AND OLD.doctor_id IS NOT DISTINCT FROM NEW.doctor_id
       AND upper(coalesce(OLD.booking_channel, ''))
           = upper(coalesce(NEW.booking_channel, ''))
    THEN
        RETURN NEW;
    END IF;

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
