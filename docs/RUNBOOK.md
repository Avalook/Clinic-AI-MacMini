# RUNBOOK — ClinicAI / Dr4Women self-host (Mac mini)

Data lives in **Supabase cloud**. A Mac crash = *temporarily unreachable*, **never data loss**.

## Daily / quick reference

| Need | Command (in the deploy clone) |
|---|---|
| Bring prod up | `./scripts/deploy-backend.sh prod` |
| Bring staging up | `./scripts/deploy-backend.sh staging` |
| See status | `docker compose --env-file .env -p clinicai_prod ps` |
| Tail logs | `docker compose --env-file .env -p clinicai_prod logs -f --tail=100` |
| Log viewer (web) | Dozzle → `http://127.0.0.1:8888` (via Tailscale) |
| Uptime dashboard | Uptime Kuma → `http://127.0.0.1:3001` (via Tailscale) |

## Scenario: Mac is down / clinic can't reach the app
1. Data is safe (Supabase). Goal is only to restore access.
2. Power/network back → LaunchDaemon runs `clinic-backend-boot.sh` at boot + every 5 min → Colima + stack self-heal. Wait ~2–3 min.
3. Still down → on the Mac: `colima start` then `./scripts/deploy-backend.sh prod`.
4. **Paper fallback:** reception records name/phone/time on paper; nurses record vitals on the exam sheet; enter into the app once it is back. Keep a printed doctor roster + service price list at the desk.

## Scenario: a deploy broke the site
- `deploy-backend.sh` auto-rolls back to the previous images if the health check fails.
- Manual rollback: `docker tag <old-image-id> clinicai-api:prod && docker tag <old-id> clinicai-dashboard:prod && docker compose --env-file .env -p clinicai_prod up -d`.
- Find previous image ids: `docker images clinicai-api` / `docker images clinicai-dashboard`.

## Scenario: one container keeps crashing
- `restart: unless-stopped` restarts it automatically. Inspect: `docker compose ... logs <svc>`.
- Uptime Kuma alerts (Telegram/Zalo) fire when a monitor goes down (configure in Kuma UI).

## DB schema changes (NEVER click-ops in the dashboard)
- All schema changes are SQL files in `supabase/migrations/`, applied via the Supabase CLI:
  ```
  supabase link --project-ref <prod-or-staging-ref>
  supabase db push          # apply pending migrations to the linked project
  ```
- Add a migration: `supabase migration new <name>` → edit the generated SQL → commit → `db push`.
- Apply schema to a BRAND-NEW project (no CLI): `psql "$DATABASE_URL" -f supabase/migrations/20260714000000_extensions.sql` then the baseline, then optionally `supabase/seed.sql`.

## First-time host setup (once)
1. `brew install colima docker docker-compose caddy` ; `brew install supabase/tap/supabase`
2. `sudo pmset -a sleep 0 disablesleep 1 autorestart 1` (no sleep, auto-boot after power loss)
3. Enable **FileVault** (disk encryption — required for patient PII).
4. Fill `.env.prod` (from `.env.prod.example`). `cp .env.prod .env`.
5. Install the LaunchDaemon (see `docker/com.dr4women.clinic-backend.plist`) pointing at this clone.
6. Public access: Cloudflare Tunnel (set `TUNNEL_TOKEN` in `.env.prod`, stack auto-runs `cloudflared`) OR Tailscale Funnel to the Caddy port.
7. **Test a real reboot** — confirm the stack comes back with no manual login.
