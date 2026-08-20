#!/usr/bin/env bash
# Bảng điều khiển sức khoẻ ClinicAI — một lệnh xem hết, chạy từ máy bất kỳ
# có cấu hình `ssh clinic-vps` (Tuyền yêu cầu 19/08/2026: "bộ script theo dõi
# trong terminal như code chuyên nghiệp, không phải khi nào cũng nhờ AI").
#
# CHỈ ĐỌC — script này không đổi bất cứ thứ gì trên máy chủ.
#
# Dùng:
#   ./scripts/suc-khoe.sh              # tổng quan: health, container, Kuma, tài nguyên, sao lưu
#   ./scripts/suc-khoe.sh loi [phút]   # lỗi của API prod trong N phút gần nhất (mặc định 30)
#   ./scripts/suc-khoe.sh kenh         # nhịp tim 4 kênh Uptime Kuma
#   ./scripts/suc-khoe.sh sao-luu      # các bản sao lưu gần nhất
#   ./scripts/suc-khoe.sh ban          # bản build nào đang chạy (tuổi image prod/staging)
#
# Khác gì các script sẵn có:
#   check-monitoring.sh  — đối chiếu cấu hình Kuma với repo (kiểm TRÔI cấu hình)
#   collect_ops_status.py— xuất snapshot một chiều cho Ops Center
#   suc-khoe.sh (này)    — cái nhìn NHANH hằng ngày cho người vận hành
set -euo pipefail

HOST="${CLINIC_HOST:-clinic-vps}"
IP="${CLINIC_IP:-222.255.215.219}"

do_mau() { # $1 = mã http; in kèm nhãn đọc được
  if [ "$1" = "200" ]; then printf "200 ✓"; else printf "%s ✗ (KHÔNG KHOẺ)" "$1"; fi
}

phan_health() {
  echo "── Nhịp thở ──────────────────────────────────────────"
  printf "  prod    (:80)   /health: %s\n" "$(do_mau "$(curl -s -o /dev/null -m 8 -w '%{http_code}' "http://$IP/health" || echo 000)")"
  printf "  staging (:8080) /health: %s\n" "$(do_mau "$(curl -s -o /dev/null -m 8 -w '%{http_code}' "http://$IP:8080/health" || echo 000)")"
}

phan_container() {
  echo "── Container (chỉ hàng KHÔNG khoẻ mới đáng lo) ───────"
  # shellcheck disable=SC2029
  ssh "$HOST" 'docker ps --format "{{.Names}}\t{{.Status}}"' \
    | sort | awk -F'\t' '{
        # unhealthy = báo động; healthy = ổn; không khai healthcheck = chỉ ghi chú
        if ($2 ~ /unhealthy/)      ok = "✗ ";
        else if ($2 ~ /healthy/)   ok = "  ";
        else                       { ok = "· "; $2 = $2 " (không khai healthcheck)" }
        printf "  %s%-38s %s\n", ok, $1, $2 }'
}

phan_kenh() {
  echo "── Uptime Kuma (1 = Up) ──────────────────────────────"
  ssh "$HOST" 'docker exec clinicai_prod-uptime-kuma-1 sqlite3 /app/data/kuma.db \
    "SELECT m.name, h.status, h.time FROM monitor m JOIN heartbeat h ON h.id=(SELECT max(id) FROM heartbeat WHERE monitor_id=m.id) ORDER BY m.id"' \
    | awk -F'|' '{ ok = ($2=="1") ? "✓" : "✗ DOWN"; printf "  %s %-28s lần cuối %s\n", ok, $1, $3 }'
}

phan_tai_nguyen() {
  echo "── Tài nguyên máy chủ ────────────────────────────────"
  ssh "$HOST" 'printf "  đĩa:  %s\n" "$(df -h / | awk "NR==2{print \$5\" đã dùng (\"\$4\" trống)\"}")";
               printf "  RAM:  %s\n" "$(free -h | awk "NR==2{print \$3\" / \"\$2}")";
               printf "  tải:  %s\n" "$(uptime | sed "s/.*load average/load average/")"'
}

phan_sao_luu() {
  echo "── Sao lưu gần nhất ──────────────────────────────────"
  ssh "$HOST" 'ls -lht /home/clinicai/backups 2>/dev/null | head -4' | sed 's/^/  /'
  echo "  (luật nhà: bản sao lưu chưa phục hồi thử = chưa phải sao lưu → scripts/restore-drill.sh)"
}

phan_loi() {
  local phut="${1:-30}"
  echo "── Lỗi API prod trong ${phut} phút gần nhất ──────────"
  # shellcheck disable=SC2029
  local dem
  dem=$(ssh "$HOST" "docker logs clinicai_prod-api-1 --since ${phut}m 2>&1 | grep -ciE '\" (500|502|503) |error|traceback' || true")
  printf "  số dòng nghi lỗi: %s\n" "$dem"
  if [ "${dem:-0}" -gt 0 ]; then
    # shellcheck disable=SC2029
    ssh "$HOST" "docker logs clinicai_prod-api-1 --since ${phut}m 2>&1 | grep -iE '\" (500|502|503) |error|traceback' | tail -5" | cut -c1-160 | sed 's/^/  /'
    echo "  → xem đầy đủ: Dozzle, hoặc: ssh $HOST 'docker logs clinicai_prod-api-1 --since ${phut}m'"
  fi
}

phan_ban() {
  echo "── Bản đang chạy (tuổi image = lần deploy gần nhất) ──"
  ssh "$HOST" 'docker images --format "{{.Repository}}:{{.Tag}}\t{{.CreatedSince}}" | grep -E "clinicai-(api|dashboard)"' \
    | awk -F'\t' '{ printf "  %-28s dựng %s\n", $1, $2 }'
  echo "  (đối chiếu commit: gh run list --workflow=cd.yml --limit 3)"
}

case "${1:-tong-quan}" in
  tong-quan) phan_health; echo; phan_container; echo; phan_kenh; echo; phan_tai_nguyen; echo; phan_sao_luu ;;
  loi)       phan_loi "${2:-30}" ;;
  kenh)      phan_kenh ;;
  sao-luu)   phan_sao_luu ;;
  ban)       phan_ban ;;
  *) echo "Lệnh không biết: $1"; grep '^#   ./scripts' "$0" | sed 's/^# *//'; exit 1 ;;
esac
