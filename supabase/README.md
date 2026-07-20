# Supabase schema — ClinicAI / Dr4Women

Single source of truth for the database schema. **No click-ops in the dashboard** —
every change is a git-tracked SQL migration applied via the Supabase CLI.

## Files
```
supabase/
  config.toml                              # CLI config (project name, seed path)
  migrations/
    20260714000000_extensions.sql          # required extensions (unaccent, pg_trgm, btree_gist, pgcrypto)
    20260714000001_baseline_schema.sql     # consolidated schema: 32 tables + RLS + functions/triggers
    20260714000002_slot_capacity_guard.sql # atomic 2+1 booking net (advisory-lock trigger)
  seed.sql                                  # reference/lookup data only (NO patient PII)
```

## How this was built
The baseline was frozen from the live schema (`pg_dump --schema=public --schema-only`)
after all 62 historical incremental migrations, then **optimised**:
- **Dropped 3 dead tables** (zero code references, audited): `patient_contact_channel`,
  `patient_next_of_kin`, `visit_amendment` — plus their orphaned trigger function.
- All `ALTER`s folded into `CREATE`s; the dropped `appointment_no_doctor_overlap`
  constraint (removed in old migration 057) is simply absent.
- `f_unaccent()` hardened to be schema-path-safe (qualified `public.unaccent`).

Result: **32 tables** (was 35), one clean baseline instead of 62 patch files with
numbering collisions. Validated end-to-end on a fresh Postgres 17 (extensions →
baseline → seed apply cleanly). The remaining 31 domain tables are all referenced
by the app — no further tables were safe to drop.

## Apply to a project
```bash
# preferred — Supabase CLI
supabase link --project-ref <ref>
supabase db push

# or raw psql to a fresh project
psql "$DATABASE_URL" -f migrations/20260714000000_extensions.sql
psql "$DATABASE_URL" -f migrations/20260714000001_baseline_schema.sql
psql "$DATABASE_URL" -f seed.sql        # optional reference data
```

## seed.sql contents (no PII)
clinic_location (2), service_type (14), service_price (29), booking_channel (7),
drug_catalog (64), province (34), ward (3321). Staff and all patient/clinical data
are intentionally excluded — this is a structure-only clone.

## Add a change later
```bash
supabase migration new <describe_change>   # creates a timestamped empty file
# edit the SQL, commit, then:
supabase db push
```
