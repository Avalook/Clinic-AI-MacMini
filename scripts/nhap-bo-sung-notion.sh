#!/bin/bash
# Nạp GÓI PHỤ lịch sử Notion (06/10/2026): lịch sử chăm sóc khách, nguồn khách, người
# nhà, dự kiến sinh. Chạy SAU gói chính (scripts/nhap-lich-su-notion.sh).
#
# Chạy TRÊN VPS, NGOÀI GIỜ ĐÓN KHÁCH, sau khi đã sao lưu. Gói phụ là thư mục do máy dev
# dựng (dong_goi_phu.py: manifest.json + *.jsonl), chép lên VPS trước.
#
#   ./scripts/nhap-bo-sung-notion.sh prod /home/clinicai/lich-su-notion/goi-phu-2026-10-06          # thử khô
#   ./scripts/nhap-bo-sung-notion.sh prod /home/clinicai/lich-su-notion/goi-phu-2026-10-06 --that   # ghi thật
#
# Một giao dịch (lỗi giữa chừng → không còn gì); thử khô = chạy hết rồi quay lui;
# chạy lại an toàn. Gỡ: scripts/hoan-tac-bo-sung-notion.sql (xem đầu tệp ấy).
set -euo pipefail

MOI_TRUONG="${1:-}"
GOI="${2:-}"
shift 2 || true
case "$MOI_TRUONG" in
    prod) API="clinicai_prod-api-1" ;;
    staging) API="clinicai_staging-api-1" ;;
    *) echo "Dùng: $0 prod|staging <thư mục gói phụ> [--that]" >&2; exit 2 ;;
esac
[ -f "$GOI/manifest.json" ] || { echo "Không thấy $GOI/manifest.json" >&2; exit 2; }
[ -f "$GOI/cham_soc.jsonl" ] || { echo "Không thấy $GOI/cham_soc.jsonl — đây không phải gói phụ" >&2; exit 2; }
docker inspect "$API" >/dev/null 2>&1 || { echo "Không thấy container $API" >&2; exit 2; }

DICH="/tmp/goi-bo-sung-notion"
echo "== Gói phụ: $(tr -d '\n' < "$GOI/manifest.json" | head -c 300)"
docker exec "$API" rm -rf "$DICH"
docker exec "$API" mkdir -p "$DICH"
trap 'docker exec "$API" rm -rf "$DICH" >/dev/null 2>&1 || true' EXIT
for f in "$GOI"/manifest.json "$GOI"/*.jsonl; do
    docker cp "$f" "$API:$DICH/"
done
docker exec -e PYTHONPATH=/app/src "$API" /app/.venv/bin/python \
    -m clinicai.services.nhap_bo_sung_notion "$DICH" "$@"
