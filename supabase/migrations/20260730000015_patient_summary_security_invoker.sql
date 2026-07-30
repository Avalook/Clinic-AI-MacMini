-- Close the patient_summary cross-tenant view bypass.
--
-- PostgreSQL views execute with the view owner's permissions by default.  The
-- owner bypasses patient RLS, so granting this ordinary view to authenticated
-- let clinic A read clinic B's identity and visit/lab metadata even though a
-- direct SELECT from patient was correctly tenant-scoped.
--
-- The dashboard has no direct consumer of patient_summary. FastAPI reads it
-- through the privileged database pool with an explicit clinic_id predicate;
-- service_role retains access for backend tooling. Remove the frontend
-- privilege. SECURITY INVOKER remains as a second line of defence: if a future
-- migration grants the view again, its base-table RLS still applies.

ALTER VIEW public.patient_summary SET (security_invoker = true);

REVOKE ALL ON public.patient_summary FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.patient_summary TO service_role;

COMMENT ON VIEW public.patient_summary IS
  'Backend-only patient summary. SECURITY INVOKER prevents owner-rights RLS bypass.';
