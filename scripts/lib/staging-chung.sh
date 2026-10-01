# shellcheck shell=bash
# Phần DÙNG CHUNG của các script staging (01/10/2026). `source`, không chạy.
#
#   scripts/staging-dung-lan-dau.sh   dựng lần đầu (chạy lại được)
#   scripts/staging-nap-ban-sao.sh    nạp bản sao lưu prod + che dữ liệu khách
#   scripts/deploy-staging.sh         đưa một nhánh / PR lên staging
#
# Mọi tên ở đây đều là tên CỦA STAGING; các hàm `kiem_*` dừng ngay nếu thấy một
# tên của prod — một script staging trỏ nhầm sang database phòng khám là kiểu
# hỏng không chữa được.

STAGING_KIEU="${STAGING_KIEU:-chung}"           # chung | rieng (VPS riêng)
STG_APP_PROJECT="${STG_APP_PROJECT:-clinicai_staging}"
STG_SB_PROJECT="${STG_SB_PROJECT:-clinicai_stg_db}"
STG_PREFIX="${STG_PREFIX:-clinicai_stg}"
STG_DB="${STG_DB_CONTAINER:-${STG_PREFIX}_db}"
STG_SB_NETWORK="${STG_SB_NETWORK:-${STG_SB_PROJECT}_supabase}"
STAGING_EDGE_NETWORK="${STAGING_EDGE_NETWORK:-clinicai_staging_edge}"
STAGING_DEPLOY_LOCK="${STAGING_DEPLOY_LOCK:-/tmp/clinicai-staging-deploy.lock}"
STAGING_TEN_MIEN="${STAGING_TEN_MIEN:-staging.dr4women.io.vn}"

# Tên của PROD — chỉ để SO SÁNH (cấm trùng) và để đọc: sổ migration (SELECT),
# khoá deploy (có thì staging nhường), Caddy (nối vào mạng cầu).
PROD_DB_CONTAINER="${PROD_DB_CONTAINER:-clinicai_db}"
PROD_APP_PROJECT="${PROD_APP_PROJECT:-clinicai_prod}"
PROD_SB_NETWORK="${PROD_SB_NETWORK:-clinicai_db_supabase}"
PROD_DEPLOY_LOCK="${PROD_DEPLOY_LOCK:-/tmp/clinicai-deploy.lock}"
PROD_DIR="${PROD_DIR:-$HOME/clinicai}"

# Chốt tài nguyên khi chạy chung máy với prod (Tuyền chốt 01/10/2026).
STG_RAM_TOI_THIEU_MB="${STG_RAM_TOI_THIEU_MB:-2560}"
STG_DIA_TOI_THIEU_GB="${STG_DIA_TOI_THIEU_GB:-8}"

buoc() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
xong() { printf '\033[32m    %s\033[0m\n' "$*"; }
canh() { printf '\033[33m!! %s\033[0m\n' "$*" >&2; }
dung() { printf '\033[31m!! DỪNG: %s\033[0m\n' "$*" >&2; exit 1; }

# env_get FILE KEY — giá trị đầu tiên, bỏ nháy. Không in giá trị bí mật ra màn.
env_get() {
    grep -E "^${2}=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r"' || true
}

compose_sb() {
    docker compose --env-file "$STAGING_ENV_FILE" \
        -f "$STAGING_DIR/docker-compose.supabase.yml" \
        -f "$STAGING_DIR/docker-compose.supabase.staging.yml" \
        -p "$STG_SB_PROJECT" "$@"
}

compose_app() {
    CLINIC_ENV_FILE="$STAGING_ENV_FILE" docker compose --env-file "$STAGING_ENV_FILE" \
        -f "$STAGING_DIR/docker-compose.yml" \
        -f "$STAGING_DIR/docker-compose.staging.yml" \
        -p "$STG_APP_PROJECT" "$@"
}

