#!/bin/bash
# Nạp gói hồ sơ khám cũ (Notion) vào hệ thống (05/10/2026).
#
# Chạy TRÊN VPS, NGOÀI GIỜ ĐÓN KHÁCH, sau khi đã sao lưu. Gói là thư mục do máy dev
# dựng (manifest.json + *.jsonl + tep/), chép lên VPS trước.
#
#   ./scripts/nhap-lich-su-notion.sh prod /home/clinicai/lich-su-notion/goi-2026-10-05          # thử khô
#   ./scripts/nhap-lich-su-notion.sh prod /home/clinicai/lich-su-notion/goi-2026-10-05 --that   # ghi thật
#
# * Chỉ DỮ LIỆU (*.jsonl, vài chục MB) đi vào container API; bộ nạp chạy trong MỘT
#   giao dịch (lỗi giữa chừng → không còn gì), thử khô = chạy hết rồi quay lui.
# * Tệp PDF (tep/, vài GB) KHÔNG đi qua container: ghi thật xong mới chép thẳng trên
#   máy chủ vào kho tệp của môi trường (ổ gắn vào /var/lib/clinicai/media), không ghi
#   đè tệp đã có. Chạy lại an toàn.
# Gỡ: scripts/hoan-tac-lich-su-notion.sql (xem đầu tệp ấy).
set -euo pipefail

MOI_TRUONG="${1:-}"
GOI="${2:-}"
shift 2 || true
case "$MOI_TRUONG" in
    prod) API="clinicai_prod-api-1" ;;
    staging) API="clinicai_staging-api-1" ;;
    *) echo "Dùng: $0 prod|staging <thư mục gói> [--that]" >&2; exit 2 ;;
esac
[ -f "$GOI/manifest.json" ] || { echo "Không thấy $GOI/manifest.json" >&2; exit 2; }
docker inspect "$API" >/dev/null 2>&1 || { echo "Không thấy container $API" >&2; exit 2; }
THAT=0
for a in "$@"; do [ "$a" = "--that" ] && THAT=1; done

DICH="/tmp/goi-lich-su-notion"
echo "== Gói: $(tr -d '\n' < "$GOI/manifest.json" | head -c 300)"
docker exec "$API" rm -rf "$DICH"
docker exec "$API" mkdir -p "$DICH"
trap 'docker exec "$API" rm -rf "$DICH" >/dev/null 2>&1 || true' EXIT
for f in "$GOI"/manifest.json "$GOI"/*.jsonl; do
    docker cp "$f" "$API:$DICH/"
done
KQ="$(docker exec -e PYTHONPATH=/app/src "$API" /app/.venv/bin/python \
    -m clinicai.services.nhap_lich_su_notion "$DICH" --khong-chep-tep "$@")"
echo "$KQ"

if [ "$THAT" = 1 ] && [ -d "$GOI/tep" ]; then
    KHO="$(docker inspect "$API" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/clinicai/media"}}{{.Source}}{{end}}{{end}}')"
    CLINIC="$(printf '%s\n' "$KQ" | sed -n 's/.*"clinic_id": "\([0-9a-f-]*\)".*/\1/p' | head -1)"
    [ -n "$KHO" ] && [ -d "$KHO" ] || { echo "Không tìm thấy kho tệp của $API" >&2; exit 1; }
    [ -n "$CLINIC" ] || { echo "Không đọc được clinic_id từ kết quả nạp" >&2; exit 1; }
    DICH_TEP="$KHO/$CLINIC/lich-su-notion"
    echo "== Chép tệp kết quả vào $DICH_TEP (không ghi đè tệp đã có)…"
    mkdir -p "$DICH_TEP"
    cp -an "$GOI/tep/." "$DICH_TEP/"
    echo "   xong: $(find "$DICH_TEP" -type f | wc -l) tệp trong kho"
fi
