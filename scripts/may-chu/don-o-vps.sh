#!/bin/bash
# Dọn bộ đệm build trên VPS (13/10/2026) — chạy TỪ MAC, mặc định CHỈ ĐỌC.
#
#   ./scripts/may-chu/don-o-vps.sh           # chạy thử: báo sẽ dọn gì, không xoá
#   ./scripts/may-chu/don-o-vps.sh --that    # dọn thật (hỏi xác nhận)
#
# Chỉ đụng BỘ ĐỆM BUILD (cache dựng image) — không đụng image đang dùng (kể cả
# để rollback), volume database, tệp bệnh nhân, nhật ký, container nào. Dọn xong
# bản build kế tiếp của staging/prod chậm hơn vài phút (dựng lại lớp đệm), chạy
# bình thường.
#
# Chốt an toàn (khách đang dùng prod và staging):
#   1. Có tiến trình build/deploy/sao lưu/áp migration đang chạy → DỪNG, không dọn.
#   2. Chụp tên + giờ khởi động + số lần restart của MỌI container trước và sau;
#      khác nhau là báo lỗi (dọn đệm không được làm container nào khởi động lại).
#   3. Sau khi dọn kiểm prod + staging còn trả lời, không container nào unhealthy.
# Xoá file bộ đệm làm đĩa bận ít phút — chạy lúc ít khách (sau giờ phòng khám).
set -euo pipefail

HOST="${VPS_HOST:-clinic-vps-moi}"
BUILDER_STG="clinicai-staging-builder-3g"
THAT=0
[ "${1:-}" = "--that" ] && THAT=1

r() { ssh -o ConnectTimeout=10 -o BatchMode=yes "$HOST" "$1"; }

chup() {
  r 'docker ps -a --format "{{.Names}}" | sort | while read -r n; do
       docker inspect "$n" --format "{{.Name}} {{.State.StartedAt}} restart={{.RestartCount}}"
     done'
}

echo "==> [1/4] kiểm có việc đang chạy trên VPS không"
BAN=$(r 'ps -eo pid,etimes,args | grep -E "deploy-|docker (buildx|build|compose)|buildctl|backup-db|apply-pending|len-staging|len-prod" | grep -vE "grep|ps -eo" || true')
if [ -n "$BAN" ]; then
  echo "!! VPS đang có việc chạy — KHÔNG dọn lúc này:" >&2
  echo "$BAN" | cut -c1-160 >&2
  exit 2
fi
echo "   không có build/deploy/sao lưu nào đang chạy"

echo "==> [2/4] hiện trạng"
r 'df -h / | tail -1; echo "-- bộ đệm builder staging:"; docker buildx du --builder '"$BUILDER_STG"' 2>/dev/null | tail -2; echo "-- bộ đệm builder mặc định:"; docker buildx du 2>/dev/null | tail -2'

if [ "$THAT" != 1 ]; then
  echo
  echo "Chạy thử xong — chưa xoá gì. Dọn thật: $0 --that"
  exit 0
fi

read -r -p "Dọn bộ đệm build (giữ 3GB đệm gần nhất của staging, đệm mặc định giữ 72 giờ)? Gõ 'dọn' để tiếp: " OK
[ "$OK" = "dọn" ] || { echo "Huỷ."; exit 1; }

TRUOC="$(chup)"
echo "==> [3/4] dọn"
r "docker buildx prune --builder $BUILDER_STG --max-used-space 3gb -f"
r 'docker builder prune --filter until=72h -f'

echo "==> [4/4] kiểm sau dọn"
SAU="$(chup)"
if [ "$TRUOC" != "$SAU" ]; then
  echo "!! container thay đổi trong lúc dọn (khởi động lại / thêm / mất) — xem:" >&2
  diff <(echo "$TRUOC") <(echo "$SAU") >&2 || true
  exit 3
fi
echo "   mọi container giữ nguyên (không khởi động lại)"
XAU=$(r 'docker ps --filter health=unhealthy --format "{{.Names}}"')
[ -z "$XAU" ] || { echo "!! container unhealthy: $XAU" >&2; exit 4; }
echo "   không container nào unhealthy"
for u in https://dr4women.io.vn/ https://staging.dr4women.io.vn/; do
  m=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$u" || true)
  echo "   $u -> $m"
  case "$m" in 2*|3*|401) ;; *) echo "!! $u trả $m" >&2; exit 5 ;; esac
done
r 'df -h / | tail -1'
echo "XONG — dọn bộ đệm build, không đụng dữ liệu hay container."