# ── Chốt TÊN: không tên nào của staging được trùng prod ──────────────────────
kiem_ten_staging() {
    [ "$STG_PREFIX" != "clinicai" ] || dung "STG_PREFIX=clinicai là tiền tố container của PROD."
    [ "$STG_DB" != "$PROD_DB_CONTAINER" ] || dung "database đích $STG_DB là database PROD."
    [ "$STG_SB_PROJECT" != "clinicai_db" ] || dung "STG_SB_PROJECT=clinicai_db là bộ Supabase PROD."
    [ "$STG_APP_PROJECT" != "$PROD_APP_PROJECT" ] || dung "STG_APP_PROJECT trùng project prod."
    [ "$STG_SB_NETWORK" != "$PROD_SB_NETWORK" ] || dung "mạng Supabase staging trùng mạng PROD."
    case "$STAGING_KIEU" in chung|rieng) ;; *) dung "STAGING_KIEU phải là chung hoặc rieng (đang: $STAGING_KIEU)";; esac
}

# ── Chốt ENV: .env.staging đúng là của staging, không mang khoá thật ─────────
kiem_env_staging() {
    local f="$STAGING_ENV_FILE" k v
    [ -f "$f" ] || dung "thiếu $f (staging-dung-lan-dau.sh sinh tệp này)."
    [ "$(env_get "$f" APP_ENV)" = "staging" ] || dung "APP_ENV trong $f phải là staging."
    [ "$(env_get "$f" COMPOSE_PROJECT_NAME)" = "$STG_APP_PROJECT" ] || dung "COMPOSE_PROJECT_NAME phải là $STG_APP_PROJECT."
    [ "$(env_get "$f" IMAGE_TAG)" = "staging" ] || dung "IMAGE_TAG phải là staging (ảnh prod mang tag prod — không được đè)."
    [ "$(env_get "$f" SUPABASE_PREFIX)" = "$STG_PREFIX" ] || dung "SUPABASE_PREFIX phải là $STG_PREFIX."
    [ "$(env_get "$f" SUPABASE_NETWORK)" = "$STG_SB_NETWORK" ] || dung "SUPABASE_NETWORK phải là $STG_SB_NETWORK."
    [ "$(env_get "$f" SUPABASE_GATEWAY_HOST)" = "${STG_PREFIX}_supabase_gateway" ] || dung "SUPABASE_GATEWAY_HOST phải là ${STG_PREFIX}_supabase_gateway."
    [ "$(env_get "$f" AUTH_GUARD_HOST)" = "${STG_PREFIX}_auth_guard" ] || dung "AUTH_GUARD_HOST phải là ${STG_PREFIX}_auth_guard."
    case "$(env_get "$f" DATABASE_URL)" in
        *"@${STG_DB}:"*) ;;
        *) dung "DATABASE_URL trong $f phải trỏ ${STG_DB}." ;;
    esac
    for k in SUPABASE_DB_PORT SUPABASE_API_PORT; do
        v="$(env_get "$f" "$k")"
        case "$v" in 54321|54322|"") dung "$k=$v trùng cổng prod hoặc rỗng." ;; esac
    done
    for k in SUPABASE_JWT_SECRET SUPABASE_DB_PASSWORD BACKEND_API_KEY SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY; do
        v="$(env_get "$f" "$k")"
        [ -n "$v" ] && [[ "$v" != *"<"* ]] || dung "$k rỗng hoặc còn là chỗ trống mẫu."
        if [ -f "$PROD_DIR/.env.prod" ] && [ "$v" = "$(env_get "$PROD_DIR/.env.prod" "$k")" ]; then
            dung "$k của staging TRÙNG prod — token của bên này sẽ dùng được ở bên kia."
        fi
    done
    # Khoá gửi tin / tích hợp THẬT không được có mặt: staging mà gửi Zalo cho
    # khách thật (dữ liệu đã che thì số giả — nhưng vẫn là số của AI ĐÓ).
    for k in TELEGRAM_BOT_TOKEN ZALO_ZNS_ACCESS_TOKEN TUNNEL_TOKEN SENTRY_DSN RABBITMQ_URL; do
        [ -z "$(env_get "$f" "$k")" ] || dung "$k phải RỖNG ở staging."
    done
    case "$(env_get "$f" POS_ADAPTER)" in ""|none) ;; *) dung "POS_ADAPTER phải là none ở staging." ;; esac
    case "$(env_get "$f" ANTHROPIC_API_KEY)" in sk-ant-api*) dung "ANTHROPIC_API_KEY ở staging phải là khoá giả." ;; esac
    [ "$(env_get "$f" NOTIFICATION_RELAY_ENABLED)" != "true" ] || dung "NOTIFICATION_RELAY_ENABLED phải tắt ở staging."
}

