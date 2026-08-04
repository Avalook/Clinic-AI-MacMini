#!/usr/bin/env bash
# So monitoring/monitors.json với những gì Uptime Kuma ĐANG thật sự theo dõi.
#
# VÌ SAO CẦN. Danh sách monitor sống trong volume kuma_data và được bấm tay qua
# giao diện. Không có gì nối nó với repo, nên hai kiểu trôi xảy ra âm thầm:
#
#   * mất volume → Kuma khởi động lại với 0 monitor, và "không có cảnh báo"
#     trông hệt "mọi thứ đều ổn";
#   * ai đó tắt/xoá một monitor để đỡ ồn trong lúc bảo trì rồi quên bật lại.
#
# Cả hai đều không có triệu chứng. Script này biến chúng thành một dòng đỏ.
#
#   ./scripts/check-monitoring.sh              # dùng KUMA_URL/KUMA_TOKEN nếu có
#   KUMA_URL=http://127.0.0.1:3001 ./scripts/check-monitoring.sh
#
# Không có token thì vẫn chạy được phần hữu ích nhất: kiểm tra chính các
# endpoint mà monitors.json khai báo, để biết chúng có sống thật không.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="${REPO}/monitoring/monitors.json"
KUMA_URL="${KUMA_URL:-http://127.0.0.1:3001}"

if [[ ! -f "$SPEC" ]]; then
    echo "Không thấy $SPEC — monitoring/ phải có bản khai báo." >&2
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "Cần jq: brew install jq" >&2
    exit 1
fi

echo "=== Monitor đã khai báo (monitoring/monitors.json) ==="
jq -r '.monitors[] | "  \(.type)\t\(.name)"' "$SPEC"
echo

echo "=== Kuma có đang chạy không ==="
if curl -fsS --max-time 5 "$KUMA_URL" >/dev/null 2>&1; then
    echo "  OK — Kuma trả lời tại $KUMA_URL"
else
    echo "  ✗ KHÔNG trả lời tại $KUMA_URL"
    echo "    Hệ giám sát chết thì mọi cảnh báo ngừng gửi, và sự im lặng đó"
    echo "    không phân biệt được với 'hệ thống khoẻ'."
    exit 2
fi
echo

# Kuma 1.x không có REST API đọc danh sách monitor (chỉ socket.io), nên không tự
# so được từng cái. Thứ kiểm được — và cũng là thứ quan trọng hơn — là các
# endpoint trong bản khai báo có thật sự phục vụ hay không.
echo "=== Endpoint HTTP trong bản khai báo ==="
fail=0
while IFS=$'\t' read -r name url; do
    [[ -z "${url:-}" || "$url" == "null" ]] && continue
    case "$url" in *'${'*) echo "  ⊘ $name — bỏ qua (URL có biến chưa thay)"; continue ;; esac
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
        echo "  OK   $name"
    else
        echo "  ✗    $name  ($url)"
        fail=1
    fi
done < <(jq -r '.monitors[] | select(.type == "http") | "\(.name)\t\(.url)"' "$SPEC")

echo
if [[ $fail -eq 0 ]]; then
    echo "Tất cả endpoint khai báo đều phục vụ được."
    echo
    echo "LƯU Ý: script này KHÔNG chứng minh Kuma đang theo dõi chúng."
    echo "Mở $KUMA_URL và đối chiếu với danh sách ở trên — Kuma 1.x không có API"
    echo "đọc monitor nên bước này vẫn phải làm bằng mắt."
else
    echo "Có endpoint không phục vụ được. Nếu Kuma đang xanh, nghĩa là nó KHÔNG"
    echo "theo dõi endpoint đó — chính là kiểu trôi mà file này sinh ra để bắt."
    exit 3
fi
