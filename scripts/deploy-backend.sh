#!/bin/bash
# Deploy the ClinicAI self-host stack on the Mac mini.
#   ./scripts/deploy-backend.sh prod      # branch main  → prod stack    (Supabase prod)
#   ./scripts/deploy-backend.sh staging   # tag staging-* → staging stack (Supabase staging)
#
# Flow (spec Phase 5/7): verify exact source → build → up → health → rollback.
# CLINIC_ENV_DIR may point at a separate secrets directory (used by CI checkouts).
# DB migrations are NOT run here — apply schema separately + reviewed via Supabase CLI
# (`supabase db push`). Decoupling schema from code deploy keeps deploys safe.
set -euo pipefail

ENVN="${1:-}"
case "$ENVN" in
  prod) EXPECTED_REF="branch main"; EXPECTED_APP_ENV="production" ;;
  staging) EXPECTED_REF="tag staging-*"; EXPECTED_APP_ENV="staging" ;;
  *) echo "usage: $0 [prod|staging]" >&2; exit 2 ;;
esac

# Trunk-based (see CLAUDE.md): `main` is the only long-lived branch, and staging
# deploys a tag. So the source check below is on a ref PATTERN, not a branch
# name — a tag checkout is a detached HEAD and has no branch to compare at all.
ref_is_expected() {
  case "$ENVN:$1" in
    prod:main) return 0 ;;
    staging:staging-*) return 0 ;;
    *) return 1 ;;
  esac
}

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
  if [ -n "${DEPLOY_SOURCE_REF:-}" ] && ! ref_is_expected "$DEPLOY_SOURCE_REF"; then
    echo "!! $ENVN must deploy from $EXPECTED_REF, not $DEPLOY_SOURCE_REF" >&2
    exit 1
  fi
else
  PINNED_CHECKOUT=0
  CURRENT_REF="$(git branch --show-current)"
  if [ -z "$CURRENT_REF" ]; then
    # Detached HEAD — the normal shape of a staging deploy. Accept it only when
    # HEAD sits exactly on a tag, so the release has a name a human can say out
    # loud in the runbook, not just a SHA nobody will recognise later.
    CURRENT_REF="$(git describe --tags --exact-match HEAD 2>/dev/null || true)"
  fi
  ref_is_expected "$CURRENT_REF" || {
    echo "!! $ENVN must deploy from $EXPECTED_REF (currently ${CURRENT_REF:-detached, not on a tag})" >&2
    exit 1
  }
  # Preserve the old manual workflow, but never continue with stale code. Only a
  # branch can fall behind; a tag is already the exact commit that was tested.
  if [ "$ENVN" = "prod" ]; then
    git pull --ff-only
  fi
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

profile_enabled() {
  case ",${1// /}," in *",$2,"*) return 0 ;; *) return 1 ;; esac
}

# Reconcile every intentionally enabled optional service as part of the same
# release. This prevents workers/relay/tunnel containers from remaining on an
# old image merely because Compose profiles are opt-in.
ENABLED_PROFILES="$(env_value COMPOSE_PROFILES)"
if [ -n "$(env_value TUNNEL_TOKEN)" ]; then
  ENABLED_PROFILES="${ENABLED_PROFILES:+${ENABLED_PROFILES},}cloudflare"
fi
if profile_enabled "$ENABLED_PROFILES" workers; then
  for required in RABBITMQ_PASSWORD RABBITMQ_URL; do
    value="$(env_value "$required")"
    if [ -z "$value" ] || [[ "$value" == *"<"* ]]; then
      echo "!! workers profile requires a non-placeholder $required in $ENV_FILE" >&2
      exit 1
    fi
  done
fi
if [ -n "$ENABLED_PROFILES" ]; then
  export COMPOSE_PROFILES="$ENABLED_PROFILES"
else
  unset COMPOSE_PROFILES 2>/dev/null || true
fi

"${COMPOSE[@]}" config --quiet