# ── Chốt DATABASE: container đích đúng là Postgres của bộ staging ────────────
kiem_db_la_staging() {
    local c="${1:-$STG_DB}" proj mang
    [ "$c" != "$PROD_DB_CONTAINER" ] || dung "$c là database PROD."
    docker inspect "$c" >/dev/null 2>&1 || dung "không có container $c."
    proj="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$c")"
    [ "$proj" = "$STG_SB_PROJECT" ] || dung "$c thuộc compose project '$proj', không phải $STG_SB_PROJECT."
    mang="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$c")"
    case " $mang " in *" $PROD_SB_NETWORK "*) dung "$c đang nối vào mạng PROD $PROD_SB_NETWORK." ;; esac
}

# ── Chốt TÀI NGUYÊN (chỉ kiểu chung): prod không bao giờ phải nhường ─────────
kiem_tai_nguyen() {
    [ "$STAGING_KIEU" = "chung" ] || return 0
    if [ -e "$PROD_DEPLOY_LOCK" ]; then
        dung "prod đang deploy ($PROD_DEPLOY_LOCK) — staging nhường, chạy lại sau."
    fi
    if [ -r /proc/meminfo ]; then
        local con_mb
        con_mb=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
        [ "${con_mb:-0}" -ge "$STG_RAM_TOI_THIEU_MB" ] || \
            dung "RAM khả dụng ${con_mb}MB < ${STG_RAM_TOI_THIEU_MB}MB — không dựng staging lúc này (prod cần chỗ)."
        xong "RAM khả dụng ${con_mb}MB (ngưỡng ${STG_RAM_TOI_THIEU_MB}MB)"
    else
        canh "không đọc được /proc/meminfo (máy dev?) — bỏ qua chốt RAM."
    fi
    local con_gb
    con_gb=$(df -Pk "$STAGING_DIR" | awk 'NR==2{print int($4/1048576)}')
    [ "${con_gb:-0}" -ge "$STG_DIA_TOI_THIEU_GB" ] || \
        dung "đĩa còn ${con_gb}G < ${STG_DIA_TOI_THIEU_GB}G — không dựng staging (đầy đĩa là prod chết)."
    xong "đĩa còn ${con_gb}G (ngưỡng ${STG_DIA_TOI_THIEU_GB}G)"
}

# ── Mạng cầu Caddy prod ↔ Caddy staging ──────────────────────────────────────
tao_mang_cau() {
    docker network inspect "$STAGING_EDGE_NETWORK" >/dev/null 2>&1 || \
        docker network create --driver bridge \
            --label clinicai.vai=cau-caddy-prod-staging "$STAGING_EDGE_NETWORK" >/dev/null
}

# Nối Caddy prod vào mạng cầu — KHÔNG alias, KHÔNG khởi động lại (đi ngay).
# Mất khi container Caddy prod bị TẠO LẠI; deploy-backend.sh nối lại sau mỗi
# lần deploy prod, script staging cũng gọi lại hàm này mỗi lần chạy.
noi_caddy_prod_vao_cau() {
    [ "$STAGING_KIEU" = "chung" ] || return 0
    local cid mang
    cid="$(docker ps -q --filter "label=com.docker.compose.project=${PROD_APP_PROJECT}" \
        --filter "label=com.docker.compose.service=caddy" | head -1)"
    [ -n "$cid" ] || { canh "không thấy Caddy prod đang chạy — site staging chưa vào được từ ngoài."; return 0; }
    mang="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$cid")"
    case " $mang " in
        *" $STAGING_EDGE_NETWORK "*) xong "Caddy prod đã ở mạng cầu $STAGING_EDGE_NETWORK" ;;
        *) docker network connect "$STAGING_EDGE_NETWORK" "$cid" && \
               xong "đã nối Caddy prod vào mạng cầu $STAGING_EDGE_NETWORK (không khởi động lại)" ;;
    esac
}

# Container của một dịch vụ compose (theo nhãn, không đoán tên).
cid_dich_vu() {
    docker ps -aq --filter "label=com.docker.compose.project=$1" \
        --filter "label=com.docker.compose.service=$2" | head -1
}
