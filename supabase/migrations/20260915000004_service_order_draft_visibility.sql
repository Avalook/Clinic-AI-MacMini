-- Unapproved instructions are visible only to doctors and medical scribes.
-- Restrictive policy also narrows the existing own-clinic permissive policy,
-- including SELECT used by Supabase realtime. Browser writes remain disabled.
DROP POLICY IF EXISTS service_order_draft_visibility ON public.service_order;
CREATE POLICY service_order_draft_visibility
    ON public.service_order AS RESTRICTIVE
    FOR SELECT TO authenticated
    USING (
        clinic_id IN (SELECT public.current_clinic_ids())
        AND (
            exec_status <> 'draft'
            OR clinic_id IN (
                SELECT public.current_clinic_ids_for_roles(ARRAY['DOCTOR', 'TKYK'])
            )
        )
    );
