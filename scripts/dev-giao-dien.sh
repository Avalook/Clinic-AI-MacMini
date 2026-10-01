#!/usr/bin/env bash
# Sửa giao diện và THẤY NGAY — không dựng lại (Tuyền 01/10/2026).
#
# `scripts/dev-up.sh` chạy dashboard bằng BẢN DỰNG (`next start`): sửa .tsx thì
# trang không đổi gì cho tới khi `scripts/dev-nap-lai.sh web` dựng lại (~40–60s).
# Lúc đang chỉnh chữ, màu, khoảng cách trong Antigravity / VS Code thì vòng ấy
# quá chậm. Lệnh này thay `next start` bằng `next dev`: lưu tệp là trang tự đổi.
#
#   scripts/dev-giao-dien.sh               web ở cổng 3100 (như dev-up.sh)
#   WEB_PORT=3190 scripts/dev-giao-dien.sh  cổng khác (không đụng 3100)
#
# Nó KHÔNG tự dựng API/Supabase — chưa chạy thì bảo chạy dev-up.sh trước.
# Dừng: Ctrl+C. Về lại bản dựng (để nghiệm thu như prod): scripts/dev-nap-lai.sh web
#
# GHI CHÚ `next dev` VÀ TRÌNH DUYỆT HEADLESS. dev-up.sh chọn bản dựng vì lúc dựng
# stack, `next dev` không hydrate client component dưới Chromium HEADLESS (máy
# bấm thử tự động). Đó là chuyện của trình duyệt headless — Chrome/Safari thật
# mà Tuyền mở thì chạy bình thường. Nghiệm thu bằng máy bấm tự động hay đo tốc
# độ thì quay về bản dựng.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

API_PORT="${API_PORT:-8100}"
WEB_PORT="${WEB_PORT:-3100}"

do_() { printf '\033[31m%s\033[0m\n' "$*" >&2; }
xanh() { printf '\033[32m%s\033[0m\n' "$*"; }

# .env.thu-local: của cây này; worktree thì mượn của bản checkout chính (stack
# local chạy từ đó — khoá phải khớp GoTrue đang chạy).
ENV_THU="$REPO/.env.thu-local"
if [ ! -f "$ENV_THU" ]; then
    chinh="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo "$REPO/.git")")"
    [ -f "$chinh/.env.thu-local" ] && ENV_THU="$chinh/.env.thu-local"
fi
[ -f "$ENV_THU" ] || { do_ "Thiếu .env.thu-local — chạy scripts/dev-up.sh trước."; exit 1; }
set -a
# shellcheck disable=SC1090
. "$ENV_THU"
set +a
# shellcheck source=scripts/lib/moi-truong-web.sh
. "$REPO/scripts/lib/moi-truong-web.sh"

# 1. API + Supabase phải đang chạy — chỉ KIỂM, không dựng.
thieu=""
curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:${SUPABASE_API_PORT:-54421}/health" \
    || thieu="$thieu Supabase(:${SUPABASE_API_PORT:-54421})"
curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:${API_PORT}/health" \
    || thieu="$thieu API(:${API_PORT})"
if [ -n "$thieu" ]; then
    do_ "Chưa chạy:$thieu — chạy scripts/dev-up.sh trước (nó dựng cả stack local), rồi chạy lại lệnh này."
    exit 1
fi

[ -x src/dashboard/node_modules/.bin/next ] || {
    do_ "Thiếu src/dashboard/node_modules — chạy: (cd src/dashboard && npm ci)"; exit 1; }

# 2. Tắt Next đang giữ cổng web (next start của dev-up / dev-nap-lai, hay một
#    next dev cũ). CHỈ theo cổng — không `pkill next-server` toàn máy, vì phiên
#    khác có thể đang chạy Next ở cổng khác.
for pid in $(lsof -tiTCP:"$WEB_PORT" -sTCP:LISTEN 2>/dev/null || true); do
    lenh="$(ps -o command= -p "$pid" 2>/dev/null || true)"
    case "$lenh" in
        *next*)
            cha="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
            kill "$pid" 2>/dev/null || true
            if [ -n "$cha" ] && ps -o command= -p "$cha" 2>/dev/null | grep -qE 'next (start|dev)'; then
                kill "$cha" 2>/dev/null || true
            fi
            echo "  đã tắt Next đang giữ cổng $WEB_PORT (pid $pid)" ;;
        *)
            do_ "Cổng $WEB_PORT đang bị giữ bởi thứ không phải Next: $lenh — dừng nó hoặc đặt WEB_PORT khác."
            exit 1 ;;
    esac
done
for _ in $(seq 1 20); do
    lsof -nP -iTCP:"$WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
    sleep 0.5
done
if lsof -nP -iTCP:"$WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    do_ "Cổng $WEB_PORT vẫn bận sau 10 giây — kiểm: lsof -nP -iTCP:$WEB_PORT -sTCP:LISTEN"
    exit 1
fi

# 3. next dev với ĐÚNG bộ biến như dev-up.sh bước 4 (scripts/lib/moi-truong-web.sh).
xuat_moi_truong_web
cat <<EOF

$(xanh "Mở http://127.0.0.1:${WEB_PORT} — sửa .tsx là trang tự đổi; Ctrl+C để dừng, chạy lại scripts/dev-nap-lai.sh web để về bản dựng.")
  (API :${API_PORT} · Supabase :${SUPABASE_API_PORT:-54421} · khoá từ ${ENV_THU})
  Lần mở đầu mỗi trang chậm vài giây (dev biên dịch theo yêu cầu) — bình thường.

EOF
cd src/dashboard
exec ./node_modules/.bin/next dev -p "$WEB_PORT"
