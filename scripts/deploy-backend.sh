#!/bin/bash
# Deploy the ClinicAI self-host stack on the Mac mini.
#   ./scripts/deploy-backend.sh prod      # main    → prod stack    (Supabase prod)
#   ./scripts/deploy-backend.sh staging   # staging → staging stack (Supabase staging)
#
# Flow (spec Phase 5/7): verify exact source → build → up → health → rollback.
# CLINIC_ENV_DIR may point at a separate secrets directory (used by CI checkouts).
# DB migrations are NOT run here — apply schema separately + reviewed via Supabase CLI
# (`supabase db push`). Decoupling schema from code deploy keeps deploys safe.
set -euo pipefail

ENVN="${1:-}"
case "$ENVN" in
  prod) EXPECTED_BRANCH="main"; EXPECTED_APP_ENV="production" ;;
  staging) EXPECTED_BRANCH="staging"; EXPECTED_APP_ENV="staging" ;;
  *) echo "usage: $0 [prod|staging]" >&2; exit 2 ;;
esac

export PATH="${CLINIC_PATH_PREFIX:-/opt/homebrew/bin:/usr/local/bin}:$PATH"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

PROJECT="clinicai_${ENVN}"
TAG="$ENVN"
ENV_DIR="${CLINIC_ENV_DIR:-$REPO}"
SOURCE_ENV_FILE="${ENV_DIR}/.env.${ENVN}"
ENV_FILE="$SOURCE_ENV_FILE"

[ -f "$SOURCE_ENV_FILE" ] || { echo "!! missing $SOURCE_ENV_FILE (fill from ${SOURCE_ENV_FILE}.example)" >&2; exit 1; }

LOCK_DIR="${CLINIC_DEPLOY_LOCK:-/tmp/clinicai-deploy.lock}"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "!! another ClinicAI deploy is active ($LOCK_DIR)" >&2
  exit 1
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

echo "==> [1/6] verify source + environment"
if [ -n "$(git status --porcelain --untracked-files=normal)" ] && [ "${DEPLOY_ALLOW_DIRTY:-0}" != "1" ]; then
  echo "!! refusing to deploy a dirty worktree (set DEPLOY_ALLOW_DIRTY=1 only for an intentional emergency)" >&2
  exit 1
fi

if [ -n "${DEPLOY_EXPECTED_SHA:-}" ]; then
  PINNED_CHECKOUT=1
  ACTUAL_SHA="$(git rev-parse HEAD)"
  [ "$ACTUAL_SHA" = "$DEPLOY_EXPECTED_SHA" ] || {
    echo "!! checkout SHA $ACTUAL_SHA does not match requested $DEPLOY_EXPECTED_SHA" >&2
    exit 1
  }
  if [ -n "${DEPLOY_SOURCE_BRANCH:-}" ] && [ "$DEPLOY_SOURCE_BRANCH" != "$EXPECTED_BRANCH" ]; then
    echo "!! $ENVN must deploy from $EXPECTED_BRANCH, not $DEPLOY_SOURCE_BRANCH" >&2
    exit 1
  fi
else
  PINNED_CHECKOUT=0
  CURRENT_BRANCH="$(git branch --show-current)"
  [ "$CURRENT_BRANCH" = "$EXPECTED_BRANCH" ] || {
    echo "!! $ENVN must deploy from branch $EXPECTED_BRANCH (currently ${CURRENT_BRANCH:-detached})" >&2
    exit 1
  }
  # Preserve the old manual workflow, but never continue with stale code.
  git pull --ff-only
fi

# Freeze the exact env revision used by this release in the private secrets
# directory. A rollback must never reuse a newly edited/broken env file.
RELEASE_SHA="$(git rev-parse HEAD)"
RELEASE_SOURCE="$REPO"
if [ "$PINNED_CHECKOUT" = "0" ]; then
  RELEASE_SOURCE_DIR="${ENV_DIR}/.release-source-${ENVN}"
  RELEASE_SOURCE="${RELEASE_SOURCE_DIR}/${RELEASE_SHA}"
  if [ ! -f "$RELEASE_SOURCE/docker-compose.yml" ]; then
    mkdir -p "$RELEASE_SOURCE_DIR" "${RELEASE_SOURCE}.tmp"
    git archive HEAD | tar -x -C "${RELEASE_SOURCE}.tmp"
    mv "${RELEASE_SOURCE}.tmp" "$RELEASE_SOURCE"
  fi
fi
if command -v shasum >/dev/null 2>&1; then
  ENV_HASH="$(shasum -a 256 "$SOURCE_ENV_FILE" | awk '{print $1}')"
