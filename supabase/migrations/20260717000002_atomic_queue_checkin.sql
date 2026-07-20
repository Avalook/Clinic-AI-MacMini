-- Allocate the daily clinic queue number and transition to CHECKED_IN in one
-- database transaction. The advisory lock serializes concurrent check-ins for
-- the same Vietnam clinic day, removing the former client-side MAX()+1 race.

CREATE OR REPLACE FUNCTION public.assign_appointment_queue_number()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
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
        pg_catalog.hashtextextended('clinicai:queue:' || clinic_day::text, 0)
    );

    SELECT coalesce(max(a.queue_number::integer), 0) + 1
      INTO next_number
      FROM public.appointment AS a
     WHERE (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = clinic_day
       AND a.queue_number ~ '^[0-9]+$'
       AND a.id IS DISTINCT FROM NEW.id;

    NEW.queue_number := next_number::text;
    RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION public.assign_appointment_queue_number() FROM PUBLIC;

DROP TRIGGER IF EXISTS appointment_assign_queue_number
ON public.appointment;

CREATE TRIGGER appointment_assign_queue_number
BEFORE INSERT OR UPDATE OF status, queue_number, slot_start
ON public.appointment
FOR EACH ROW
EXECUTE FUNCTION public.assign_appointment_queue_number();

CREATE OR REPLACE FUNCTION public.check_in_appointment(
    p_appointment_id uuid,
    p_from_statuses text[]
)
RETURNS TABLE (id uuid, queue_number text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
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
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended('clinicai:queue:' || clinic_day::text, 0)
    );

    IF nullif(pg_catalog.btrim(target.queue_number), '') IS NULL THEN
        SELECT coalesce(max(a.queue_number::integer), 0) + 1
          INTO next_number
          FROM public.appointment AS a
         WHERE (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = clinic_day
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

REVOKE ALL ON FUNCTION public.check_in_appointment(uuid, text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.check_in_appointment(uuid, text[]) FROM anon;
REVOKE ALL ON FUNCTION public.check_in_appointment(uuid, text[]) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.check_in_appointment(uuid, text[]) TO service_role;

COMMENT ON FUNCTION public.check_in_appointment(uuid, text[]) IS
  'Atomically assign the Vietnam-day queue number and transition an appointment to CHECKED_IN; service-role only.';
