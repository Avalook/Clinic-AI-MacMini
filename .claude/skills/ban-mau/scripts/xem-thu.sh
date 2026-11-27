#!/bin/bash
# Xem thử artboard .dc.html ở máy, không cần đăng nhập claude.ai.
# Dùng: xem-thu.sh <Main.dc.html> <dc-runtime.js> [thư mục asset]  (chạy nền)
#   dc-runtime.js: Artifact action read, path "artifact-type/dc-runtime.js" của chính artifact.
#   thư mục asset: các tệp đặt tên đúng id blob (vd ee2c…dc59) để /_blob/<id> mở được.
# Mở http://127.0.0.1:${CONG:-3291}/Main.dc.html. Dừng: pkill -f "http.server ${CONG:-3291}".
set -euo pipefail
CONG="${CONG:-3291}"
XEM="$(dirname "$1")/../xem-thu"
mkdir -p "$XEM/_blob"
cp "$2" "$XEM/support.js"
cp "$1" "$XEM/Main.dc.html"
if [ -n "${3:-}" ]; then cp "$3"/* "$XEM/_blob/"; fi
echo "Đang phục vụ $XEM ở http://127.0.0.1:$CONG/Main.dc.html"
exec python3 -m http.server "$CONG" --bind 127.0.0.1 --directory "$XEM"