else
  ENV_HASH="$(sha256sum "$SOURCE_ENV_FILE" | awk '{print $1}')"
fi
RELEASE_ENV_DIR="${ENV_DIR}/.release-env-${ENVN}"
mkdir -p "$RELEASE_ENV_DIR"
chmod 700 "$RELEASE_ENV_DIR"
ENV_FILE="${RELEASE_ENV_DIR}/${RELEASE_SHA}-${ENV_HASH}.env"
if [ ! -f "$ENV_FILE" ]; then
  cp "$SOURCE_ENV_FILE" "${ENV_FILE}.tmp"
  chmod 600 "${ENV_FILE}.tmp"
  mv "${ENV_FILE}.tmp" "$ENV_FILE"
fi
export CLINIC_ENV_FILE="$ENV_FILE"
COMPOSE=(docker compose --env-file "$ENV_FILE" -p "$PROJECT")

env_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2- || true
}

[ "$(env_value APP_ENV)" = "$EXPECTED_APP_ENV" ] || {
  echo "!! APP_ENV in $ENV_FILE must be $EXPECTED_APP_ENV" >&2
  exit 1
}
[ "$(env_value COMPOSE_PROJECT_NAME)" = "$PROJECT" ] || {
  echo "!! COMPOSE_PROJECT_NAME in $ENV_FILE must be $PROJECT" >&2
  exit 1
}
[ "$(env_value IMAGE_TAG)" = "$TAG" ] || {
  echo "!! IMAGE_TAG in $ENV_FILE must be $TAG" >&2
  exit 1
}
for required in SITE_ADDRESS SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY DATABASE_URL BACKEND_API_KEY; do
  value="$(env_value "$required")"
  if [ -z "$value" ] || [[ "$value" == *"<"* ]]; then
    echo "!! required setting $required is empty or still a placeholder in $ENV_FILE" >&2
    exit 1
  fi
done

# Reconcile every intentionally enabled optional service as part of the same
# release. This prevents workers/relay/tunnel containers from remaining on an
# old image merely because Compose profiles are opt-in.
ENABLED_PROFILES="$(env_value COMPOSE_PROFILES)"
if [ -n "$(env_value TUNNEL_TOKEN)" ]; then
  ENABLED_PROFILES="${ENABLED_PROFILES:+${ENABLED_PROFILES},}cloudflare"
fi
if [ -n "$ENABLED_PROFILES" ]; then
  export COMPOSE_PROFILES="$ENABLED_PROFILES"
else
  unset COMPOSE_PROFILES 2>/dev/null || true
fi

"${COMPOSE[@]}" config --quiet

echo "==> [2/6] snapshot current images for rollback"
OLD_API="$(docker image inspect -f '{{.Id}}' "clinicai-api:${TAG}"       2>/dev/null || true)"
OLD_DASH="$(docker image inspect -f '{{.Id}}' "clinicai-dashboard:${TAG}" 2>/dev/null || true)"
ACTIVE_STATE_FILE="${ENV_DIR}/.active-state-${ENVN}"
PREVIOUS_RELEASE=""
PREVIOUS_ENV_FILE=""
if [ -f "$ACTIVE_STATE_FILE" ]; then
  PREVIOUS_RELEASE="$(grep -E '^source=' "$ACTIVE_STATE_FILE" | head -1 | cut -d= -f2- || true)"
  PREVIOUS_ENV_FILE="$(grep -E '^env=' "$ACTIVE_STATE_FILE" | head -1 | cut -d= -f2- || true)"
  if [ ! -f "$PREVIOUS_RELEASE/docker-compose.yml" ] || [ ! -f "$PREVIOUS_ENV_FILE" ]; then
    PREVIOUS_RELEASE=""
    PREVIOUS_ENV_FILE=""
  fi
fi
PREVIOUS_PROFILES=""
if [ -n "$PREVIOUS_ENV_FILE" ]; then
  PREVIOUS_PROFILES="$(grep -E '^COMPOSE_PROFILES=' "$PREVIOUS_ENV_FILE" | head -1 | cut -d= -f2- || true)"
  if grep -qE '^TUNNEL_TOKEN=.+' "$PREVIOUS_ENV_FILE" 2>/dev/null; then
    PREVIOUS_PROFILES="${PREVIOUS_PROFILES:+${PREVIOUS_PROFILES},}cloudflare"
  fi
fi

echo "==> [3/6] build"
"${COMPOSE[@]}" build

