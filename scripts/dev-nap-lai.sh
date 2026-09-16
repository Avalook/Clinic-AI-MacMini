#!/usr/bin/env bash
# Nạp lại phần vừa sửa — MỘT lệnh, không phải nhớ mười biến môi trường.
#
# VÌ SAO CÓ FILE NÀY. Hai phiên liên tiếp mất thời gian vì cùng một chuyện: sửa
# code xong, mở màn, thấy hành vi CŨ, rồi đi tìm lỗi ở chỗ không có lỗi.
#
#   · API chạy uvicorn KHÔNG có --reload  → Python cũ vẫn nằm trong bộ nhớ.
#     (dev-up.sh nay bật --reload sẵn, nên phần này chỉ còn cần khi đổi .env
#     hoặc khi muốn khởi động sạch.)
#   · Web chạy `next start` trên BẢN DỰNG  → sửa .tsx không đổi gì cho tới khi
#     dựng lại. Đây mới là cái hay cắn, vì `next start` không hề báo gì.
#
# Cách dùng:
#   scripts/dev-nap-lai.sh web     dựng lại + khởi động lại dashboard (~40–60s)
#   scripts/dev-nap-lai.sh api     khởi động lại FastAPI
#   scripts/dev-nap-lai.sh         cả hai
#
# Nó ĐỌC .env.thu-local để lấy khoá, giống hệt dev-up.sh — một nguồn, không phải
# một bản chép tay trong đầu người gõ lệnh.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

API_PORT="${API_PORT:-8100}"
WEB_PORT="${WEB_PORT:-3100}"
LOG_DIR="${LOG_DIR:-$REPO/.dev-logs}"
mkdir -p "$LOG_DIR"

[ -f .env.thu-local ] || { echo "Thiếu .env.thu-local — chạy scripts/dev-up.sh trước." >&2; exit 1; }
set -a; . ./.env.thu-local; set +a

SB_URL="http://127.0.0.1:${SUPABASE_API_PORT:-54421}"
DB_URL="postgresql+asyncpg://postgres:${SUPABASE_DB_PASSWORD}@127.0.0.1:${SUPABASE_DB_PORT:-54422}/postgres"
# Giá trị LOCAL, cố định trong dev-up.sh — giữ giống hệt để hai lối khởi động
# không đẻ ra hai cấu hình khác nhau.
KHOA_CONG="${BACKEND_API_KEY:-staging-local-api-key}"

# Cờ tự nạp lại — MẢNG, không phải chuỗi. `${BIEN-"a b"}` nhả ra MỘT từ "a b"
# và uvicorn đọc nó thành một tuỳ chọn duy nhất rồi chết. Mảng tách đúng.
if [ -z "${TU_NAP_LAI+x}" ]; then
    NAP=(--reload --reload-dir src/clinicai)
else
    read -ra NAP <<< "$TU_NAP_LAI"
fi

xanh() { printf '\033[32m%s\033[0m\n' "$*"; }

cho_len() {
    local url="$1" ten="$2" i
    for i in $(seq 1 120); do
        curl -sf -o /dev/null "$url" 2>/dev/null && return 0
        sleep 1
    done
    echo "$ten không lên — xem $LOG_DIR" >&2
    return 1
}

nap_api() {
    echo "→ FastAPI"
    pkill -f "uvicorn clinicai.main.*--port ${API_PORT}" 2>/dev/null || true
    sleep 1
    PYTHONPATH=src \
    SUPABASE_URL="$SB_URL" DATABASE_URL="$DB_URL" \
    SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
    SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
    SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET" \
    ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-local-not-real}" \
    BACKEND_API_KEY="$KHOA_CONG" \
    CHECKPOINTER_BACKEND=memory APP_ENV=staging POS_ADAPTER=none \
        nohup poetry run uvicorn clinicai.main:app \
            --host 127.0.0.1 --port "$API_PORT" \
            "${NAP[@]}" \
            >"$LOG_DIR/api.log" 2>&1 &
    cho_len "http://127.0.0.1:${API_PORT}/health" "API" && xanh "  API sẵn sàng :${API_PORT}"
}

nap_web() {
    echo "→ Next.js (dựng lại — bản production, đây là chỗ hay quên)"
    cd src/dashboard
    NEXT_PUBLIC_SUPABASE_URL="$SB_URL" \
    NEXT_PUBLIC_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
    SUPABASE_URL="$SB_URL" \
    SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
    CLINIC_API_URL="http://127.0.0.1:${API_PORT}" \
    BACKEND_API_KEY="$KHOA_CONG" \
        npx next build >"$LOG_DIR/web-build.log" 2>&1 || {
            echo "dựng hỏng — $LOG_DIR/web-build.log" >&2
            grep -m5 -E "Error|error" "$LOG_DIR/web-build.log" | sed 's/^/    /' >&2
            exit 1; }
    pkill -f "next start -p ${WEB_PORT}" 2>/dev/null || true
    pkill -f "next-server" 2>/dev/null || true
    sleep 1
    NEXT_PUBLIC_SUPABASE_URL="$SB_URL" \
    NEXT_PUBLIC_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
    SUPABASE_URL="$SB_URL" \
    SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
    CLINIC_API_URL="http://127.0.0.1:${API_PORT}" \
    BACKEND_API_KEY="$KHOA_CONG" \
        nohup npx next start -p "$WEB_PORT" >"$LOG_DIR/web.log" 2>&1 &
    cd "$REPO"
    cho_len "http://127.0.0.1:${WEB_PORT}/login" "dashboard" && xanh "  Web sẵn sàng :${WEB_PORT}"
}

case "${1:-all}" in
    api) nap_api ;;
    web) nap_web ;;
    all) nap_api; nap_web ;;
    *)   echo "Dùng: $0 [api|web|all]" >&2; exit 2 ;;
esac
