#!/bin/bash
# Xem NHANH toàn bộ trạng thái backend ClinicAI trên Mac mini (1 lệnh).
# Dùng: ~/clinic-server/Clinic-AI-Dr4Women/scripts/server-status.sh
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

REPO="${1:-$HOME/clinic-server/Clinic-AI-Dr4Women}"
COMPOSE="docker compose -f $REPO/docker-compose.prod.yml"
PUBLIC="https://mac-mini-ca-quang.tailc94236.ts.net"

ok(){ printf "  \033[32m✅ %s\033[0m\n" "$1"; }
no(){ printf "  \033[31m❌ %s\033[0m\n" "$1"; }

echo "════════ TRẠNG THÁI SERVER MAC MINI ════════"

echo "• Docker (Colima):"
colima status >/dev/null 2>&1 && ok "Colima đang chạy" || no "Colima KHÔNG chạy"

echo "• Containers:"
$COMPOSE ps --format '  {{.Service}}: {{.Status}}' 2>/dev/null || no "không đọc được compose"

echo "• Backend api (nội bộ :8000):"
curl -fsS http://localhost:8000/health >/dev/null 2>&1 && ok "/health OK" || no "/health FAIL"
db=$(curl -fsS http://localhost:8000/health/db 2>/dev/null)
echo "$db" | grep -q '"connected"' && ok "DB atf: connected ($(echo "$db" | grep -oE '"latency_ms":[0-9.]+' | cut -d: -f2)ms)" || no "DB: $db"

echo "• Web dashboard (nội bộ :3000):"
c=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/enter 2>/dev/null)
[ "$c" = "200" ] && ok "trang /enter HTTP 200" || no "web HTTP $c"

echo "• Link công khai (qua internet):"
c=$(curl -s -o /dev/null -w "%{http_code}" -L "$PUBLIC/enter" 2>/dev/null)
[ "$c" = "200" ] && ok "$PUBLIC → HTTP 200" || no "$PUBLIC → HTTP $c (funnel?)"

echo "• Tailscale Funnel:"
tailscale funnel status 2>/dev/null | grep -qE 'Funnel on|proxy' && ok "đang phơi ra internet" || no "funnel chưa bật"

echo "• Dịch vụ tự chạy 24/7 (LaunchDaemon):"
[ -f /Library/LaunchDaemons/com.dr4women.clinic-backend.plist ] && ok "đã cài (tự lên khi boot)" || no "CHƯA cài LaunchDaemon"

echo "════════════════════════════════════════════"
echo "Xem LOG trực tiếp:"
echo "  Tất cả:      $COMPOSE logs -f"
echo "  Chỉ web:     $COMPOSE logs -f dashboard"
echo "  Chỉ backend: $COMPOSE logs -f api"
echo "  Tự-khởi-động: tail -f ~/Library/Logs/clinic-backend-boot.log"
