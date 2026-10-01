#!/usr/bin/env bash
# DỰNG STAGING ONLINE LẦN ĐẦU (01/10/2026) — chạy lại bao nhiêu lần cũng được.
#
# Chạy TRÊN máy của staging. Kiểu mặc định `chung`: chung VPS với prod
# (clinic-vps-moi), tách hẳn project / container / mạng / database / env.
# Lệnh mồi (từ Mac) — lấy script từ origin, KHÔNG đổi cây code prod:
#
#   ssh clinic-vps-moi "git -C ~/clinicai fetch -q origin && \
#     git -C ~/clinicai show origin/main:scripts/staging-dung-lan-dau.sh > /tmp/stg-dung.sh && \
#     bash /tmp/stg-dung.sh"
#
# CÁC BƯỚC (in từng bước, hỏng là dừng ngay):
#   1. Clone riêng ~/clinicai-staging (đứng tách rời ở STAGING_REF, mặc định main)
#   2. Chốt tài nguyên: RAM khả dụng ≥ 2,5G, đĩa ≥ 8G, prod không đang deploy
#   3. Sinh .env.staging (khoá JWT / DB / API RIÊNG; không khoá gửi tin thật).
#      Đã có thì GIỮ NGUYÊN — sinh lại là đá văng mọi phiên đăng nhập staging.
#   4. Dựng bộ Supabase staging (db, auth, rest, gateway, auth-guard)
#   5. Nạp bản sao lưu prod + che dữ liệu khách (staging-nap-ban-sao.sh)
#   6. Deploy code lên staging (deploy-staging.sh)
#   7. Kiểu chung: thêm site staging vào Caddy prod (caddy/them/staging.caddy) —
#      sao lưu, `caddy validate`, rồi mới khởi động lại Caddy prod (~1–2 giây).
#   8. Bật hẹn giờ nạp lại mỗi đêm 03:30 (systemd)
#
# THỨ DUY NHẤT NÓ ĐỤNG Ở PROD (kiểu chung): ghi caddy/them/staging.caddy (tệp
# không theo git) + nối Caddy prod vào mạng cầu + khởi động lại Caddy prod khi
# site staging mới/đổi. Không đụng container, ảnh, database, env nào khác của prod.
#
# Biến:
#   STAGING_KIEU      chung (mặc định) | rieng
#   STAGING_REF       nhánh/tag để đứng lần đầu (mặc định main)
#   STAGING_DIR       mặc định ~/clinicai-staging
#   STAGING_DATA      mặc định ~/clinicai-staging-data (tệp tải lên của staging)
#   STAGING_TEN_MIEN  mặc định staging.dr4women.io.vn
#   STAGING_REPO_URL  kiểu rieng: địa chỉ git để clone (chung: lấy từ ~/clinicai)
#   BAN_SAO_SSH       kiểu rieng: user@may-prod để kéo bản sao lưu (xem staging-nap-ban-sao.sh)
#   BO_HEN_GIO=1      không cài systemd timer
#   STAGING_DEN_BUOC  dừng sau bước N (thử từng phần; mặc định chạy hết 8 bước)

set -euo pipefail

STAGING_KIEU="${STAGING_KIEU:-chung}"
STAGING_REF="${STAGING_REF:-main}"
STAGING_DIR="${STAGING_DIR:-$HOME/clinicai-staging}"
STAGING_DATA="${STAGING_DATA:-$HOME/clinicai-staging-data}"
STAGING_ENV_FILE="${STAGING_ENV_FILE:-$STAGING_DIR/.env.staging}"
PROD_DIR="${PROD_DIR:-$HOME/clinicai}"
export STAGING_KIEU STAGING_REF STAGING_DIR STAGING_DATA STAGING_ENV_FILE PROD_DIR

in_buoc() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
dung0() { printf '\033[31m!! DỪNG: %s\033[0m\n' "$*" >&2; exit 1; }

