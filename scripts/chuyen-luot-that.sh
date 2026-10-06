#!/bin/bash
# Chuyển lịch sử khám cũ (lich_su_notion, đã nạp) thành LƯỢT THẬT (06/10/2026).
#
# Chạy TRÊN VPS, NGOÀI GIỜ ĐÓN KHÁCH, sau khi sao lưu. Cần tep_meta.jsonl (cỡ +
# sha256 từng PDF, dựng trên máy dev) nằm trong thư mục gói.
#
#   ./scripts/chuyen-luot-that.sh prod /home/clinicai/lich-su-notion/goi-2026-10-06          # thử khô
#   ./scripts/chuyen-luot-that.sh prod /home/clinicai/lich-su-notion/goi-2026-10-06 --that   # ghi thật
#
# Một giao dịch; chạy lại an toàn (lượt đã chuyển thì bỏ qua).
# Gỡ: docker exec -i clinicai_db psql -v ON_ERROR_STOP=1 -U postgres < scripts/hoan-tac-luot-that.sql
set -euo pipefail

MOI_TRUONG="${1:-}"
GOI="${2:-}"
shift 2 || true
case "$MOI_TRUONG" in
    prod) API="clinicai_prod-api-1" ;;
    staging) API="clinicai_staging-api-1" ;;
    *) echo "Dùng: $0 prod|staging <thư mục gói> [--that]" >&2; exit 2 ;;
esac
[ -f "$GOI/tep_meta.jsonl" ] || { echo "Không thấy $GOI/tep_meta.jsonl" >&2; exit 2; }
docker inspect "$API" >/dev/null 2>&1 || { echo "Không thấy container $API" >&2; exit 2; }

DICH="/tmp/tep_meta_luot_that.jsonl"
docker cp "$GOI/tep_meta.jsonl" "$API:$DICH"
trap 'docker exec "$API" rm -f "$DICH" >/dev/null 2>&1 || true' EXIT
docker exec -e PYTHONPATH=/app/src "$API" /app/.venv/bin/python \
    -m clinicai.services.chuyen_luot_that --tep-meta "$DICH" "$@"
