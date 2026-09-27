#!/bin/bash
# Bước MÁY CHỦ của Pha 0 theo dõi lỗi (27/09/2026). Chạy MỘT lần trên VPS:
#
#     ssh clinic-vps-moi
#     cd /home/clinicai/clinicai && git pull --ff-only && sudo ./scripts/may-chu/bat-theo-doi-may-chu.sh
#
# Làm hai việc, chạy lại bao nhiêu lần cũng được:
#   1. Journal lưu bền trên đĩa (trần 2G). Lần deploy KẾ TIẾP, deploy-backend.sh
#      thấy /var/log/journal và chuyển log container sang journald — log giữ qua
#      deploy. Tra: journalctl CONTAINER_NAME=clinicai_prod-api-1 --since "1 hour ago"
#   2. Lịch chụp tình trạng máy chủ mỗi phút cho tab Hệ thống ở /ops.
#
# Không đụng container nào, không restart ứng dụng. journald khởi động lại mất
# chưa tới một giây; log đang ra lúc ấy vẫn nằm trong bộ đệm json-file.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Cần sudo." >&2; exit 1; }
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

echo "==> [1/2] journal lưu bền"
install -d -m 2755 -g systemd-journal /var/log/journal
install -d -m 755 /etc/systemd/journald.conf.d
install -m 644 "$REPO/scripts/may-chu/journald-clinicai.conf" /etc/systemd/journald.conf.d/clinicai.conf
systemd-tmpfiles --create --prefix /var/log/journal
systemctl restart systemd-journald
journalctl --flush
sleep 1
ls /var/log/journal/*/system.journal >/dev/null 2>&1 \
  || { echo "!! journal CHƯA ghi xuống đĩa — kiểm: journalctl -u systemd-journald" >&2; exit 1; }
echo "   $(journalctl --disk-usage)"

echo "==> [2/2] lịch chụp tình trạng cho /ops"
install -m 644 "$REPO/scripts/systemd/clinicai-ops-status.service" /etc/systemd/system/
install -m 644 "$REPO/scripts/systemd/clinicai-ops-status.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now clinicai-ops-status.timer
systemctl start clinicai-ops-status.service
TT="$(grep -E '^OPS_STATUS_DIR=' "$REPO/.env.prod" | cut -d= -f2-)/production/status.json"
case "$TT" in /*) ;; *) TT="$REPO/$TT" ;; esac
[ -s "$TT" ] || { echo "!! chưa thấy $TT — kiểm: journalctl -u clinicai-ops-status" >&2; exit 1; }
echo "   $TT: $(stat -c '%y' "$TT")"

echo
echo "XONG. Lần deploy kế tiếp sẽ in \"==> log container: journald\"."
