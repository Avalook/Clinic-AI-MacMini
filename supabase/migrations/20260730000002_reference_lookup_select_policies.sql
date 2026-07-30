-- W1b — Same bug class as care_episode: RLS ENABLED with ZERO policies.
--
-- A disposable-Postgres run of the full migration chain found 8 tables in this
-- state. For an `authenticated` session PostgREST returns 0 rows from all of
-- them, silently (no error) — exactly the /episodes symptom.
--
-- Confirmed live impact: app/(dashboard)/reports/page.tsx:119 reads
-- `booking_channel` through getSupabaseServer() (the caller's session, role
-- `authenticated`), so the report's channel lookup is always empty.
-- `province` / `ward` are read through getSupabaseService() today, so they work
-- by accident; they are pure reference data and any future UI read should not
-- have to borrow service_role to see a province list.
--
-- Scope of this migration: REFERENCE / LOOKUP tables only — no patient data, no
-- clinical data, no PII. Read-only for `authenticated`; writes stay
-- service_role-only (no INSERT/UPDATE/DELETE policy).
--
-- DELIBERATELY NOT FIXED HERE (they are correct as service_role-only, and the
-- decision on 2026-07-30 was to TIGHTEN RLS, not to broaden it):
--   ultrasound_record  — clinical PII; reached via app/api/ultrasound (service_role)
--   mpi_merge_queue    — patient identifiers pending merge
--   block_budget       — capacity config; reached via app/api/appointments/quote
--   staff_capability   — staffing config; backend-only
--   schema_migrations  — CLI bookkeeping
-- These stay policy-less on purpose. The clinic-scoped rewrite of every policy
-- (auth.uid() -> staff -> clinic_id + role) lands with the identity/tenant work.

DROP POLICY IF EXISTS booking_channel_select_authenticated ON public.booking_channel;
CREATE POLICY booking_channel_select_authenticated
  ON public.booking_channel
  FOR SELECT
  TO authenticated
  USING (true);

DROP POLICY IF EXISTS province_select_authenticated ON public.province;
CREATE POLICY province_select_authenticated
  ON public.province
  FOR SELECT
  TO authenticated
  USING (true);

DROP POLICY IF EXISTS ward_select_authenticated ON public.ward;
CREATE POLICY ward_select_authenticated
  ON public.ward
  FOR SELECT
  TO authenticated
  USING (true);