# ── 1. Clone riêng của staging ───────────────────────────────────────────────
if [ "${1:-}" != "--da-clone" ]; then
    in_buoc "1/8  Code staging ở $STAGING_DIR (đứng ở $STAGING_REF)"
    case "$STAGING_KIEU" in chung|rieng) ;; *) dung0 "STAGING_KIEU phải là chung hoặc rieng";; esac
    [ "$(cd "$STAGING_DIR" 2>/dev/null && pwd -P)" != "$(cd "$PROD_DIR" 2>/dev/null && pwd -P)" ] || \
        dung0 "STAGING_DIR trùng thư mục prod $PROD_DIR."
    if [ ! -d "$STAGING_DIR/.git" ]; then
        if [ -n "${STAGING_REPO_URL:-}" ]; then
            git clone -q "$STAGING_REPO_URL" "$STAGING_DIR"
        elif [ -d "$PROD_DIR/.git" ]; then
            # Clone từ ổ (nhanh, không cần mạng) rồi trỏ origin về GitHub như prod.
            git clone -q --no-hardlinks "$PROD_DIR" "$STAGING_DIR"
            git -C "$STAGING_DIR" remote set-url origin "$(git -C "$PROD_DIR" remote get-url origin)"
        else
            dung0 "không có $PROD_DIR/.git — đặt STAGING_REPO_URL để clone."
        fi
    fi
    # Prod tải code bằng khoá chỉ-đọc riêng (core.sshCommand trong .git/config của
    # prod) — bản clone không mang theo cấu hình ấy → "Permission denied
    # (publickey)" ở bước fetch (lần dựng đầu 01/10/2026). Chép đúng khoá prod dùng.
    if [ -z "$(git -C "$STAGING_DIR" config --get core.sshCommand || true)" ] \
       && [ -n "$(git -C "$PROD_DIR" config --get core.sshCommand 2>/dev/null || true)" ]; then
        git -C "$STAGING_DIR" config core.sshCommand "$(git -C "$PROD_DIR" config --get core.sshCommand)"
    fi
    git -C "$STAGING_DIR" fetch -q origin
    if git -C "$STAGING_DIR" rev-parse -q --verify "origin/$STAGING_REF^{commit}" >/dev/null; then
        SHA="$(git -C "$STAGING_DIR" rev-parse "origin/$STAGING_REF")"
    else
        SHA="$(git -C "$STAGING_DIR" rev-parse "$STAGING_REF^{commit}")"
    fi
    git -C "$STAGING_DIR" checkout -q --detach -f "$SHA"
    echo "    $(git -C "$STAGING_DIR" log --oneline -1)"
    # Chạy tiếp bằng BẢN SCRIPT TRONG CLONE — cùng phiên bản với code sẽ dựng.
    exec bash "$STAGING_DIR/scripts/staging-dung-lan-dau.sh" --da-clone
fi

cd "$STAGING_DIR"
# shellcheck source=lib/staging-chung.sh
. "$STAGING_DIR/scripts/lib/staging-chung.sh"
kiem_ten_staging
den_buoc() { [ "${STAGING_DEN_BUOC:-8}" -gt "$1" ] || { echo "(dừng sau bước $1 theo STAGING_DEN_BUOC)"; exit 0; }; }

# ── 2. Chốt tài nguyên ───────────────────────────────────────────────────────
buoc "2/8  Chốt tài nguyên (kiểu $STAGING_KIEU)"
kiem_tai_nguyen

den_buoc 2

# ── 3. .env.staging ──────────────────────────────────────────────────────────
buoc "3/8  .env.staging"
mkdir -p "$STAGING_DATA/media" "$STAGING_DATA/media-vps" "$STAGING_DATA/ops-status"
if [ -f "$STAGING_ENV_FILE" ]; then
    xong "đã có — giữ nguyên (sinh lại = mọi phiên đăng nhập staging bị đá ra)"
