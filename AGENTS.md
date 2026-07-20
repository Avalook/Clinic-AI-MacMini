# AGENTS.md — Dr4Women-MacMini (self-host)

Clean, single-source deployment of ClinicAI: the **whole app runs on the Mac mini**
via Docker Compose, data stays in **Supabase cloud**. Target spec: `docs/spec-clinic.md`.

This folder replaces the old tangle (2 web links / 2 branches / 2 Supabase / manual
DB paste). Here there is **one** of each.

## Architecture
```
client → Caddy (TLS/ingress) → dashboard (Next.js, UI only) → api (FastAPI, all logic) → Supabase
                                             worker ← RabbitMQ (opt-in)
         Uptime Kuma + Dozzle = monitoring/logs (localhost-bound, private via Tailscale)
```
- **Frontend = UI only.** All business logic belongs in the FastAPI backend (or SQL).
  Frontend talks to Supabase directly ONLY for auth + realtime.
- **Everything is containerised + env-driven** (no hardcoded URLs/keys) → lift-and-shift to a VPS later.

## Environments & branches
- `main` → **prod** stack → Supabase **prod**.
- `staging` → **staging** stack → Supabase **staging** (fake/anonymised data only).
- Both run side-by-side on the Mac (different project names + Caddy ports).
- CI runs on every PR + push (ruff/mypy/pytest + tsc/lint/build). CD auto-deploys on
  merge to `main`/`staging` via the self-hosted runner (build → up → health → rollback).

## Database — Supabase CLI ONLY
- Schema = `supabase/migrations/*.sql` (git-tracked). Apply with `supabase db push`.
- **Never** edit schema by hand in the dashboard. See `supabase/README.md`.

## Key commands
```
./scripts/deploy-backend.sh prod          # or staging
docker compose --env-file .env -p clinicai_prod ps
docker compose --env-file .env -p clinicai_prod logs -f
supabase db push                          # apply schema migrations
```

## Rules
- Secrets only in `.env.prod` / `.env.staging` (gitignored) + GitHub Actions secrets. Never in code.
- Router thin; logic in service functions (pure Python, testable). No business rules in TSX.
- Don't run migrations inside the deploy; schema changes are a separate reviewed `db push`.
- Keep the old Vercel build running in parallel until the Mac stack is proven (spec §8).

## Status (see docs/spec-clinic.md for phases)
- **Done:** clean folder, consolidated+optimised Supabase schema (32 tables, validated),
  parameterized prod/staging compose, Caddy ingress, worker, Uptime Kuma + Dozzle,
  `/health` on api + dashboard, CI (mypy + frontend) + CD (rollback), runbook.
- **Pending — Phase 4 (biggest):** move remaining business logic out of `src/dashboard`
  (slot 2+1, capacity CAP-01, queue call-order, roles/auth, MPI dedup, form schemas)
  into FastAPI services / SQL. See the audit worklist.
- **Ops (do on the Mac):** FileVault, PITR/backup + test restore, self-hosted runner
  registration, Cloudflare Tunnel or Tailscale Funnel, reboot test.
