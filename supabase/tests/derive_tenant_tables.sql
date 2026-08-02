-- The list of tenant-scoped tables, as the schema currently defines it: every
-- public base table with a clinic_id column. Not an assertion file — it emits
-- one table name per line for tools that need the list:
--
--   psql -At -f supabase/tests/derive_tenant_tables.sql > tenant-tables.txt
--   python3 scripts/tests/tenant-scope-audit.py --check --tenant-tables tenant-tables.txt
--
-- The audit used to carry these names inline and fell behind the schema in both
-- directions at once. Anything that needs the list should ask here.
--
-- Note this is a wider set than tenant_invariants.sql checks: clinic_membership
-- appears below because a backend query that reads it without clinic_id does
-- read across clinics, which is exactly the audit's question. It is excluded
-- from the invariants file because it maps staff TO clinics rather than
-- belonging to one, so per-tenant RLS is not the right shape for it.
SELECT c.relname
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public'
   AND c.relkind = 'r'
   AND EXISTS (
       SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = c.oid
          AND a.attname = 'clinic_id'
          AND a.attnum > 0
          AND NOT a.attisdropped)
 ORDER BY c.relname;
