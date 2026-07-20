#!/bin/bash
# Keep the ClinicAI PROD stack alive on the Mac mini (headless, self-healing).
# Called by the LaunchDaemon at BOOT (no GUI login) + every 5 min (self-heal).
# Idempotent: safe to run anytime.
#   (1) Colima (Docker runtime) is up
#   (2) prod stack is up (docker compose, project clinicai_prod)
# Ingress is part of the stack: Caddy + (if TUNNEL_TOKEN set) cloudflared.
#
# $1 = deploy clone path (LaunchDaemon passes it). Default = the standard clone.
set -u

REPO="${1:-$HOME/Projects/Dr4Women-MacMini}"
LOG="$HOME/Library/Logs/clinic-backend-boot.log"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

ts()  { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" >>"$LOG"; }

cd "$REPO" 2>/dev/null || { log "repo not found: $REPO"; exit 1; }

# Activate prod env if not already present.
[ -f .env ] || { [ -f .env.prod ] && cp .env.prod .env && log "activated .env.prod"; }

# 0) Colima (headless Docker runtime) — start if down.
if command -v colima >/dev/null 2>&1; then
  colima status >/dev/null 2>&1 || { colima start >>"$LOG" 2>&1 && log "colima start OK" || log "colima start FAILED"; }
else
  log "colima not on PATH (install: brew install colima docker)"
fi

# 1) Bring up the prod stack (restart:unless-stopped handles per-container crashes).
#    Enable the cloudflare tunnel profile automatically when a token is configured.
PROFILES=()
grep -qE '^TUNNEL_TOKEN=.+' .env 2>/dev/null && PROFILES+=(--profile cloudflare)

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if docker compose --env-file .env -p clinicai_prod "${PROFILES[@]}" up -d >>"$LOG" 2>&1; then
    log "compose up -d OK (prod${PROFILES:+ +cloudflare})"
  else
    log "compose up -d FAILED — check $REPO/.env + docker-compose.yml"
  fi
else
  log "docker daemon not ready — will retry next tick"
fi
