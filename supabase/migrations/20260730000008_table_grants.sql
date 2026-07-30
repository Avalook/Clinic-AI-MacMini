-- Restore the table privileges the frozen baseline lost.
--
-- Found by standing up a fresh Supabase project (locally) and applying the
-- migration chain: `authenticated` had no SELECT on `patient`, on `visit`, on
-- anything from the baseline. Every `*_select_own_clinic` policy written in W1
-- through W4 was unreachable, because a row-level policy only narrows a
-- privilege the role already holds. The app would come up with every screen
-- erroring on permission denied.
--
-- Production never noticed. Its tables were created before the baseline was
-- frozen, so they still carry the grants Supabase's default privileges gave
-- them at creation time. `20260714000001_baseline_schema.sql` was dumped
-- without ACLs, so the grants existed only in the live database and in nobody's
-- git history. Any NEW environment — staging, a second clinic on its own
-- project, a restore drill — would have been broken from the first request.
--
-- Rather than reinstating Supabase's blanket defaults (ALL on everything to
-- anon and authenticated), the grants are made explicit and narrowed to the
-- model the ADRs describe:
--
--   service_role   ALL on everything          the backend owns every write
--   authenticated  SELECT, and only on tables that actually have a read policy
--   anon           nothing                    there is no public surface
--
-- Driving `authenticated` off the policies means the two stay in step by
-- construction: a table gets a read grant when, and only when, somebody wrote a
-- policy saying who may read it. `idempotency_key` and `pos_outbox` have no
-- policy on purpose, so they get no grant.

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

DO $grants$
DECLARE
    t record;
    granted integer := 0;
BEGIN
    -- The backend acts as service_role and is responsible for every write.
    FOR t IN
        SELECT c.relname
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relkind = 'r'
    LOOP
        EXECUTE format('GRANT ALL ON public.%I TO service_role', t.relname);
    END LOOP;

    -- Read access for end users, exactly where a policy grants it.
    FOR t IN
        SELECT DISTINCT c.relname
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN pg_policy p ON p.polrelid = c.oid
         WHERE n.nspname = 'public'
           AND c.relkind = 'r'
           AND p.polcmd IN ('r', '*')
    LOOP
        EXECUTE format('GRANT SELECT ON public.%I TO authenticated', t.relname);
        granted := granted + 1;
    END LOOP;

    RAISE NOTICE 'granted SELECT to authenticated on % tables', granted;
END
$grants$;

-- Belt and braces for the two that must never be client-readable, in case a
-- future policy is added to them by accident: they are written and read only by
-- the backend (see 20260730000004 and 20260730000007).
REVOKE ALL ON public.idempotency_key FROM anon, authenticated;
REVOKE ALL ON public.pos_outbox FROM anon, authenticated;

-- Sequences: PostgREST needs USAGE to satisfy a DEFAULT nextval() on insert,
-- but only service_role inserts, so only service_role gets it.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
