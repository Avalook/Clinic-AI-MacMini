#!/usr/bin/env bash
# ĐƯA MỘT NHÁNH / PR LÊN STAGING để mọi người thử TRƯỚC prod (01/10/2026).
#
# Chạy TRÊN máy staging, từ thư mục staging (~/clinicai-staging):
#
#   ./scripts/deploy-staging.sh              # main
#   ./scripts/deploy-staging.sh 301          # PR số 301 (refs/pull/301/head)
#   ./scripts/deploy-staging.sh claude/abc   # một nhánh
#
# KHÔNG ĐỤNG PROD:
#   • project compose riêng (clinicai_staging), ảnh riêng (tag :staging — ảnh
#     prod mang tag :prod), khoá deploy riêng (/tmp/clinicai-staging-deploy.lock).
#   • Prod đang deploy (/tmp/clinicai-deploy.lock) → staging NHƯỜNG, dừng ngay.
#   • RAM khả dụng < 2,5G hoặc đĩa < 8G → không dựng.
#   • Dựng ảnh bằng builder RIÊNG (buildx, driver docker-container) có TRẦN RAM
#     và cpu-shares thấp. `nice`/`ionice` ở máy khách KHÔNG đủ: `docker build`
#     chỉ gửi lệnh, việc dựng chạy trong dockerd/buildkitd với ưu tiên của nó —
#     nên trần phải đặt lên chính container buildkitd. Client vẫn chạy dưới
#     `nice -n 19 ionice -c3` cho phần nén/gửi ngữ cảnh.
#   • Sau deploy: dọn ảnh staging cũ (chỉ ảnh mang nhãn project staging) và bộ
#     nhớ tạm của builder staging.
#
# Migration: nhánh có migration mới thì chạy thêm
#   CLINIC_DB_CONTAINER=clinicai_stg_db ./scripts/apply-pending-migrations.sh --apply
# (staging-nap-ban-sao.sh mỗi đêm cũng tự áp). Database staging, không phải prod.

set -euo pipefail

STAGING_DIR="${STAGING_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STAGING_ENV_FILE="${STAGING_ENV_FILE:-$STAGING_DIR/.env.staging}"
# shellcheck source=lib/staging-chung.sh
. "$STAGING_DIR/scripts/lib/staging-chung.sh"

# TRẦN RAM CỦA BUILDER — đo 01/10/2026: `next build` (Turbopack) đỉnh 2,6GiB
# (tổng cây tiến trình, máy 10 nhân); trong builder trần 1,4G trên 4 nhân thì
# bị giết sau 10 giây (SIGKILL, "cannot allocate memory") — hỏng NHANH, prod
# không sao. Mặc định 3g; tên builder mang trần để đổi trần là builder mới.
STG_BUILDER_RAM="${STG_BUILDER_RAM:-3g}"
STG_BUILDER="${STG_BUILDER:-clinicai-staging-builder-$STG_BUILDER_RAM}"
# Phần RAM luôn chừa cho prod TRONG LÚC dựng (ngoài trần builder).
STG_RAM_CHUA_PROD_MB="${STG_RAM_CHUA_PROD_MB:-768}"
STG_BUILDER_CPU_SHARES="${STG_BUILDER_CPU_SHARES:-128}"
REF="${1:-main}"
NICE=(nice -n 19)
command -v ionice >/dev/null 2>&1 && NICE+=(ionice -c3)

cd "$STAGING_DIR"
kiem_ten_staging
[ "$(cd "$STAGING_DIR" && pwd -P)" != "$(cd "$PROD_DIR" 2>/dev/null && pwd -P)" ] || \
    dung "đang đứng trong thư mục PROD ($PROD_DIR). Staging ở ~/clinicai-staging."

if ! mkdir "$STAGING_DEPLOY_LOCK" 2>/dev/null; then
    dung "staging đang deploy/nạp ($STAGING_DEPLOY_LOCK)."
