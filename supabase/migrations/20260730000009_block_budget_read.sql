-- W5 — Let clinic members read their own capacity configuration.
--
-- `block_budget` holds the per-location, per-doctor, per-hour minute budgets the
-- booking grid is coloured from. It has been backend-only since W1b, which is
-- why /api/appointments/quote held a service-role key just to read config.
--
-- It is configuration, not patient data: no PII, no clinical content, and the
-- staff doing the booking are exactly who needs it. Giving it the same
-- tenant-scoped read as the rest of the catalogue removes the last reason that
-- endpoint had to bypass RLS.
--
-- Writes stay service_role-only, like every other table: no INSERT/UPDATE/
-- DELETE policy is created.
--
-- The capacity ENGINE (resolveBudget/usageOf/cellState in
-- src/dashboard/lib/capacity.ts) deliberately stays shared pure code. The UI has
-- to draw the same grid the server would compute, so duplicating it in Python
-- would create two sources of truth for the same arithmetic — the same reasoning
-- already applied to lib/slot-capacity.ts.

DROP POLICY IF EXISTS block_budget_select_own_clinic ON public.block_budget;
CREATE POLICY block_budget_select_own_clinic
    ON public.block_budget
    FOR SELECT
    TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT ON public.block_budget TO authenticated;
