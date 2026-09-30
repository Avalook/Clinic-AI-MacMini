#!/usr/bin/env bash
# Dọn dữ liệu khách GIẢ từ một mốc TRỞ VỀ TRƯỚC trên PROD (30/09/2026).
# Chạy TỪ MÁY MAC, trong thư mục repo; mọi bước làm trên VPS qua ssh.
#
#   ./scripts/don-truoc-moc.sh --moc '2026-09-29 17:45'          # chạy thử: in danh sách + số dòng, cuộn lại
#   ./scripts/don-truoc-moc.sh --moc '2026-09-29 17:45' --that   # xoá thật (hỏi xác nhận)
#
# Luật chọn (chi tiết ở đầu scripts/don-truoc-moc.sql): chỉ xoá KHÁCH mà MỌI
# dữ liệu đều ≤ mốc; khách có dù một lịch/lượt sau mốc thì giữ nguyên toàn bộ.
# Mốc không ghi múi giờ = giờ Việt Nam.
#
# Xoá thật làm theo thứ tự (giống don-prod-truoc-ban-giao.sh):
#   1. sao lưu database (kèm tài khoản đăng nhập)
#   2. dừng các container đang GHI (api, worker, su-kien, day-tep, pos-relay,
#      notification-relay) — dashboard vẫn chạy, chỉ báo lỗi tạm vài giây
#   3. chạy scripts/don-truoc-moc.sql trong MỘT giao dịch
#   4. chuyển TỪNG tệp kết quả của các dòng đã xoá sang thư mục cách ly nằm cạnh
#      kho, cùng ổ — cả ổ VPS (MEDIA_LOCAL_DIR) lẫn Viettel CFS (MEDIA_DIR).
#      Chuyển, không xoá: lỡ tay thì chuyển về được.
#   5. bật lại đúng các container đã dừng
# Bước 3 hỏng thì cả giao dịch cuộn lại, bước 4 không chạy, bước 5 vẫn chạy (trap).
#
# DIỄN TẬP trên bản sao (không ssh, không sao lưu, không dừng gì):
#   DIEN_TAP_DSN=postgresql://postgres:mk@127.0.0.1:55581/postgres \
#     [DIEN_TAP_MEDIA_CFS=/duong/kho-cfs DIEN_TAP_MEDIA_VPS=/duong/kho-vps] \
#     ./scripts/don-truoc-moc.sh --moc '2026-09-29 17:45' [--that]
#   (hai biến MEDIA là thư mục CHỨA `production/` — có thì chuyển tệp thật ở đó)

set -euo pipefail

HOST="${CLINIC_VPS:-clinic-vps-moi}"
DIR=/home/clinicai/clinicai
BK=/home/clinicai/backups/clinicai
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SQL="$REPO/scripts/don-truoc-moc.sql"
DSN="${DIEN_TAP_DSN:-}"

THAT=0
MOC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --that) THAT=1 ;;
    --moc) MOC="${2:-}"; shift ;;
    *) echo "Không hiểu tham số: $1" >&2; exit 2 ;;
  esac
  shift
done
# Chỉ số, gạch, hai chấm, dấu cách, +: mốc đi qua ssh + psql không cần thoát ký tự.
if ! [[ "$MOC" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}(:[0-9]{2})?([+-][0-9]{2}(:?[0-9]{2})?)?$ ]]; then
  echo "Cần --moc 'YYYY-MM-DD HH:MM' (giờ Việt Nam), vd --moc '2026-09-29 17:45'" >&2
  exit 2
fi

TS="$(date +%Y%m%d_%H%M%S)"
NOI="$HOST"
[ -z "$DSN" ] || NOI="bản sao diễn tập (DIEN_TAP_DSN)"   # không in DSN: có mật khẩu
RA="$(mktemp -t don-truoc-moc)"   # toàn bộ đầu ra (kể cả danh sách tệp)

chay_sql() {
  if [ -n "$DSN" ]; then
    psql "$DSN" -X -q -v that="$1" -v "moc=$MOC" -f "$SQL" 2>&1
  else
    ssh "$HOST" "docker exec -i clinicai_db psql -U postgres -d postgres -X -q -v that=$1 -v 'moc=$MOC'" <"$SQL" 2>&1
  fi | sed -E 's/^psql:[^ ]+: (NOTICE|ERROR):  /\1: /' >"$RA"
  # Danh sách tệp dài — màn hình chỉ in số tệp, đủ danh sách nằm trong $RA.
  grep -v '^TEP|' "$RA" || true
  grep -q '^>>> ' "$RA"
}

