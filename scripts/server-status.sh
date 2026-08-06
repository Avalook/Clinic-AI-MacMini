#!/bin/bash
# Xem nhanh trạng thái ClinicAI trên Mac mini mà không cần publish API/dashboard.
# Dùng:
#   ./scripts/server-status.sh
#   CLINIC_ENV_FILE="$PWD/.env.staging" CLINIC_PROJECT=clinicai_staging ./scripts/server-status.sh
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)}"
ENV_FILE="${CLINIC_ENV_FILE:-$REPO/.env.prod}"
PROJECT="${CLINIC_PROJECT:-clinicai_prod}"
PUBLIC_URL="${PUBLIC_URL:-}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -p "$PROJECT")

ok() { printf "  \033[32m✅ %s\033[0m\n" "$1"; }
no() { printf "  \033[31m❌ %s\033[0m\n" "$1"; }
note() { printf "  • %s\n" "$1"; }

container_id() {
  CLINIC_ENV_FILE="$ENV_FILE" "${COMPOSE[@]}" ps -q "$1" 2>/dev/null | head -n 1
}

container_health() {
  local id="$1"
  [ -n "$id" ] || return 1
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null
}

printf "════════ TRẠNG THÁI CLINICAI (%s) ════════\n" "$PROJECT"

echo "• Cấu hình:"
if [ -f "$ENV_FILE" ]; then
  note "$ENV_FILE"
else
  no "không tìm thấy $ENV_FILE"
  exit 1
fi

echo "• Docker (Colima):"
if command -v colima >/dev/null 2>&1; then
  colima status >/dev/null 2>&1 && ok "Colima đang chạy" || no "Colima KHÔNG chạy"
elif docker info >/dev/null 2>&1; then
  ok "Docker đang chạy"
else
  no "Docker KHÔNG chạy"
fi

echo "• Containers:"
CLINIC_ENV_FILE="$ENV_FILE" "${COMPOSE[@]}" ps --format '  {{.Service}}: {{.Status}}' 2>/dev/null \
  || no "không đọc được compose project"

api_id="$(container_id api)"
dashboard_id="$(container_id dashboard)"
caddy_id="$(container_id caddy)"

echo "• Backend API (chỉ trong Docker):"
api_state="$(container_health "$api_id" || true)"
[ "$api_state" = "healthy" ] && ok "container healthy" || no "container: ${api_state:-not running}"
if [ -n "$api_id" ]; then
  api_health="$(docker exec "$api_id" curl -fsS http://127.0.0.1:8000/health/db 2>/dev/null || true)"
  if printf '%s' "$api_health" | grep -q '"db":"connected"'; then
    latency="$(printf '%s' "$api_health" | grep -oE '"latency_ms":[0-9.]+' | cut -d: -f2)"
    ok "database connected (${latency:-?} ms)"
  else
    no "database readiness FAIL"
  fi
fi

echo "• Dashboard (chỉ trong Docker):"
dashboard_state="$(container_health "$dashboard_id" || true)"
[ "$dashboard_state" = "healthy" ] && ok "container healthy" || no "container: ${dashboard_state:-not running}"

echo "• Caddy ingress:"
caddy_state="$(container_health "$caddy_id" || true)"
[ "$caddy_state" = "healthy" ] && ok "container healthy" || no "container: ${caddy_state:-not running}"
if [ -n "$caddy_id" ] && docker exec "$caddy_id" wget -qO- http://127.0.0.1:80/health >/dev/null 2>&1; then
  ok "/health HTTP 200"
else
  no "/health FAIL"
fi

echo "• Cổng nội bộ:"
if [ -n "$api_id" ] && [ -z "$(docker port "$api_id" 2>/dev/null)" ]; then
  ok "API không publish ra host"
else
  no "API đang publish ra host"
fi
if [ -n "$dashboard_id" ] && [ -z "$(docker port "$dashboard_id" 2>/dev/null)" ]; then
  ok "Dashboard không publish ra host"
else
  no "Dashboard đang publish ra host"
fi

if [ -n "$PUBLIC_URL" ]; then
  echo "• Link công khai:"
  public_code="$(curl -sS -o /dev/null -w '%{http_code}' -L --max-time 15 "$PUBLIC_URL/login" 2>/dev/null || true)"
  [ "$public_code" = "200" ] && ok "$PUBLIC_URL/login → HTTP 200" || no "$PUBLIC_URL/login → HTTP ${public_code:-FAIL}"
fi

echo "• Tailscale Funnel:"
if command -v tailscale >/dev/null 2>&1; then
  funnel_status="$(tailscale funnel status 2>/dev/null || true)"
  caddy_port="$(sed -n 's/^CADDY_HTTP_PORT=//p' "$ENV_FILE" | tail -n 1 | tr -d '"' || true)"
  caddy_port="${caddy_port:-80}"
  if printf '%s' "$funnel_status" | grep -q "proxy http://127.0.0.1:$caddy_port"; then
    ok "đang trỏ vào Caddy :$caddy_port"
  elif printf '%s' "$funnel_status" | grep -q 'proxy http://'; then
    funnel_target="$(printf '%s' "$funnel_status" | grep -oE 'proxy http://[^ ]+' | head -n 1)"
    no "đang trỏ sai ingress (${funnel_target:-unknown}); cần trỏ vào Caddy :$caddy_port"
  else
    note "chưa bật"
  fi
else
  note "không cài Tailscale hoặc không dùng Funnel"
fi

echo "════════════════════════════════════════════"
echo "Xem log trực tiếp:"
printf '  CLINIC_ENV_FILE="%s" docker compose --env-file "%s" -p "%s" logs -f --tail=100\n' \
  "$ENV_FILE" "$ENV_FILE" "$PROJECT"
