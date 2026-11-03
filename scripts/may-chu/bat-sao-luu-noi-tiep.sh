#!/bin/bash
# Chuẩn bị máy chủ cho sao lưu nối tiếp (docs/KE-HOACH-SAO-LUU-NOI-TIEP.md).
#
#     sudo ./scripts/may-chu/bat-sao-luu-noi-tiep.sh staging   # thử trước
#     sudo ./scripts/may-chu/bat-sao-luu-noi-tiep.sh prod
#
# Làm, chạy lại bao nhiêu lần cũng được:
#   1. Tạo thư mục kho thuộc uid 999 (postgres trong ảnh) — Docker tự tạo thì
#      chủ là root và mọi lần chép WAL hỏng.
#   2. Dựng ảnh clinicai-db:17-pgbackrest.
#   3. (prod) cài + bật timer full/diff/chép-sang-CFS.
#
# KHÔNG khởi động lại DB. Bật thật = đặt trong .env tương ứng
#   SUPABASE_DB_IMAGE=clinicai-db:17-pgbackrest
#   SUPABASE_DB_ARCHIVE_MODE=on
#   SUPABASE_DB_PGBACKREST_DIR=<thư mục ở bước 1>
# rồi dựng lại container DB (khung giờ không có khách — DB ngừng ~1 phút), rồi
#   ./scripts/sao-luu-noi-tiep.sh bat && ./scripts/sao-luu-noi-tiep.sh full
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "cần sudo" >&2; exit 1; }
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
MOI="${1:-}"

case "$MOI" in
  prod)    KHO=/home/clinicai/pgbackrest ;;
  staging) KHO=/home/clinicai/pgbackrest-staging ;;
  *) echo "dùng: $0 prod|staging" >&2; exit 2 ;;
esac

echo "==> [1/3] thư mục kho $KHO"
install -d -o 999 -g 999 -m 750 "$KHO"
echo "   $(stat -c '%U(%u) %a %n' "$KHO")"

echo "==> [2/3] ảnh clinicai-db:17-pgbackrest"
nice -n 19 docker build -q -f "$REPO/docker/db/Dockerfile" -t clinicai-db:17-pgbackrest "$REPO/docker/db"
docker run --rm clinicai-db:17-pgbackrest pgbackrest version

if [ "$MOI" = prod ]; then
  echo "==> [3/3] timer"
  for u in full diff chep; do
    install -m 644 "$REPO/scripts/systemd/clinicai-pgbackrest-$u.service" /etc/systemd/system/
    install -m 644 "$REPO/scripts/systemd/clinicai-pgbackrest-$u.timer" /etc/systemd/system/
  done
  systemctl daemon-reload
  systemctl enable --now clinicai-pgbackrest-full.timer clinicai-pgbackrest-diff.timer \
    clinicai-pgbackrest-chep.timer
  systemctl list-timers 'clinicai-pgbackrest-*' --no-pager
else
  echo "==> [3/3] staging: không cài timer — chạy tay:"
  echo "   CLINIC_DB_CONTAINER=clinicai_stg_db SUPABASE_DB_PGBACKREST_DIR=$KHO ./scripts/sao-luu-noi-tiep.sh full"
fi
