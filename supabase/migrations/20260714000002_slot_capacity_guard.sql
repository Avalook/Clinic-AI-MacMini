-- Atomic "2+1 per doctor per 15' slot" booking net (Phase 4, cluster #4).
--
-- Rule (SLOT-21, chốt 2026-07-02): each (doctor, 15-minute bucket) holds at most
--   2 regular appointments (BN1/BN2) + 1 walk-in (booking_channel = 'WALK_IN').
-- Dead statuses (CANCELLED/NO_SHOW/DOCTOR_DECLINED) hold no seat.
--
-- WHY a DB trigger: the app-layer check in the frontend is best-effort/fail-open —
-- two simultaneous requests both pass the count and overbook. The old 6-overlap
-- exclusion constraint was dropped (mig 057), leaving NO hard net. This trigger
-- takes a per-(doctor,bucket,kind) advisory transaction lock so the count-then-check
-- is atomic: concurrent bookings serialize and the cap holds. Authoritative logic
-- lives here (SQL), the frontend only smooths UX.
--
-- CAP-01 (minute-budget) stays advisory by product decision (Quang, 2026-07-03) —
-- not enforced here.

CREATE OR REPLACE FUNCTION public.enforce_slot_capacity() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    dead         text[] := ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'];
    none         text   := '~none~';   -- sentinel for a NULL (unassigned) doctor
    bucket_start timestamptz;
    bucket_end   timestamptz;
    v_walkin    boolean;
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
    v_walkin    := upper(coalesce(NEW.booking_channel, '')) = 'WALK_IN';
    cap          := CASE WHEN v_walkin THEN 1 ELSE 2 END;

    -- Serialize concurrent bookings for the SAME (doctor, bucket, kind).
    lock_key := hashtextextended(
        coalesce(NEW.doctor_id::text, none) || '|'
        || to_char(bucket_start, 'YYYYMMDDHH24MI') || '|'
        || (CASE WHEN v_walkin THEN 'w' ELSE 'r' END),
        0);
    PERFORM pg_advisory_xact_lock(lock_key);

    SELECT count(*) INTO live_count
    FROM public.appointment a
    WHERE a.id <> NEW.id
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
$$;

CREATE TRIGGER trg_enforce_slot_capacity
    BEFORE INSERT OR UPDATE OF slot_start, doctor_id, booking_channel, status
    ON public.appointment
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_slot_capacity();
