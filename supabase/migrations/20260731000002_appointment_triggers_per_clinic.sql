-- Two more appointment functions that counted across every clinic.
--
-- 20260731000001 scoped check_in_appointment(). Reading the neighbouring
-- functions in pg_proc turned up two more with the same shape. Both fire on
-- every appointment write, and both are reached from the backend, which
-- connects as the database owner (bypassrls = true) — so RLS never narrows what
-- they see, whatever their SECURITY setting says.
--
--   assign_appointment_queue_number  (SECURITY DEFINER trigger)
--       The same cross-clinic max(queue_number) that check_in_appointment had.
--       Fixing one and not the other left the bug reachable by the other path:
--       this trigger numbers a walk-in that is inserted already CHECKED_IN,
--       which is exactly how the front desk registers someone at the counter.
--
--   enforce_slot_capacity  (the 2+1 rule, CAP-01)
--       Counted live bookings in the 15-minute bucket matching on doctor_id
--       alone. A NULL doctor collapses to one sentinel, so EVERY clinic's
--       unassigned bookings shared a single bucket: clinic A taking its two
--       09:00 slots would tell clinic B "khung giờ đã đầy" for a doctor clinic B
--       has never heard of. The advisory lock had the same shape, so the two
--       clinics also serialised against each other.
--
-- Capacity and queue position are properties of one clinic's day. Neither says
-- anything about another clinic's.

CREATE OR REPLACE FUNCTION public.assign_appointment_queue_number()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    clinic_day date;
    next_number integer;
BEGIN
    IF NEW.status <> 'CHECKED_IN'
       OR nullif(pg_catalog.btrim(NEW.queue_number), '') IS NOT NULL THEN
        RETURN NEW;
    END IF;

    clinic_day := (NEW.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            'clinicai:queue:' || NEW.clinic_id::text || ':' || clinic_day::text, 0
        )
    );

    SELECT coalesce(max(a.queue_number::integer), 0) + 1
      INTO next_number
      FROM public.appointment AS a
     WHERE a.clinic_id = NEW.clinic_id
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = clinic_day
       AND a.queue_number ~ '^[0-9]+$'
       AND a.id IS DISTINCT FROM NEW.id;

    NEW.queue_number := next_number::text;
    RETURN NEW;
END
$function$;

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
    cap          integer;
    live_count   integer;
    lock_key     bigint;
BEGIN
    -- A dead booking never holds a seat.
    IF NEW.status = ANY (dead) THEN
        RETURN NEW;
    END IF;

    -- 15-minute bucket, UTC-floored (matches lib/slot-capacity.ts).
    bucket_start := to_timestamp(floor(extract(epoch FROM NEW.slot_start) / 900) * 900);
    bucket_end   := bucket_start + interval '15 minutes';
    v_walkin     := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';
    cap          := CASE WHEN v_walkin THEN 1 ELSE 2 END;

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
            'Khung giờ đã đầy: tối đa % chỗ % cho bác sĩ này trong khung 15 phút.',
            cap, CASE WHEN v_walkin THEN 'vãng lai' ELSE 'lịch hẹn' END
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.assign_appointment_queue_number() IS
  'Assigns the next queue number for that clinic and day when a row lands '
  'already CHECKED_IN (walk-in registered at the counter).';
COMMENT ON FUNCTION public.enforce_slot_capacity() IS
  'CAP-01 2+1 per (clinic, doctor, 15-minute bucket, walk-in/booked).';
