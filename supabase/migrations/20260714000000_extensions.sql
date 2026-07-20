-- Required Postgres extensions for the ClinicAI baseline schema.
-- Applied BEFORE the baseline (filename order) so indexes/functions resolve.
-- Mirrors what the source Supabase project has installed in `public`.
--   unaccent   : accent-insensitive patient/name search (mig 039)
--   pg_trgm    : trigram GIN indexes for fuzzy search
--   btree_gist : GiST exclusion support (scheduling constraints)
--   pgcrypto   : gen_random_uuid() default for PKs (core also provides it on PG13+)
CREATE EXTENSION IF NOT EXISTS unaccent   WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pg_trgm    WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