fi
DA_DUNG_APP=0
don_dep() {
    # Hỏng giữa chừng (dựng ảnh bị giết vì hết RAM…) sau khi đã tắt staging để
    # dựng → bật lại bản đang có, đừng để staging tắt hẳn.
    if [ "$DA_DUNG_APP" = "1" ]; then
        canh "deploy dừng giữa chừng — bật lại staging bằng ảnh đang có"
        compose_app up -d --no-build >/dev/null 2>&1 || true
    fi
    rmdir "$STAGING_DEPLOY_LOCK" 2>/dev/null || true
}
trap don_dep EXIT INT TERM

buoc "1/6  Chốt tài nguyên + nguồn code"
kiem_tai_nguyen
if [ "${STAGING_TAI_CHO:-0}" = "1" ]; then
    # staging-dung-lan-dau.sh đã checkout sẵn — dựng đúng chỗ đang đứng.
    SHA="$(git rev-parse HEAD)"
    NGUON="(tại chỗ)"
else
    case "$REF" in
        ''|*[!0-9]*) git fetch -q origin "$REF"; NGUON="nhánh/tag $REF" ;;
        *)           git fetch -q origin "pull/$REF/head"; NGUON="PR #$REF" ;;
    esac
    SHA="$(git rev-parse FETCH_HEAD)"
    # Tách rời ở đúng commit; tệp không theo git (.env.staging) giữ nguyên.
    git checkout -q --detach -f "$SHA"
fi
xong "$NGUON → $(git log --oneline -1 "$SHA")"
kiem_env_staging

buoc "2/6  Builder riêng của staging (trần RAM $STG_BUILDER_RAM, cpu-shares $STG_BUILDER_CPU_SHARES)"
BUILDER_ARGS=()
if docker buildx inspect "$STG_BUILDER" >/dev/null 2>&1 || \
   docker buildx create --name "$STG_BUILDER" --driver docker-container \
       --driver-opt "memory=$STG_BUILDER_RAM" --driver-opt "memory-swap=$STG_BUILDER_RAM" \
       --driver-opt "cpu-shares=$STG_BUILDER_CPU_SHARES" >/dev/null 2>&1; then
    BUILDER_ARGS=(--builder "$STG_BUILDER")
    xong "dùng builder $STG_BUILDER"
else
    canh "không tạo được builder riêng — dựng bằng builder mặc định (KHÔNG có trần RAM)."
fi

buoc "3/6  Dựng ảnh clinicai-api:staging + clinicai-dashboard:staging"
tao_mang_cau
# Dừng ứng dụng staging trong lúc dựng (staging tạm tắt vài phút — chấp nhận)
# để trả RAM, rồi kiểm: RAM khả dụng ≥ trần builder + phần chừa cho prod.
for svc in caddy dashboard su-kien api; do
    c="$(docker ps -q --filter "label=com.docker.compose.project=$STG_APP_PROJECT" \
        --filter "label=com.docker.compose.service=$svc" | head -1)"
    [ -z "$c" ] || { docker stop "$c" >/dev/null; DA_DUNG_APP=1; }
done
if [ "$STAGING_KIEU" = "chung" ] && [ -r /proc/meminfo ]; then
    case "$STG_BUILDER_RAM" in
        *g|*G) TRAN_MB=$(( ${STG_BUILDER_RAM%[gG]} * 1024 )) ;;
        *m|*M) TRAN_MB=${STG_BUILDER_RAM%[mM]} ;;
        *)     TRAN_MB=3072 ;;
    esac
    CAN_MB=$(( TRAN_MB + STG_RAM_CHUA_PROD_MB ))
    [ "$CAN_MB" -ge "$STG_RAM_TOI_THIEU_MB" ] || CAN_MB=$STG_RAM_TOI_THIEU_MB
    CON_MB=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
    if [ "${CON_MB:-0}" -lt "$CAN_MB" ]; then
        dung "RAM khả dụng ${CON_MB}MB < ${CAN_MB}MB (builder $STG_BUILDER_RAM + chừa prod ${STG_RAM_CHUA_PROD_MB}MB) — không dựng; đã bật lại staging cũ."
    fi
    xong "RAM khả dụng ${CON_MB}MB ≥ ${CAN_MB}MB — dựng"
