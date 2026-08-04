#!/usr/bin/env bash
#
# GIỮ STACK SỐNG SAU KHI MÁY KHỞI ĐỘNG LẠI — bản thay thế cho
# ~/clinic-server/.../clinic-backend-boot.sh.
#
# VÌ SAO VẪN CẦN MỘT SCRIPT NHƯ THẾ NÀY.
#
# `restart: unless-stopped` trong compose chỉ có tác dụng KHI Docker đã chạy.
# Trên máy này Docker là **Colima**, và Colima KHÔNG tự khởi động cùng macOS.
# Nên sau một lần mất điện, không container nào dậy — và không có gì báo.
#
# Đó là việc DUY NHẤT script cũ làm đúng. Nó cũng làm hai việc SAI, và bản này
# bỏ cả hai:
#
#   1. Dựng api + dashboard từ `~/clinic-server/.../docker-compose.prod.yml`,
#      trong khi caddy/dozzle/kuma đến từ repo này — hai stack tranh nhau cùng
#      tên project `clinicai_prod`. File cũ khai "8000:8000" và "3000:3000",
#      tức 0.0.0.0, nên cứ 5 phút cổng lại mở ra toàn mạng LAN, bỏ qua Caddy.
#      Đó là lý do cổng "mở lại" sau mỗi lần sửa.
#
#   2. Bật `tailscale funnel` phơi thẳng cổng 3000 ra internet — đi vòng qua
#      Caddy, nên cấu hình TLS/ingress của repo này không nằm trên đường đi
#      thật. Ai cần đường vào từ xa thì bật Funnel bằng tay và biết mình đang
#      bật cái gì; một script chạy nền không nên tự phơi phòng khám ra internet
#      mỗi 5 phút.
#
# Script này CHỈ làm hai việc, và cả hai đều idempotent:
#   - Colima chưa chạy → khởi động.
#   - Stack chưa đủ    → `up -d` theo ĐÚNG compose của repo này.
#
# Nó KHÔNG build, KHÔNG kéo code mới, KHÔNG chạy migration. Triển khai là việc
# của `deploy-backend.sh` — một script chạy nền mỗi vài phút mà tự đổi phiên
# bản đang chạy là thứ không ai muốn có trong phòng khám.

set -u

REPO="${1:-$HOME/Projects/Dr4Women-MacMini}"
ENVN="${2:-prod}"
ENV_FILE="$REPO/.env.$ENVN"
PROJECT="clinicai_$ENVN"
LOG="$HOME/Library/Logs/clinic-boot.log"

# launchd cho PATH tối thiểu — nạp vị trí thường gặp của brew/colima/docker.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"; }

[ -f "$ENV_FILE" ] || { log "không thấy $ENV_FILE — dừng"; exit 1; }
[ -f "$REPO/docker-compose.yml" ] || { log "không thấy compose ở $REPO"; exit 1; }

# 1. Docker runtime.
if command -v colima >/dev/null 2>&1 && ! colima status >/dev/null 2>&1; then
  if colima start >>"$LOG" 2>&1; then log "colima start OK"; else log "colima start THẤT BẠI"; fi
fi

if ! docker info >/dev/null 2>&1; then
  log "docker chưa sẵn sàng — bỏ qua, lần sau thử lại"
  exit 0
fi

# 2. Stack. `up -d` không đụng gì khi mọi thứ đã đúng, nên chạy mỗi 5 phút là
#    vô hại — nhưng chỉ khi nó đọc ĐÚNG file compose. CLINIC_ENV_FILE là biến
#    mà compose của repo này đòi (xem services.dashboard.env_file).
cd "$REPO" || exit 1
export CLINIC_ENV_FILE="$ENV_FILE"

before="$(docker compose --env-file "$ENV_FILE" -p "$PROJECT" ps -q 2>/dev/null | wc -l | tr -d ' ')"
if docker compose --env-file "$ENV_FILE" -p "$PROJECT" up -d >>"$LOG" 2>&1; then
  after="$(docker compose --env-file "$ENV_FILE" -p "$PROJECT" ps -q 2>/dev/null | wc -l | tr -d ' ')"
  # Chỉ ghi log khi CÓ THAY ĐỔI. Ghi mỗi 5 phút một dòng "vẫn ổn" thì file log
  # đầy tiếng ồn, và đúng lúc cần tìm sự cố thì không ai đọc nổi.
  [ "$before" = "$after" ] || log "up -d: $before → $after container"
else
  log "up -d THẤT BẠI — xem $LOG"
fi
