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
export PATH="${CLINIC_PATH_PREFIX:-/opt/homebrew/bin:/usr/local/bin}:$PATH"

ts()  { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" >>"$LOG"; }

cd "$REPO" 2>/dev/null || { log "repo not found: $REPO"; exit 1; }
CONTROL_REPO="$REPO"

# Deploy and self-heal must never reconcile the same Compose project at once.
# `/tmp` is host-global on macOS; an override exists only for deterministic tests.
LOCK_DIR="${CLINIC_DEPLOY_LOCK:-/tmp/clinicai-deploy.lock}"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "deployment/self-heal already active ($LOCK_DIR); skipping this tick"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

# CD records the last verified immutable release. Use its compose/config files so
# the five-minute self-heal cannot reapply stale files from the maintenance clone.
ACTIVE_STATE_FILE="$CONTROL_REPO/.active-state-prod"
ENV_FILE="$CONTROL_REPO/.env.prod"
if [ -f "$ACTIVE_STATE_FILE" ]; then
  ACTIVE_REPO="$(grep -E '^source=' "$ACTIVE_STATE_FILE" | head -1 | cut -d= -f2- || true)"
  ACTIVE_ENV="$(grep -E '^env=' "$ACTIVE_STATE_FILE" | head -1 | cut -d= -f2- || true)"
  if [ ! -f "${ACTIVE_REPO:-}/docker-compose.yml" ] || [ ! -f "${ACTIVE_ENV:-}" ]; then
    log "active release state is invalid; refusing mutable fallback: $ACTIVE_STATE_FILE"
    exit 1
  fi
  REPO="$ACTIVE_REPO"
  ENV_FILE="$ACTIVE_ENV"
  cd "$REPO" || exit 1
fi

# Always use the explicit production env. Never reuse a shared `.env` that may
# have been written by a staging deployment.
[ -f "$ENV_FILE" ] || { log "missing production env: $ENV_FILE"; exit 1; }
export CLINIC_ENV_FILE="$ENV_FILE"

# 0) Colima (headless Docker runtime) — start if down.
if command -v colima >/dev/null 2>&1; then
  colima status >/dev/null 2>&1 || { colima start >>"$LOG" 2>&1 && log "colima start OK" || log "colima start FAILED"; }
else
  log "colima not on PATH (install: brew install colima docker)"
fi

# 1) Bring up the prod stack (restart:unless-stopped handles per-container crashes).
# Persist optional profiles in COMPOSE_PROFILES; append cloudflare when configured.
ENABLED_PROFILES=$(grep -E '^COMPOSE_PROFILES=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)
if grep -qE '^TUNNEL_TOKEN=.+' "$ENV_FILE" 2>/dev/null; then
  ENABLED_PROFILES="${ENABLED_PROFILES:+${ENABLED_PROFILES},}cloudflare"
fi
if [ -n "$ENABLED_PROFILES" ]; then
  export COMPOSE_PROFILES="$ENABLED_PROFILES"
else
  unset COMPOSE_PROFILES 2>/dev/null || true
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker compose --env-file "$ENV_FILE" -p clinicai_prod up -d >>"$LOG" 2>&1
  if [ "$?" -eq 0 ]; then
    log "compose up -d OK (prod, profiles=${ENABLED_PROFILES:-none})"
  else
    log "compose up -d FAILED — check $ENV_FILE + docker-compose.yml"
  fi
else
  log "docker daemon not ready — will retry next tick"
fi
