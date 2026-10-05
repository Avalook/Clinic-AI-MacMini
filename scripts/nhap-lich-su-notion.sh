#!/bin/bash
# Nạp gói lịch sử khám Notion vào hệ thống (05/10/2026).
#
# Chạy TRÊN VPS, NGOÀI GIỜ ĐÓN KHÁCH, sau khi đã sao lưu. Gói là thư mục do máy dev
# dựng (manifest.json + *.jsonl + tep/), chép lên VPS trước.
#
#   ./scripts/nhap-lich-su-notion.sh prod    /home/clinicai/lich-su-notion/goi-2026-10-05          # thử khô
#   ./scripts/nhap-lich-su-notion.sh prod    /home/clinicai/lich-su-notion/goi-2026-10-05 --that   # ghi thật
#   ./scripts/nhap-lich-su-notion.sh staging /home/clinicai/lich-su-notion/goi-2026-10-05 --that
#
# Thử khô = chạy trọn trong một giao dịch rồi quay lui, in số liệu. Ghi thật = một
# giao dịch (lỗi giữa chừng → không còn gì), xong mới chép tệp kết quả vào kho.
# Chạy lại an toàn: người đã nạp giữ hồ sơ cũ, chỉ thêm phần mới + cập nhật nội dung.
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

DICH="/tmp/goi-lich-su-notion"
echo "== Gói: $(tr -d '\n' < "$GOI/manifest.json" | head -c 300)"
docker exec "$API" rm -rf "$DICH"
docker cp "$GOI" "$API:$DICH"
trap 'docker exec "$API" rm -rf "$DICH" >/dev/null 2>&1 || true' EXIT
docker exec -e PYTHONPATH=/app/src "$API" /app/.venv/bin/python \
    -m clinicai.services.nhap_lich_su_notion "$DICH" "$@"
