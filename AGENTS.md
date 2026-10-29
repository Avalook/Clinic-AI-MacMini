# AGENTS.md — ClinicAI (Dr4Women)

**Read `CLAUDE.md` first** — it is the source of truth for architecture, rules and
commands, and applies to every agent (Claude, Codex, others). Then
`docs/SO-LUAT.md` (rules), `docs/DANG-LAM.md` (work in progress). Reply to the
team in Vietnamese.

## Where it runs (27/09/2026)
- **One VPS** `clinic-vps-moi` (222.255.214.133), https://dr4women.io.vn,
  prod at `/home/clinicai/clinicai` on branch `main`.
- Database: **self-hosted Supabase on that VPS** (`docker-compose.supabase.yml`:
  Postgres + GoTrue + PostgREST + Realtime + gateway). The Mac only receives backups.
- **Dead — do not use or reintroduce:** old VPS `clinic-vps` (222.255.215.219),
  staging (:8080, `/home/clinicai/staging`), Mac mini hosting, Vercel, Supabase
  cloud, Cloudflare Tunnel, Tailscale, Sentry, GitHub Actions CD, `supabase db push`.
  Docs from that era live in `docs/legacy/`.

## Architecture
```
client → Caddy (TLS) → dashboard (Next.js, UI only) → api (FastAPI, all logic) → Postgres
                       su-kien (event worker)         self-hosted Supabase (auth + realtime)
```
- **Frontend = UI only.** Business rules belong in FastAPI services or SQL. The
  frontend talks to Supabase directly ONLY for auth + realtime.
- Everything is containerised + env-driven (no hardcoded URLs/keys).

## CI / deploy
- CI runs **on the dev machine**: `./scripts/ci-may.sh --bao-github` (GitHub
  Actions is down — billing). Green before merge, green before deploy.
- No automatic CD. Deploy by hand on the VPS: backup → (migrations: rehearse on a
  copy, then `scripts/apply-pending-migrations.sh --apply`) →
  `git checkout -B main <reviewed-sha>` (never `origin/main`) →
  `DEPLOY_EXPECTED_SHA=<reviewed-sha> ./scripts/deploy-backend.sh prod` — without
  that variable the script runs `git pull --ff-only` and deploys whatever `main`
  is by then. Afterwards `deployment verified at <sha>` must print that SHA.
  Details: skill `len-prod`.
- Only `main` is long-lived; work branches live ≤ 2 days.

## Rules
- Secrets only in `.env.prod` on the VPS (gitignored). Never in code or chat.
- Router thin; logic in service functions (pure Python, testable). No business rules in TSX.
- Schema only via `supabase/migrations/*.sql`; migrations are a separate, watched
  step — never inside the deploy.
- UI changes: follow `DESIGN.md` and the "Sửa giao diện" procedure in `CLAUDE.md`.

## Reading code — read the real source, not memory
- Definitions, callers, renames: **Serena** (`find_symbol`, `find_referencing_symbols`).
- Behavior questions when you don't know the file: `jg "<question>" src` (only if
  `jg doctor` passes). Root is always `src` or `supabase/migrations`, never the repo
  root: `scratch/`, `tmp/`, `docs/`, `reports/` may hold real clinic data and `jg`
  uploads what it reads. Exact strings / filenames: grep.
- Library APIs (FastAPI, Supabase, Next.js…): **context7**, don't recall from memory.
- UI / console / network: chrome-devtools or playwright, local/staging only.
- If a tool fails (MCP down, no `jg` key), say so and use the next one.
