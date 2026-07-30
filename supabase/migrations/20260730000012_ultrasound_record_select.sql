-- Let staff read ultrasound records the same way they read every other piece of
-- clinical data (ADR-0012).
--
-- WHY NOW. The ultrasound page read this table through the service-role key,
-- which bypasses RLS entirely — the key was doing the job a SELECT policy should
-- do. Deleting the legacy branches means the route reads with the caller's own
-- session, and without this policy it would read nothing.
--
-- Every other clinical table (clinical_record, lab_result, clinical_form_
-- response) already has exactly this policy. ultrasound_record was missed
-- because nothing but the service-role path ever read it.
--
-- Who may WRITE is still decided in FastAPI (ULTRASOUND_DOCTOR only). This is
-- read access for signed-in staff of the owning clinic, nothing more.

ALTER TABLE public.ultrasound_record ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ultrasound_record_select ON public.ultrasound_record;
CREATE POLICY ultrasound_record_select ON public.ultrasound_record
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT ON public.ultrasound_record TO authenticated;