else
    KHOA="$(python3 "$STAGING_DIR/scripts/sinh-khoa-supabase.py")"
    lay() { printf '%s\n' "$KHOA" | sed -n "s/^$1=//p" | head -1; }
    DB_PASS="$(lay SUPABASE_DB_PASSWORD)"
    if [ "$STAGING_KIEU" = "rieng" ]; then
        SITE="$STAGING_TEN_MIEN"; BIND=0.0.0.0; HTTP=80; HTTPS=443
    else
        SITE=":80"; BIND=127.0.0.1; HTTP=8080; HTTPS=8443
    fi
    # Cờ NGHIỆP VỤ chép từ prod để staging cư xử y hệt (không chép bí mật nào).
    AI_GIA="sk-staging-khong-phai-khoa-that"   # khoá GIẢ — staging không gọi AI thật
    co_prod() { [ -f "$PROD_DIR/.env.prod" ] && env_get "$PROD_DIR/.env.prod" "$1" || true; }
    umask 077
    {
        echo "# STAGING — sinh bởi scripts/staging-dung-lan-dau.sh lúc $(date '+%F %T')."
        echo "# BÍ MẬT RIÊNG CỦA STAGING. Không chép sang prod, không dán vào chat."
        echo "APP_ENV=staging"
        echo "COMPOSE_PROJECT_NAME=$STG_APP_PROJECT"
        echo "IMAGE_TAG=staging"
        echo "COMPOSE_PROFILES="
        echo "SITE_ADDRESS=$SITE"
        echo "SITE_URL=https://$STAGING_TEN_MIEN"
        echo "CADDY_BIND_ADDRESS=$BIND"
        echo "CADDY_HTTP_PORT=$HTTP"
        echo "CADDY_HTTPS_PORT=$HTTPS"
        echo "CADDY_FILE=./caddy/Caddyfile.staging"
        echo "STAGING_EDGE_NETWORK=$STAGING_EDGE_NETWORK"
        echo "SUPABASE_PREFIX=$STG_PREFIX"
        echo "SUPABASE_NETWORK=$STG_SB_NETWORK"
        echo "SUPABASE_GATEWAY_HOST=${STG_PREFIX}_supabase_gateway"
        echo "AUTH_GUARD_HOST=${STG_PREFIX}_auth_guard"
        echo "SUPABASE_DB_PORT=54332"
        echo "SUPABASE_API_PORT=54331"
        echo "SUPABASE_JWT_SECRET=$(lay SUPABASE_JWT_SECRET)"
        echo "SUPABASE_DB_PASSWORD=$DB_PASS"
        echo "SUPABASE_ANON_KEY=$(lay SUPABASE_ANON_KEY)"
        echo "SUPABASE_SERVICE_ROLE_KEY=$(lay SUPABASE_SERVICE_ROLE_KEY)"
        echo "NEXT_PUBLIC_SUPABASE_URL=https://$STAGING_TEN_MIEN"
        echo "NEXT_PUBLIC_SUPABASE_ANON_KEY=$(lay SUPABASE_ANON_KEY)"
        echo "SUPABASE_URL=http://${STG_PREFIX}_supabase_gateway:8000"
        echo "DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASS}@${STG_DB}:5432/postgres"
        echo "BACKEND_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
        echo "CHECKPOINTER_BACKEND=$(co_prod CHECKPOINTER_BACKEND)"
        echo "ANTHROPIC_API_KEY=${AI_GIA}"
        echo "ENABLE_AI_ORCHESTRATOR=false"
        echo "POS_ADAPTER=none"
        echo "MO_QUYEN_TAM_THOI=$(co_prod MO_QUYEN_TAM_THOI)"
        echo "KET_QUA_VIDEO_UPLOAD_ENABLED=$(co_prod KET_QUA_VIDEO_UPLOAD_ENABLED)"
        echo "NOTIFICATION_RELAY_ENABLED=false"
        echo "TELEGRAM_BOT_TOKEN="
        echo "ZALO_ZNS_ACCESS_TOKEN="
        echo "SENTRY_DSN="
        echo "TUNNEL_TOKEN="
        echo "RABBITMQ_URL="
        echo "MEDIA_DIR=$STAGING_DATA/media"
        echo "MEDIA_LOCAL_DIR=$STAGING_DATA/media-vps"
        echo "OPS_STATUS_DIR=$STAGING_DATA/ops-status"
        echo "NEXT_WORKERS=1"
    } > "$STAGING_ENV_FILE"
    chmod 600 "$STAGING_ENV_FILE"
    unset KHOA DB_PASS
    xong "đã sinh $STAGING_ENV_FILE (quyền 600, khoá riêng của staging)"
fi
kiem_env_staging

den_buoc 3

# ── 4. Bộ Supabase staging ───────────────────────────────────────────────────
buoc "4/8  Bộ Supabase staging ($STG_SB_PROJECT)"
tao_mang_cau
compose_sb up -d db auth rest gateway auth-guard
for _ in $(seq 1 60); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "${STG_PREFIX}_auth" 2>/dev/null)" = "healthy" ] && break
    sleep 2
done
[ "$(docker inspect -f '{{.State.Health.Status}}' "${STG_PREFIX}_auth" 2>/dev/null)" = "healthy" ] || \
    dung "GoTrue staging chưa healthy sau 120s — xem: docker logs ${STG_PREFIX}_auth"
kiem_db_la_staging "$STG_DB"
xong "Postgres + GoTrue + PostgREST + gateway staging đã chạy"

den_buoc 4

# ── 5. Nạp bản sao + che ─────────────────────────────────────────────────────
buoc "5/8  Nạp bản sao lưu prod + che dữ liệu khách"
"$STAGING_DIR/scripts/staging-nap-ban-sao.sh"

den_buoc 5

# ── 6. Deploy ────────────────────────────────────────────────────────────────
buoc "6/8  Deploy code lên staging"
STAGING_TAI_CHO=1 "$STAGING_DIR/scripts/deploy-staging.sh"

den_buoc 6

