#!/usr/bin/env bash
# Dọn sạch dữ liệu khách trên PROD trước khi bàn giao (25/09/2026).
# Chạy TỪ MÁY MAC, trong thư mục repo; mọi bước làm trên VPS qua ssh.
#
#   ./scripts/don-prod-truoc-ban-giao.sh              # chạy thử: đếm + làm thật rồi cuộn lại
#   ./scripts/don-prod-truoc-ban-giao.sh --that       # xoá thật (hỏi xác nhận)
#   ./scripts/don-prod-truoc-ban-giao.sh --that --xoa-kho   # xoá cả tồn kho thuốc
#
# Xoá thật làm theo thứ tự:
#   1. sao lưu database (kèm tài khoản đăng nhập)
#   2. dừng các container đang GHI (api, worker, su-kien, pos-relay,
#      notification-relay) — dashboard vẫn chạy, chỉ báo lỗi tạm vài giây
#   3. chạy scripts/don-prod-truoc-ban-giao.sql trong MỘT giao dịch
#   4. chuyển tệp kết quả / ảnh siêu âm của khách sang thư mục cách ly nằm
#      cạnh kho media, cùng ổ (chuyển, không xoá — lỡ tay thì chuyển về được)
#   5. bật lại đúng các container đã dừng
# Bước 3 hỏng thì cả giao dịch cuộn lại và bước 5 vẫn chạy (trap).

set -euo pipefail

HOST="${CLINIC_VPS:-clinic-vps-moi}"
DIR=/home/clinicai/clinicai
BK=/home/clinicai/backups/clinicai
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SQL="$REPO/scripts/don-prod-truoc-ban-giao.sql"

THAT=0
KHO=giu
for a in "$@"; do
  case "$a" in
    --that) THAT=1 ;;
    --xoa-kho) KHO=xoa ;;
    *) echo "Không hiểu tham số: $a" >&2; exit 2 ;;
  esac
done

chay_sql() {
  ssh "$HOST" "docker exec -i clinicai_db psql -U postgres -d postgres -q -v that=$1 -v kho=$KHO" <"$SQL" 2>&1 |
    sed -E 's/^psql:<stdin>:[0-9]+: NOTICE:  //'
}

if [ "$THAT" = 0 ]; then
  echo "== CHẠY THỬ trên $HOST (kho=$KHO) — không xoá gì =="
  chay_sql 0
  echo
  echo "Muốn xoá thật: $0 --that$([ "$KHO" = xoa ] && echo ' --xoa-kho')"
  exit 0
fi

echo "!! SẮP XOÁ THẬT toàn bộ dữ liệu khách trên $HOST (kho=$KHO)."
printf 'Gõ đúng chữ  XOA SACH  để tiếp tục: '
read -r xac_nhan
[ "$xac_nhan" = "XOA SACH" ] || { echo "Huỷ."; exit 1; }

TS="$(date +%Y%m%d_%H%M%S)"

echo "== 1/5 Sao lưu database =="
ssh "$HOST" "cd $DIR && PG_DUMP_BIN=$DIR/scripts/pg-dump-qua-container.sh \
  CLINIC_DB_CONTAINER=clinicai_db BACKUP_ENV_FILE=$DIR/.env.prod \
  CLINIC_BACKUP_DIR=$BK ./scripts/backup-db.sh" | tail -5
MOI="$(ssh "$HOST" "ls -t $BK/*.sql.gz | head -1")"
ssh "$HOST" "test \$(find '$MOI' -mmin -10 -size +10k | wc -l) -eq 1" || {
  echo "!! Không thấy bản sao lưu mới (<10 phút, >10KB). Dừng, chưa xoá gì." >&2
  exit 1
}
echo "   bản sao lưu: $MOI"

echo "== 2/5 Dừng các container đang ghi =="
DUNG="$(ssh "$HOST" "docker ps --format '{{.Names}}' | grep -E '^clinicai_prod-(api|worker|su-kien|day-tep|pos-relay|notification-relay)-[0-9]+$' | tr '\n' ' '")"
[ -n "$DUNG" ] || { echo "!! Không tìm thấy container api — sai máy?" >&2; exit 1; }
bat_lai() {
  echo "== 5/5 Bật lại: $DUNG=="
  ssh "$HOST" "docker start $DUNG >/dev/null && docker ps --format '{{.Names}} {{.Status}}' | grep clinicai_prod-"
}
trap bat_lai EXIT
ssh "$HOST" "docker stop $DUNG >/dev/null"
echo "   đã dừng: $DUNG"

echo "== 3/5 Xoá dữ liệu khách (một giao dịch) =="
chay_sql 1

echo "== 4/5 Chuyển tệp kết quả / siêu âm sang thư mục cách ly (cùng ổ) =="
# Kho media ở prod nằm trên ổ Viettel (MEDIA_DIR=/mnt/viettel-cfs/...). Chuyển
# trong CÙNG ổ = đổi tên, tức thì; chép về ổ VPS là kéo vài GB qua mạng.
ssh "$HOST" bash -s -- "$DIR" "$TS" <<'TU_XA'
set -euo pipefail
cd "$1"
M="$(grep -E '^MEDIA_DIR=' .env.prod | cut -d= -f2- || true)"
M="${M:-./.media}"
M="$(cd "$M" 2>/dev/null && pwd || true)"
[ -n "$M" ] && [ -d "$M/production" ] || { echo "   không có thư mục media — bỏ qua"; exit 0; }
D="$(dirname "$M")/$(basename "$M")-truoc-ban-giao-$2"
n=0
for d in "$M"/production/*/ket-qua "$M"/production/*/ultrasound; do
  [ -d "$d" ] || continue
  dich="$D/${d#"$M"/}"
  mkdir -p "$(dirname "$dich")"
  mv "$d" "$dich"
  n=$((n + 1))
done
echo "   đã chuyển $n thư mục sang $D"
TU_XA

echo "Xong phần xoá. Mở https://dr4women.io.vn kiểm lại: danh sách bệnh nhân, lịch hẹn, hàng đợi phải trống."
