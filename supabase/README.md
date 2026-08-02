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
    20260714000003_idempotency_key.sql     # request replay/cache table
    20260714000004_hot_query_indexes.sql   # production hot-path indexes
    20260714000005_idempotency_scope_and_reservation.sql # atomic actor-scoped reservation
    20260717000001_event_log_least_privilege.sql # MANAGEMENT-only audit reads
    20260717000002_atomic_queue_checkin.sql # atomic daily queue allocation + check-in
    20260730000001_care_episode_select_policy.sql        # RLS on, zero policies -> /episodes was empty
    20260730000002_reference_lookup_select_policies.sql  # same bug class on the lookup tables
    20260730000003_multi_tenant_foundation.sql           # clinic + clinic_membership + clinic_id (ADR-0009)
    20260730000004_tenant_scoped_rls.sql                 # every USING(true) -> current_clinic_ids() (ADR-0004)
    20260730000005_workflow_kernel.sql                   # node_* / work_item_* / follow_up_case (ADR-0011)
    20260730000006_seed_node_catalogue.sql               # the 37 nodes of docs §13, for Dr4Women
  tests/
    bootstrap_plain_postgres.sql           # disposable stock-Postgres fixture
    event_log_rls.sql                      # forward-migration policy assertions
    multi_tenant_foundation.sql            # tenant invariants + cross-clinic isolation
    tenant_invariants.sql                  # every table with clinic_id, derived — not listed
    derive_tenant_tables.sql               # emits that list for scripts/tests/tenant-scope-audit.py
    tenant_scoped_rls.sql                  # no blanket reads; a clinic sees only itself
    workflow_kernel.sql                    # the 37-node catalogue + FS/SS/FF/SF and AND/OR/XOR gates
    run-local.sh                           # apply the chain to a throwaway container, run the assertions
  seed.sql                                  # reference/lookup data only (NO patient PII)
```

## Run the schema tests

```bash
supabase/tests/run-local.sh     # needs Docker; touches no Supabase project
```

CI runs the same assertion files against `postgres:17` service containers, in the
same two shapes the harness uses locally (jobs `db_fresh` and `db_replay` in
`.github/workflows/ci.yml`):

- **`db_fresh`** applies the chain **once** — what `supabase db push` produces on a
  real project — and runs every assertion against that.
- **`db_replay`** applies it twice and asserts nothing beyond "no error".

They are separate because assertions run after a second pass describe a schema
nobody deploys. `20260730000014` drops every `clinic_id` DEFAULT and
`20260730000008` grants `SELECT` wherever a policy exists, so replaying quietly
repaired the two pharmacy bugs of `20260802000001` before any gate could see
them.

**Migrations from `20260730000000` onward must be idempotent** — `db push` retries and
restore drills replay them, which is the property `db_replay` checks.
Earlier migrations are already in production and are not edited retroactively.

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
for migration in migrations/*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration"
done
psql "$DATABASE_URL" -f seed.sql        # optional reference data
```

Apply every pending migration **before** deploying the matching application
release. In particular, payment/scheduling idempotency requires `...00005` and
safe front-desk check-in requires `...00002_atomic_queue_checkin.sql`; the UI
fails closed when those database functions are absent.

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

Database assertions must target a disposable database and roll back their own
transaction:

```bash
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/event_log_rls.sql
```
