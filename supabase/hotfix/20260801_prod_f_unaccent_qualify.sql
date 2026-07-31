-- HOTFIX for PRODUCTION ONLY: make the backup restorable.
--
-- Not a migration. Production was built by the old repository and is not on this
-- repo's migration lineage (it tracks with public.schema_migrations, 55 rows;
-- supabase_migrations.schema_migrations does not exist there). `supabase db push`
-- would try to replay all 31 migrations from baseline_schema onto a database
-- that already has 35 tables — see docs/prod-cutover-findings.md. So this lands
-- as one reviewed statement, applied once, rather than through a chain that
-- does not apply.
--
-- THE DEFECT. Production's f_unaccent does not qualify its call:
--
--     CREATE FUNCTION public.f_unaccent(text) AS $$ SELECT unaccent('unaccent', $1) $$
--
-- pg_dump opens every dump with set_config('search_path', '', false), and
-- patient.full_name_unaccent is a GENERATED column over this function. The
-- first COPY of a patient row inlines the call, fails to resolve `unaccent`
-- under an empty search_path, and the restore dies. Production has therefore
-- never had a restorable backup — the nightly drill only ever passed because it
-- was restoring local dumps that had landed in the same folder.
--
-- This repo's own baseline already has the qualified form, so nothing changes
-- for local, staging, or any future install; this only brings production's copy
-- into line with what everything else already does.
--
-- SAFE TO RUN, and safe to run twice:
--   * The RESULT of the function is unchanged — same input, same output. Only
--     the resolution path is qualified, so no stored generated value becomes
--     wrong and nothing needs recomputing.
--   * CREATE OR REPLACE keeps the oid, so patient.full_name_unaccent's
--     dependency survives; the column is not rewritten and the table is not
--     locked beyond a brief catalogue update.
--   * IMMUTABLE / STRICT / PARALLEL SAFE are preserved exactly, which a
--     generated column requires.

CREATE OR REPLACE FUNCTION public.f_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $_$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $_$;

-- Prove it resolves with the search_path a restore actually uses.
DO $verify$
DECLARE
    got text;
BEGIN
    PERFORM set_config('search_path', '', true);
    SELECT public.f_unaccent('Nguyễn Thị Hằng') INTO got;
    IF got IS NULL OR got = '' THEN
        RAISE EXCEPTION 'f_unaccent returned nothing under an empty search_path';
    END IF;
    IF got LIKE '%ễ%' OR got LIKE '%ằ%' THEN
        RAISE EXCEPTION 'f_unaccent no longer strips accents: %', got;
    END IF;
    RAISE NOTICE 'f_unaccent OK under empty search_path: % -> %',
        'Nguyễn Thị Hằng', got;
END
$verify$;