profile_enabled() {
  case ",${1// /}," in *",$2,"*) return 0 ;; *) return 1 ;; esac
}

# `compose up` does not remove containers belonging to profiles that were just
# disabled. Remove only those known optional services, while holding the host
# deploy lock, before reconciling the new release.
remove_disabled_services() {
  if ! profile_enabled "$ENABLED_PROFILES" workers; then
    "${COMPOSE[@]}" rm -sf worker rabbitmq
  fi
  if ! profile_enabled "$ENABLED_PROFILES" workers && ! profile_enabled "$ENABLED_PROFILES" notifications; then
    "${COMPOSE[@]}" rm -sf notification-relay
  fi
  if ! profile_enabled "$ENABLED_PROFILES" cloudflare; then
    "${COMPOSE[@]}" rm -sf cloudflared
  fi
}
remove_disabled_services

echo "==> [4/6] up -d"
"${COMPOSE[@]}" up -d

echo "==> [5/6] health check (up to ~120s)"
health_ok() {
  local svc cid st
  for svc in api dashboard caddy; do
    cid="$("${COMPOSE[@]}" ps -q "$svc" 2>/dev/null || true)"
    [ -n "$cid" ] || { echo "   $svc: no container"; return 1; }
    st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)"
    [ "$st" = "healthy" ] || [ "$st" = "running" ] || { echo "   $svc: $st"; return 1; }
    [ "$st" = "healthy" ] || return 1
  done
  if profile_enabled "$ENABLED_PROFILES" workers; then
    for svc in rabbitmq worker notification-relay; do
      cid="$("${COMPOSE[@]}" ps -q "$svc" 2>/dev/null || true)"
      [ -n "$cid" ] || { echo "   $svc: no container"; return 1; }
      st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)"
      [ "$st" = "healthy" ] || [ "$st" = "running" ] || return 1
    done
  elif profile_enabled "$ENABLED_PROFILES" notifications; then
    cid="$("${COMPOSE[@]}" ps -q notification-relay 2>/dev/null || true)"
    [ -n "$cid" ] || return 1
    st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)"
    [ "$st" = "healthy" ] || [ "$st" = "running" ] || return 1
  fi
  if profile_enabled "$ENABLED_PROFILES" cloudflare; then
    cid="$("${COMPOSE[@]}" ps -q cloudflared 2>/dev/null || true)"
    [ -n "$cid" ] || return 1
    st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)"
    [ "$st" = "healthy" ] || [ "$st" = "running" ] || return 1
  fi
  return 0
}

wait_for_health() {
  local i
  for i in $(seq 1 24); do
    if health_ok; then echo "   all healthy ✓"; return 0; fi
    sleep 5
  done
  return 1
}

if wait_for_health; then DEPLOY_OK=1; fi

if [ "${DEPLOY_OK:-0}" != "1" ]; then
  echo "!! health check FAILED — rolling back"
  if [ -n "$OLD_API" ] && [ -n "$OLD_DASH" ] && [ -n "$PREVIOUS_RELEASE" ] && [ -n "$PREVIOUS_ENV_FILE" ]; then
    docker tag "$OLD_API"  "clinicai-api:${TAG}"
    docker tag "$OLD_DASH" "clinicai-dashboard:${TAG}"
    cd "$PREVIOUS_RELEASE"
    export CLINIC_ENV_FILE="$PREVIOUS_ENV_FILE"
    ENABLED_PROFILES="$PREVIOUS_PROFILES"
    if [ -n "$ENABLED_PROFILES" ]; then export COMPOSE_PROFILES="$ENABLED_PROFILES"; else unset COMPOSE_PROFILES 2>/dev/null || true; fi
    COMPOSE=(docker compose --env-file "$PREVIOUS_ENV_FILE" -p "$PROJECT")
    remove_disabled_services
    "${COMPOSE[@]}" up -d
    if wait_for_health; then
      echo "   rollback health verified. Investigate the failed release logs."
    else
      echo "!! rollback was attempted but health verification FAILED" >&2
    fi
  else
    echo "   no complete previous release (source + images) to roll back to. Stack left up for inspection."
  fi
  exit 1
fi

printf 'source=%s\nenv=%s\n' "$RELEASE_SOURCE" "$ENV_FILE" > "${ACTIVE_STATE_FILE}.tmp"
mv "${ACTIVE_STATE_FILE}.tmp" "$ACTIVE_STATE_FILE"
echo "==> [6/6] deployment verified at $(git rev-parse HEAD)"
echo "==> deploy ($ENVN) complete."
