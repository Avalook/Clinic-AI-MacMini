-- KQ_CHUA_GUI must reopen when a result becomes usable AFTER an older TRA_KQ.
--
-- The service and upload guard use the effective result timestamp:
-- reviewed_at → result_received_at → created_at. The view previously compared
-- only created_at, so a lab row created at t0, an old result delivered at t1,
-- and the row reviewed at t2 was incorrectly considered delivered (t1 >= t0).
--
-- Rebuild from PostgreSQL's current normalized definition rather than copying
-- the whole multi-branch view again. The exact-count guard makes this fail
-- closed if an earlier migration changes the predicate: silent partial repair
-- would be worse than a migration that stops and asks for review.
DO $$
DECLARE
    view_sql text := pg_get_viewdef('public.v_viec_cskh'::regclass, true);
    old_predicate constant text := 't.xay_ra_luc >= r.created_at';
    new_predicate constant text :=
        't.xay_ra_luc >= COALESCE(r.reviewed_at, r.result_received_at, r.created_at)';
    occurrences integer;
BEGIN
    occurrences := (
        length(view_sql) - length(replace(view_sql, old_predicate, ''))
    ) / length(old_predicate);

    IF occurrences <> 1 THEN
        RAISE EXCEPTION
            'Expected exactly one old KQ_CHUA_GUI predicate, found %', occurrences;
    END IF;

    view_sql := replace(view_sql, old_predicate, new_predicate);
    EXECUTE 'CREATE OR REPLACE VIEW public.v_viec_cskh '
            'WITH (security_invoker = true) AS ' || view_sql;

    IF position(new_predicate IN pg_get_viewdef(
        'public.v_viec_cskh'::regclass, true
    )) = 0 THEN
        RAISE EXCEPTION 'v_viec_cskh effective-result predicate was not installed';
    END IF;
END $$;

COMMENT ON VIEW public.v_viec_cskh IS
    'CSKH work queue; KQ_CHUA_GUI compares delivery with the effective result '
    'timestamp (reviewed_at/result_received_at/created_at), not order creation.';
