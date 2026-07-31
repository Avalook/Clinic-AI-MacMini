-- The daily queue number belongs to one clinic, not to the database.
--
-- check_in_appointment() picked the next number with
--
--     SELECT max(queue_number) + 1 FROM appointment
--      WHERE (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = clinic_day
--
-- with no clinic_id. Demonstrated against the local database: with clinic A
-- already at number 46 today, clinic B's FIRST patient of the day was handed
-- number 47. A queue number is what a receptionist calls across the waiting
-- room; starting the morning at 47 is wrong in a way everyone notices and
-- nobody can explain.
--
-- The advisory lock had the same shape — one lock named
-- 'clinicai:queue:<date>' serialised check-ins across every clinic, so two
-- clinics could not check patients in at the same moment.
--
-- Why the tenant gate did not catch this: scripts/tests/tenant-scope-audit.py
-- reads Python string literals in src/clinicai. SQL living inside a migration
-- is invisible to it, and this is the second real cross-tenant defect found in
-- a place that gate cannot see (the first was AND/OR precedence). The check
-- below is the narrow fix; widening the audit to cover SQL functions is worth
-- doing and is deliberately not bundled here.
--
-- Numbering is per (clinic, day) from now on. Existing rows are untouched: a
-- number already called out to a patient is history, not something to renumber.

CREATE OR REPLACE FUNCTION public.check_in_appointment(
    p_appointment_id uuid,
    p_from_statuses text[]
)
RETURNS TABLE(id uuid, queue_number text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    target public.appointment%ROWTYPE;
    clinic_day date;
    next_number integer;
BEGIN
    SELECT a.*
      INTO target
      FROM public.appointment AS a
     WHERE a.id = p_appointment_id
     FOR UPDATE;

    IF NOT FOUND OR NOT (target.status = ANY (p_from_statuses)) THEN
        RETURN;
    END IF;

    clinic_day := (target.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;

    -- Lock per (clinic, day): two clinics checking patients in at the same
    -- moment are not contending for anything.
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            'clinicai:queue:' || target.clinic_id::text || ':' || clinic_day::text, 0
        )
    );

    IF nullif(pg_catalog.btrim(target.queue_number), '') IS NULL THEN
        SELECT coalesce(max(a.queue_number::integer), 0) + 1
          INTO next_number
          FROM public.appointment AS a
         WHERE a.clinic_id = target.clinic_id
           AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = clinic_day
           AND a.queue_number ~ '^[0-9]+$';

        target.queue_number := next_number::text;
    END IF;

    UPDATE public.appointment AS a
       SET status = 'CHECKED_IN',
           queue_number = target.queue_number,
           updated_at = pg_catalog.now()
     WHERE a.id = target.id
     RETURNING a.id, a.queue_number
      INTO id, queue_number;

    RETURN NEXT;
END
$function$;

COMMENT ON FUNCTION public.check_in_appointment(uuid, text[]) IS
  'Atomic check-in: status change plus the next queue number for that clinic '
  'and day, under a per-(clinic, day) advisory lock.';