# ── Thư mục ổ bind phải TỒN TẠI TRƯỚC, và thuộc về người deploy ──────────────
#
# CHUYỆN ĐÃ XẢY RA (đo 08/08/2026). `.media/production` không tồn tại lúc `up`
# đầu tiên, nên Docker tự tạo nó — bằng quyền của daemon, tức **root**, chế độ
# 755. Container thì chạy bằng `appuser` (uid 1000). Kết quả:
#
#     docker exec … touch /var/lib/clinicai/media/x  →  Permission denied
#
# Backend KHÔNG GHI NỔI một tấm ảnh siêu âm nào, suốt từ ngày dựng. Và nó hỏng
# im lặng theo kiểu tệ nhất: không ai upload nên không ai gặp lỗi, cho tới hôm
# tính năng được bật lên và mọi lần tải đều trả 500.
#
# `mkdir -p` chạy bằng chính người deploy (uid 1000 = appuser trong ảnh) nên
# Docker gắn vào một thư mục đã có, đúng chủ. Chạy lại bao nhiêu lần cũng không
# đổi gì thêm.
MEDIA_BIND="$(env_value MEDIA_DIR)"
MEDIA_BIND="${MEDIA_BIND:-./.media}"
OPS_BIND="$(env_value OPS_STATUS_DIR)"
OPS_BIND="${OPS_BIND:-./.ops-status}"
APP_ENV_VALUE="$(env_value APP_ENV)"
for d in "${MEDIA_BIND}/${APP_ENV_VALUE}" "${OPS_BIND}/${APP_ENV_VALUE}"; do
  case "$d" in
    "~/"*) d="$HOME/${d#\~/}" ;;
    /*) : ;;
    *) d="${REPO}/${d#./}" ;;
  esac
  mkdir -p "$d" || {
    echo "!! không tạo được thư mục ổ bind: $d" >&2
    exit 1
  }
done

# ── Lược đồ có đi trước code không ────────────────────────────────────────────
#
# CHUYỆN ĐÃ XẢY RA (06/08). Deploy một bản code đọc tám cột mới của bảng `staff`
# trong khi migration tạo chúng CHƯA được áp. Kết quả: `/api/v1/staff` trả 500,
# màn Quản lý nhân sự trắng — và không có gì trong quy trình deploy nói ra, vì
# health check vẫn xanh: `/health` không chạm bảng đó.
#
# Tách lược đồ khỏi deploy là quyết định ĐÚNG (xem đầu file): schema cần người
# xem, deploy thì không. Nhưng tách mà không kiểm nghĩa là thứ tự đúng phụ thuộc
# vào trí nhớ của người bấm.
#
# CẢNH BÁO, KHÔNG CHẶN: có lần deploy cố ý đi trước migration (code mới chưa
# dùng cột mới). Nhưng nó phải nói ra, và nói TRƯỚC khi dựng ảnh.
if [ -n "${CLINIC_DB_CONTAINER:-}" ]; then
  _applied="$(docker exec "$CLINIC_DB_CONTAINER" \
      psql -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" \
      -tAc "SELECT version FROM supabase_migrations.schema_migrations" \
      2>/dev/null || true)"
  if [ -n "$_applied" ]; then
    _missing=""
    for _f in "$REPO/supabase/migrations"/*.sql; do
      [ -e "$_f" ] || continue
      _v="$(basename "$_f" | cut -d_ -f1)"
      if ! printf '%s\n' "$_applied" | tr -d ' \r' | grep -qx "$_v"; then
        _missing="$_missing $_v"
      fi
    done
    if [ -n "$_missing" ]; then
      echo ""
      echo "  !! LƯỢC ĐỒ ĐANG ĐI SAU CODE. Migration chưa áp:$_missing"
      echo "     Nếu bản code này đọc cột mới thì endpoint dùng nó sẽ trả 500,"
      echo "     và health check vẫn xanh vì /health không chạm bảng đó."
      echo "     Áp trước: ./scripts/apply-pending-migrations.sh --apply"
      echo ""
    fi
  fi
fi

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
# `set -e` would abort the whole script here, which skips the rollback below and
# leaves production DOWN — the one outcome the rollback exists to prevent. A new
# release that cannot even start is exactly when the previous one is needed, so
# the failure is captured and handled instead of ending the run.
UP_OK=1
"${COMPOSE[@]}" up -d || UP_OK=0
if [ "$UP_OK" != "1" ]; then
  echo "!! compose up FAILED for the new release"
fi

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

if [ "$UP_OK" = "1" ] && wait_for_health; then DEPLOY_OK=1; fi

if [ "${DEPLOY_OK:-0}" != "1" ]; then
  if [ "$UP_OK" = "1" ]; then
    echo "!! health check FAILED — rolling back"
  else
    echo "!! new release would not start — rolling back"
  fi
  if [ -n "$OLD_API" ] && [ -n "$OLD_DASH" ] && [ -n "$PREVIOUS_RELEASE" ] && [ -n "$PREVIOUS_ENV_FILE" ]; then
    docker tag "$OLD_API"  "clinicai-api:${TAG}"
    docker tag "$OLD_DASH" "clinicai-dashboard:${TAG}"
    cd "$PREVIOUS_RELEASE"
    export CLINIC_ENV_FILE="$PREVIOUS_ENV_FILE"
    ENABLED_PROFILES="$PREVIOUS_PROFILES"
    if [ -n "$ENABLED_PROFILES" ]; then export COMPOSE_PROFILES="$ENABLED_PROFILES"; else unset COMPOSE_PROFILES 2>/dev/null || true; fi
    COMPOSE=(docker compose --env-file "$PREVIOUS_ENV_FILE" -p "$PROJECT")
    remove_disabled_services
    # Same reason as the release `up` above: if the ROLLBACK cannot start
    # either, `set -e` would kill the script mid-recovery and the operator would
    # see no explanation at all. Say what happened — this is the worst case and
    # the one where a clear message matters most.
    ROLLBACK_UP_OK=1
    "${COMPOSE[@]}" up -d || ROLLBACK_UP_OK=0
    if [ "$ROLLBACK_UP_OK" != "1" ]; then
      echo "!! rollback compose up failed — the stack is DOWN, intervene manually" >&2
    elif wait_for_health; then
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

# DỌN BỘ NHỚ TẠM CỦA TRÌNH DỰNG ẢNH — sau khi đã xác minh xong, không sớm hơn.
#
# Mỗi lần deploy là một lần `compose build`, và Docker giữ lại mọi lớp trung
# gian của mọi lần dựng. Ngày 08/08/2026 đo trên VPS: 408 mục, **30,03 GB**,
# không mục nào đang dùng — chiếm 30 trong 33 GB đã dùng của cả ổ đĩa. Đĩa còn
# 15 GB và đang tiến đều tới 0, mà không có gì cảnh báo: `df` không biết phân
# biệt "dữ liệu bệnh nhân" với "rác của lần dựng tuần trước".
#
# Đặt SAU bước xác minh, vì nếu đứng trước thì lần rollback ngay sau đó phải
# dựng lại từ đầu — đúng lúc đang hỏng và đang vội.
#
# `|| true`: dọn rác thất bại không phải lý do để gọi một bản deploy đã chạy
# tốt là hỏng.
truoc=$(docker system df --format '{{.Type}}|{{.Size}}' 2>/dev/null | awk -F'|' '/^Build/{print $2}')
docker builder prune -af --filter 'until=24h' >/dev/null 2>&1 || true
echo "==> dọn bộ nhớ tạm của trình dựng (trước: ${truoc:-?}); đĩa còn: $(df -h / | awk 'NR==2{print $4}')"
echo "==> deploy ($ENVN) complete."
