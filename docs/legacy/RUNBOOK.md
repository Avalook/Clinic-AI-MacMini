# RUNBOOK — ClinicAI / Dr4Women self-host (Mac mini)

Data lives in **Supabase cloud**. A Mac crash = *temporarily unreachable*, **never data loss**.

## Daily / quick reference

| Need | Command (in the deploy clone) |
|---|---|
| Bring prod up | `./scripts/deploy-backend.sh prod` |
| Bring staging up | `git checkout <staging-* tag> && ./scripts/deploy-backend.sh staging` |
| See status | `CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod ps` |
| Tail logs | `CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod logs -f --tail=100` |
| Log viewer (web) | Dozzle → `http://127.0.0.1:8888` (via Tailscale) |
| Uptime dashboard | Uptime Kuma → `http://127.0.0.1:3001` (via Tailscale) |
| Unified Ops Center | Dashboard → `/ops` (`MANAGEMENT` only) |

## Scenario: Mac is down / clinic can't reach the app
1. Data is safe (Supabase). Goal is only to restore access.
2. Power/network back → LaunchDaemon runs `clinic-backend-boot.sh` at boot + every 5 min → Colima + stack self-heal. Wait ~2–3 min.
3. Still down → on the Mac: `colima start` then `./scripts/deploy-backend.sh prod`.
4. **Paper fallback:** reception records name/phone/time on paper; nurses record vitals on the exam sheet; enter into the app once it is back. Keep a printed doctor roster + service price list at the desk.

## Scenario: a deploy broke the site
- `deploy-backend.sh` auto-rolls back to the previous images if the health check fails.
- Automatic rollback uses the previous immutable source and private env revision, then rechecks health. If it reports rollback failure, stop and inspect logs instead of mixing files manually.
- Find previous image ids: `docker images clinicai-api` / `docker images clinicai-dashboard`.

## Scenario: one container keeps crashing
- `restart: unless-stopped` restarts it automatically. Inspect: `docker compose ... logs <svc>`.
- Uptime Kuma alerts (Telegram/Zalo) fire when a monitor goes down (configure in Kuma UI).

## Pre-deploy identity cutover (required)

The dashboard now derives all roles from the verified Supabase user linked by
`staff.auth_user_id`; role/staff cookies and the retired staff picker do not
grant access. Before deploying this version to an environment:

1. In that environment, link **every active person who is expected to log in**
   to exactly one active `staff` row. Create/link accounts from **Settings →
   Users** while the current release is still running.
2. Run this read-only check in Supabase SQL Editor. Since the shared clinic
   gate was removed (05/08/2026) there is **no** expected unlinked account —
   every row this returns is a login that will bounce back to `/login`:

   ```sql
   select u.id, u.email, u.last_sign_in_at
   from auth.users as u
   left join public.staff as s
     on s.auth_user_id = u.id and s.is_active = true
   where s.id is null
   order by u.email;
   ```

3. Resolve every other row before deploy. Also confirm no intended login staff
   is missing a link:

   ```sql
   select id, full_name, primary_department
   from public.staff
   where is_active = true and auth_user_id is null
   order by full_name;
   ```

   This second list may include active staff who genuinely do not use the app;
   record/confirm those exceptions with the clinic administrator.
4. Deploy to staging first. Verify one `MANAGEMENT` account can open Settings,
   and one non-management account receives `403` from `/api/admin/users`.
   Then deploy production and ask all active users to sign in again.

Do not re-enable `/role-picker`, trust `clinic_role`/`clinic_staff_id` cookies,
or add a shared-role fallback. If linkage is incomplete, stop the rollout and
finish account linking (or roll back the release).

## DB schema changes (NEVER click-ops in the dashboard)
- All schema changes are SQL files in `supabase/migrations/`, applied via the Supabase CLI:
  ```
  supabase link --project-ref <prod-or-staging-ref>
  supabase db push          # apply pending migrations to the linked project
  ```
- Add a migration: `supabase migration new <name>` → edit the generated SQL → commit → `db push`.
- Apply schema to a BRAND-NEW project (no CLI): `psql "$DATABASE_URL" -f supabase/migrations/20260714000000_extensions.sql` then the baseline, then optionally `supabase/seed.sql`.
- For this release, run `supabase db push` before application deploy: patient
  writes require verified staff JWTs, idempotency requires migration `00005`,
  and queue check-in requires `20260717000002_atomic_queue_checkin.sql`.

## First-time host setup (once)
1. `brew install colima docker docker-compose caddy` ; `brew install supabase/tap/supabase`
2. `sudo pmset -a sleep 0 disablesleep 1 autorestart 1` (no sleep, auto-boot after power loss)
3. Enable **FileVault** (disk encryption — required for patient PII).
4. Fill `.env.prod` (from `.env.prod.example`) and `chmod 600 .env.prod`; never copy it to a shared `.env`.
5. Install the LaunchDaemon (see `docker/com.dr4women.clinic-backend.plist`) pointing at this clone.
6. Public access: Cloudflare Tunnel (set `TUNNEL_TOKEN` in `.env.prod`, stack auto-runs `cloudflared`) OR Tailscale Funnel to the Caddy port.
7. **Test a real reboot** — confirm the stack comes back with no manual login.

## Hai môi trường trên VPS (07/08/2026)

| | Khách dùng thật | Mình code |
|---|---|---|
| Địa chỉ | `http://222.255.215.219` (cổng 80) | cổng **8080** |
| Ứng dụng | `clinicai_prod-*` | `clinicai_staging-*` |
| Database | `clinicai_db` | `clinicai_stg_db` |
| Khoá JWT | riêng | **riêng** |

**Ba thứ phải khác nhau, thiếu một là hỏng cách ly:** `SUPABASE_PREFIX` (tên
container là tên toàn cục), `SUPABASE_JWT_SECRET` (token bên này không đọc được
dữ liệu bên kia), `SUPABASE_GATEWAY_HOST` (Caddy chuyển `/auth` `/rest`
`/realtime` về đúng bộ của mình — ghi cứng tên gateway prod là staging gọi
thẳng vào database khách hàng).

Đã đo: token prod đọc dữ liệu staging → `401 JWSInvalidSignature`, và ngược
lại. `scripts/dung-staging.sh` kiểm ba biến đó **trước khi** dựng.

```bash
ssh clinic-vps 'cd ~/clinicai && ./scripts/dung-staging.sh'          # cập nhật
ssh clinic-vps 'cd ~/clinicai && ./scripts/dung-staging.sh --gieo'   # + dữ liệu thử
```

Deploy **prod** vẫn như cũ và không đụng gì tới staging:

```bash
ssh clinic-vps 'cd ~/clinicai && git pull --ff-only origin main \
  && DEPLOY_EXPECTED_SHA=$(git rev-parse HEAD) ./scripts/deploy-backend.sh prod'
```
