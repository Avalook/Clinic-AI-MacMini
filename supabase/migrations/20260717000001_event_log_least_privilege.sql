-- event_log contains operational audit/outbox payloads and must not be broadly
-- readable by every signed-in browser. Keep service-role/Postgres compatibility:
-- those roles bypass RLS and continue to support EventService and relay workers.
--
-- Forward-only migration. It intentionally does not rewrite historical events:
-- event_log is append-only, and changing old rows would invalidate its audit
-- semantics. Dashboard audit writers redact new PII before INSERT. This policy
-- is deliberately single-clinic; tenant isolation requires a future schema change.

CREATE OR REPLACE FUNCTION public.current_staff_department()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
    SELECT s.primary_department
      FROM public.staff AS s
     WHERE s.auth_user_id = auth.uid()
       AND s.is_active IS TRUE
$function$;

COMMENT ON FUNCTION public.current_staff_department() IS
    'Returns the active staff department linked to the caller JWT; used by RLS policies.';

REVOKE ALL ON FUNCTION public.current_staff_department() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.current_staff_department() FROM anon;
GRANT EXECUTE ON FUNCTION public.current_staff_department() TO authenticated;

DROP POLICY IF EXISTS event_log_select_authenticated ON public.event_log;
DROP POLICY IF EXISTS event_log_select_management ON public.event_log;

CREATE POLICY event_log_select_management
ON public.event_log
FOR SELECT
TO authenticated
USING (public.current_staff_department() = 'MANAGEMENT');

COMMENT ON POLICY event_log_select_management ON public.event_log IS
    'Only an active JWT-linked MANAGEMENT staff member may read audit payloads through the authenticated API.';
