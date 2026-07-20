#!/bin/bash
# Deploy the ClinicAI self-host stack on the Mac mini.
#   ./scripts/deploy-backend.sh prod      # main    → prod stack    (Supabase prod)
#   ./scripts/deploy-backend.sh staging   # staging → staging stack (Supabase staging)
#
# Flow (spec Phase 5/7): git pull → build → up → health check → rollback on fail.
# Operates on THIS clone (which must hold the real .env.<env> secrets, gitignored).
# DB migrations are NOT run here — apply schema separately + reviewed via Supabase CLI
# (`supabase db push`). Decoupling schema from code deploy keeps deploys safe.
set -euo pipefail

ENVN="${1:-}"
case "$ENVN" in
  prod|staging) : ;;
  *) echo "usage: $0 [prod|staging]" >&2; exit 2 ;;
esac

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

PROJECT="clinicai_${ENVN}"
TAG="$ENVN"
ENV_FILE=".env.${ENVN}"
COMPOSE=(docker compose --env-file .env -p "$PROJECT")

[ -f "$ENV_FILE" ] || { echo "!! missing $ENV_FILE (fill from ${ENV_FILE}.example)" >&2; exit 1; }

echo "==> [1/6] git pull"
git pull --ff-only || echo "   (pull skipped / not fast-forward — continuing with local tree)"

echo "==> [2/6] activate env ($ENV_FILE → .env)"
cp "$ENV_FILE" .env

echo "==> [3/6] snapshot current images for rollback"
OLD_API="$(docker image inspect -f '{{.Id}}' "clinicai-api:${TAG}"       2>/dev/null || true)"
OLD_DASH="$(docker image inspect -f '{{.Id}}' "clinicai-dashboard:${TAG}" 2>/dev/null || true)"

echo "==> [4/6] build"
"${COMPOSE[@]}" build

echo "==> [5/6] up -d"
"${COMPOSE[@]}" up -d

echo "==> [6/6] health check (up to ~120s)"
health_ok() {
  local svc cid st
  for svc in api dashboard caddy; do
    cid="$("${COMPOSE[@]}" ps -q "$svc" 2>/dev/null || true)"
    [ -n "$cid" ] || { echo "   $svc: no container"; return 1; }
    st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)"
    [ "$st" = "healthy" ] || [ "$st" = "running" ] || { echo "   $svc: $st"; return 1; }
    [ "$st" = "healthy" ] || return 1
  done
  return 0
}

for i in $(seq 1 24); do
  if health_ok; then echo "   all healthy ✓"; DEPLOY_OK=1; break; fi
  sleep 5
done

if [ "${DEPLOY_OK:-0}" != "1" ]; then
  echo "!! health check FAILED — rolling back"
  if [ -n "$OLD_API" ] && [ -n "$OLD_DASH" ]; then
    docker tag "$OLD_API"  "clinicai-api:${TAG}"
    docker tag "$OLD_DASH" "clinicai-dashboard:${TAG}"
    "${COMPOSE[@]}" up -d
    echo "   rolled back to previous images. Investigate: ${COMPOSE[*]} logs --tail=80"
  else
    echo "   no previous images to roll back to (first deploy?). Stack left up for inspection."
  fi
  exit 1
fi

echo "==> deploy ($ENVN) complete."
