#!/bin/bash
# DỌN Ổ GỐC VPS — chỉ bộ đệm build. Chạy trên VPS, mặc định CHẠY THỬ:
#
#     ./scripts/may-chu/don-o-vps.sh          # xem dọn được bao nhiêu
#     ./scripts/may-chu/don-o-vps.sh --that   # dọn thật
#
# 31/10: ổ 89%, 16G là bộ đệm build, dọn xong còn 76%. Hậu quả duy nhất là lần
# build kế chậm hơn. KHÔNG đụng volume, ảnh, container, sao lưu, tệp kết quả —
# muốn dọn những thứ ấy phải cân nhắc riêng, đừng thêm vào đây.
set -euo pipefail

BUILDER_STAGING=clinicai-staging-builder-3g
GIU_GIO=48

case "${1:-}" in
  "") THAT=0 ;;
  --that) THAT=1 ;;
  *) echo "Dùng: $0 [--that]" >&2; exit 2 ;;
esac

co_builder() { docker buildx inspect "$BUILDER_STAGING" >/dev/null 2>&1; }

trong() { df -h / | tail -1 | awk '{print $4 " trống, dùng " $5}'; }

echo "Ổ gốc trước: $(trong)"

if [ "$THAT" = 0 ]; then
  echo "CHẠY THỬ — chưa xoá gì."
  echo "Bộ đệm mặc định: $(docker builder du 2>/dev/null | tail -1)"
  if co_builder; then
    echo "Bộ đệm staging:  $(docker buildx du --builder "$BUILDER_STAGING" 2>/dev/null | tail -1)"
  fi
  echo "Dọn thật: $0 --that"
  exit 0
fi

docker builder prune -f >/dev/null
if co_builder; then
  docker buildx prune --builder "$BUILDER_STAGING" -f --filter "until=${GIU_GIO}h" >/dev/null
fi
echo "Ổ gốc sau:   $(trong)"
