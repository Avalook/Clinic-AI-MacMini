-- W1 — Fix care_episode read path.
--
-- care_episode has RLS ENABLED (baseline line ~2530) but ZERO policies, so
-- PostgREST returns 0 rows to `authenticated` users. The dashboard screen
-- app/(dashboard)/episodes reads care_episode as an authenticated user, so the
-- "Đóng đợt khám" screen silently shows nothing (no error, just empty).
--
-- Fix: add the same authenticated SELECT policy its clinical siblings already
-- use (clinical_record, lab_result, appointment, ...). This unblocks /episodes
-- while keeping the current read model consistent.
--
-- NOTE (scope): this deliberately matches the existing broad
-- `*_select_authenticated USING (true)` pattern. The clinic-wide RLS tightening
-- — moving sensitive reads behind FastAPI + service_role so reception/management
-- get 0 clinical rows (BRIEF W4 / DOD ROLE-02) — is a SEPARATE task that will
-- narrow all of these policies together.
--
-- Writes remain service_role-only by design: NO INSERT/UPDATE/DELETE policy.

DROP POLICY IF EXISTS care_episode_select_authenticated ON public.care_episode;

CREATE POLICY care_episode_select_authenticated
  ON public.care_episode
  FOR SELECT
  TO authenticated
  USING (true);
