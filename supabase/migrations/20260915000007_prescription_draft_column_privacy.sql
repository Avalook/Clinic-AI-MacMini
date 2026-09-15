-- Nurses may read the clinical chart, but only DOCTOR/TKYK can read an
-- unapproved medication proposal. RLS is row-level and cannot hide one column.
-- Replace table-wide read grants with column grants excluding that column.
REVOKE SELECT ON public.clinical_record FROM PUBLIC, anon, authenticated;
DO $$
DECLARE
    cols text;
BEGIN
    SELECT string_agg(format('%I', column_name), ', ' ORDER BY ordinal_position)
      INTO cols
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'clinical_record'
       AND column_name <> 'prescription_draft';
    IF cols IS NULL THEN
        RAISE EXCEPTION 'clinical_record columns not found';
    END IF;
    EXECUTE format('GRANT SELECT (%s) ON public.clinical_record TO authenticated', cols);
END;
$$;

-- The app calls this via the user's authenticated PostgREST client. A
-- SECURITY DEFINER function gives draft content only after role/clinic check;
-- it never broadens the regular chart row policy.
CREATE OR REPLACE FUNCTION public.read_prescription_draft(p_visit_id uuid)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $$
    SELECT r.prescription_draft
      FROM public.clinical_record r
      JOIN public.visit v ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
     WHERE r.visit_id = p_visit_id
       AND r.clinic_id IN (
           SELECT public.current_clinic_ids_for_roles(
               ARRAY['DOCTOR', 'ULTRASOUND_DOCTOR', 'TKYK']
           )
       )
     LIMIT 1
$$;
REVOKE ALL ON FUNCTION public.read_prescription_draft(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.read_prescription_draft(uuid) TO authenticated;