# ── 7. Site staging trên Caddy prod ──────────────────────────────────────────
if [ "$STAGING_KIEU" = "chung" ]; then
    buoc "7/8  Site $STAGING_TEN_MIEN trên Caddy prod"
    CADDY_PROD="$(docker ps -q --filter "label=com.docker.compose.project=${PROD_APP_PROJECT}" \
        --filter "label=com.docker.compose.service=caddy" | head -1)"
    [ -n "$CADDY_PROD" ] || dung "không thấy Caddy prod đang chạy."
    docker exec "$CADDY_PROD" test -d /etc/caddy/them || \
        dung "Caddy prod chưa gắn caddy/them — deploy prod bản có thư mục này trước (PR staging online)."
    THEM="$PROD_DIR/caddy/them"
    [ -d "$THEM" ] || dung "thiếu $THEM — prod chưa ở bản có caddy/them."
    MOI="$(mktemp)"
    sed "s/__STAGING_TEN_MIEN__/$STAGING_TEN_MIEN/" "$STAGING_DIR/caddy/staging-tren-prod.caddy.mau" > "$MOI"
    if [ -f "$THEM/staging.caddy" ] && cmp -s "$MOI" "$THEM/staging.caddy"; then
        xong "site staging đã có, không đổi — không khởi động lại Caddy prod"
        rm -f "$MOI"
    else
        LUC="$(date +%Y%m%d%H%M%S)"
        # Sao lưu trước khi sửa: Caddyfile prod đang chạy + site cũ (nếu có).
        docker exec "$CADDY_PROD" cat /etc/caddy/Caddyfile > "$THEM/Caddyfile.bak.$LUC"
        [ ! -f "$THEM/staging.caddy" ] || cp "$THEM/staging.caddy" "$THEM/staging.caddy.bak.$LUC"
        install -m 644 "$MOI" "$THEM/staging.caddy"
        rm -f "$MOI"
        if ! docker exec "$CADDY_PROD" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1; then
            if [ -f "$THEM/staging.caddy.bak.$LUC" ]; then
                mv "$THEM/staging.caddy.bak.$LUC" "$THEM/staging.caddy"
            else
                rm -f "$THEM/staging.caddy"
            fi
            dung "caddy validate KHÔNG qua — đã gỡ site mới, Caddy prod giữ nguyên, không khởi động lại."
        fi
        xong "caddy validate qua — khởi động lại Caddy prod (admin off nên không reload được)"
        docker restart "$CADDY_PROD" >/dev/null
        for _ in $(seq 1 30); do
            [ "$(docker inspect -f '{{.State.Health.Status}}' "$CADDY_PROD")" = "healthy" ] && break
            sleep 2
        done
        [ "$(docker inspect -f '{{.State.Health.Status}}' "$CADDY_PROD")" = "healthy" ] || \
            dung "Caddy prod CHƯA healthy sau khởi động lại — kiểm ngay: docker logs $CADDY_PROD"
    fi
    noi_caddy_prod_vao_cau
    PROD_SITE="$(env_get "$PROD_DIR/.env.prod" SITE_ADDRESS)"
    if [ -n "$PROD_SITE" ] && [ "${PROD_SITE#:}" = "$PROD_SITE" ]; then
        xong "prod  https://$PROD_SITE/login → $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://$PROD_SITE/login" || echo loi)"
    fi
else
    buoc "7/8  Kiểu rieng — Caddy staging tự giữ TLS cho $STAGING_TEN_MIEN, không đụng Caddy nào khác"
fi
xong "staging https://$STAGING_TEN_MIEN/login → $(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$STAGING_TEN_MIEN/login" || echo 'chưa vào được (DNS/TLS chưa xong?)')"

den_buoc 7

# ── 8. Hẹn giờ mỗi đêm ───────────────────────────────────────────────────────
buoc "8/8  Hẹn giờ nạp lại mỗi đêm 03:30"
if [ "${BO_HEN_GIO:-0}" = "1" ]; then
    canh "BO_HEN_GIO=1 — bỏ qua"
elif sudo -n true 2>/dev/null; then
    for u in clinicai-staging-nap.service clinicai-staging-nap.timer; do
        sed -e "s#@STAGING_DIR@#$STAGING_DIR#g" -e "s#@USER@#$(id -un)#g" \
            -e "s#@STAGING_KIEU@#$STAGING_KIEU#g" \
            "$STAGING_DIR/scripts/systemd/$u" | sudo tee "/etc/systemd/system/$u" >/dev/null
    done
    sudo systemctl daemon-reload
    sudo systemctl enable --now clinicai-staging-nap.timer >/dev/null
    xong "$(systemctl list-timers clinicai-staging-nap.timer --no-pager | sed -n 2p)"
else
    canh "không có sudo không mật khẩu — cài tay: xem docs/STAGING.md mục 'Hẹn giờ'"
fi

echo
docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}' | grep -E "^(${STG_APP_PROJECT}|${STG_PREFIX})" || true
echo
echo "XONG — https://$STAGING_TEN_MIEN (đăng nhập bằng tài khoản prod). Tắt: docs/STAGING.md."