fi
OLD_API="$(docker image inspect -f '{{.Id}}' clinicai-api:staging 2>/dev/null || true)"
OLD_DASH="$(docker image inspect -f '{{.Id}}' clinicai-dashboard:staging 2>/dev/null || true)"
compose_app config --quiet
BAT_DAU=$(date +%s)
# Dựng TỪNG ảnh một (không song song): hai bước nặng — `next build` và cài gói
# Python — chạy cùng lúc trong cùng trần RAM của builder là cùng tranh nhau đỉnh.
for svc in api dashboard; do
    "${NICE[@]}" env CLINIC_ENV_FILE="$STAGING_ENV_FILE" docker compose --env-file "$STAGING_ENV_FILE" \
        -f "$STAGING_DIR/docker-compose.yml" -f "$STAGING_DIR/docker-compose.staging.yml" \
        -p "$STG_APP_PROJECT" build ${BUILDER_ARGS[@]+"${BUILDER_ARGS[@]}"} "$svc"
done
xong "dựng xong sau $(( $(date +%s) - BAT_DAU ))s"

buoc "4/6  up -d"
UP_OK=1
compose_app up -d --no-build || UP_OK=0
DA_DUNG_APP=0

buoc "5/6  Kiểm sức khoẻ (tối đa ~150s)"
khoe() {
    local svc cid st
    for svc in api dashboard su-kien caddy; do
        cid="$(cid_dich_vu "$STG_APP_PROJECT" "$svc")"
        [ -n "$cid" ] || return 1
        st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")"
        [ "$st" = "healthy" ] || return 1
    done
}
OK=0
if [ "$UP_OK" = "1" ]; then
    for _ in $(seq 1 30); do khoe && { OK=1; break; }; sleep 5; done
fi
if [ "$OK" = "1" ]; then
    API_CID="$(cid_dich_vu "$STG_APP_PROJECT" api)"
    docker exec "$API_CID" curl -fsS http://localhost:8000/health/db >/dev/null || OK=0
    WEB="$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $STAGING_TEN_MIEN" \
        "http://127.0.0.1:$(env_get "$STAGING_ENV_FILE" CADDY_HTTP_PORT)/login" || echo loi)"
    [ "$WEB" = "200" ] || OK=0
    xong "api /health/db ok · web /login → $WEB"
fi
if [ "$OK" != "1" ]; then
    canh "staging KHÔNG khoẻ sau deploy — quay về ảnh trước"
    if [ -n "$OLD_API" ] && [ -n "$OLD_DASH" ]; then
        docker tag "$OLD_API" clinicai-api:staging
        docker tag "$OLD_DASH" clinicai-dashboard:staging
        compose_app up -d --no-build || true
        canh "đã quay về ảnh trước (code trong thư mục vẫn ở $SHA — deploy lại nhánh cũ nếu cần)."
    fi
    dung "deploy staging hỏng — xem: docker compose -p $STG_APP_PROJECT logs --tail 80 api dashboard"
fi
noi_caddy_prod_vao_cau

buoc "6/6  Dọn ảnh staging cũ + bộ nhớ tạm builder staging"
# Chỉ ảnh treo (dangling) MANG NHÃN project staging — ảnh prod nhãn clinicai_prod.
docker image prune -f --filter "label=com.docker.compose.project=$STG_APP_PROJECT" >/dev/null 2>&1 || true
if [ ${#BUILDER_ARGS[@]} -gt 0 ]; then
    docker buildx prune --builder "$STG_BUILDER" -f --filter 'until=168h' >/dev/null 2>&1 || true
fi
NHAT_KY="${STAGING_STATE_DIR:-$HOME/.local/state}/clinicai-staging-deploy.log"
mkdir -p "$(dirname "$NHAT_KY")" 2>/dev/null || true
printf '%s\t%s\t%s\n' "$(date '+%F %T')" "$NGUON" "$(git log --oneline -1 "$SHA")" >> "$NHAT_KY" 2>/dev/null || true
xong "đĩa còn $(df -h "$STAGING_DIR" | awk 'NR==2{print $4}')"
echo "XONG — https://$STAGING_TEN_MIEN đang chạy $NGUON @ ${SHA:0:8}"