# Chuyển từng tệp của danh sách sang <kho>-truoc-moc-<ts>/, cùng ổ. Chạy bằng
# `bash -s` (script qua stdin; danh sách đọc từ TỆP — `read` từ stdin sẽ nuốt
# mất phần script còn lại).
# Đối số: tệp-danh-sách ts gốc-cfs gốc-vps thư-mục-repo. Gốc "-" = đọc từ
# .env.prod ở thư-mục-repo (MEDIA_DIR, MEDIA_LOCAL_DIR — như docker-compose).
CHUYEN_TEP=""
# `read -d ''` chứ không `$(cat <<…)`: bash 3.2 của macOS phân tích sai dấu nháy
# lẻ bên trong heredoc nằm trong $( ).
IFS= read -r -d '' CHUYEN_TEP <<'TU_XA' || true
set -euo pipefail
ds="$1"; ts="$2"; cfs="$3"; vps="$4"; noi="$5"
goc_tu_env() {  # $1 = tên biến, $2 = mặc định (tương đối theo thư mục repo)
  local v
  v="$(grep -E "^$1=" .env.prod | tail -1 | cut -d= -f2- | tr -d "\"'" || true)"
  v="${v:-$2}"
  (cd "$v" 2>/dev/null && pwd) || true
}
if [ "$cfs" = - ] || [ "$vps" = - ]; then
  cd "$noi"
  if [ "$cfs" = - ]; then cfs="$(goc_tu_env MEDIA_DIR ./.media)"; fi
  if [ "$vps" = - ]; then vps="$(goc_tu_env MEDIA_LOCAL_DIR ./.media-vps)"; fi
fi
for goc in "$cfs" "$vps"; do
  if [ -z "$goc" ] || [ ! -d "$goc/production" ]; then
    echo "   bỏ qua kho không có: ${goc:-?}"; continue
  fi
  dich="$(dirname "$goc")/$(basename "$goc")-truoc-moc-$ts"
  da=0; khong=0
  while IFS="|" read -r nhan _vi_tri khoa; do
    [ "$nhan" = TEP ] || continue
    case "$khoa" in ""|/*|*..*) echo "   !! khoá lạ, bỏ qua: $khoa"; continue ;; esac
    if [ -f "$goc/production/$khoa" ]; then
      mkdir -p "$(dirname "$dich/production/$khoa")"
      mv -n "$goc/production/$khoa" "$dich/production/$khoa"
      da=$((da + 1))
    else
      khong=$((khong + 1))
    fi
  done <"$ds"
  echo "   $goc: chuyển $da tệp sang $dich ($khong tệp không có ở kho này)"
done
TU_XA

if [ "$THAT" = 0 ]; then
  echo "== CHẠY THỬ trên $NOI — mốc $MOC — không xoá gì =="
  chay_sql 0 || { echo "!! Chạy thử HỎNG — xem $RA" >&2; exit 1; }
  echo
  echo "Đầu ra đầy đủ (kèm danh sách tệp): $RA"
  echo "Muốn xoá thật: $0 --moc '$MOC' --that"
  exit 0
fi

echo "!! SẮP XOÁ THẬT dữ liệu khách ≤ $MOC trên $NOI."
if [ -z "$DSN" ]; then
  printf 'Gõ đúng chữ  XOA TRUOC MOC  để tiếp tục: '
  read -r xac_nhan
  [ "$xac_nhan" = "XOA TRUOC MOC" ] || { echo "Huỷ."; exit 1; }

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
fi

echo "== 3/5 Xoá dữ liệu khách ≤ mốc (một giao dịch) =="
chay_sql 1 || { echo "!! Xoá HỎNG, giao dịch đã cuộn lại — xem $RA" >&2; exit 1; }
grep -q '^>>> ĐÃ XOÁ THẬT (COMMIT)\.' "$RA" || { echo "!! Không thấy COMMIT — dừng trước khi chuyển tệp." >&2; exit 1; }

echo "== 4/5 Chuyển tệp kết quả của dòng đã xoá sang thư mục cách ly (cùng ổ) =="
DS="$(mktemp -t don-truoc-moc-tep)"
grep '^TEP|' "$RA" >"$DS" || true
echo "   $(wc -l <"$DS" | tr -d ' ') tệp trong danh sách"
if [ -n "$DSN" ]; then
  if [ -n "${DIEN_TAP_MEDIA_CFS:-}${DIEN_TAP_MEDIA_VPS:-}" ]; then
    bash -s -- "$DS" "$TS" "${DIEN_TAP_MEDIA_CFS:-}" "${DIEN_TAP_MEDIA_VPS:-}" "$REPO" <<<"$CHUYEN_TEP"
  else
    echo "   diễn tập không đặt DIEN_TAP_MEDIA_* — không chuyển tệp nào"
  fi
else
  ssh "$HOST" "cat > /tmp/don-truoc-moc-$TS.txt" <"$DS"
  ssh "$HOST" bash -s -- "/tmp/don-truoc-moc-$TS.txt" "$TS" - - "$DIR" <<<"$CHUYEN_TEP"
fi

echo "Xong phần xoá. Đầu ra đầy đủ: $RA"
echo "Mở https://dr4women.io.vn kiểm: lịch hẹn tuần, hành trình, thu ngân — khách sau mốc còn nguyên."
