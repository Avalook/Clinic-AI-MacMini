#!/bin/bash
# Tạo tệp mẫu (PDF + ảnh trang 1) từ một trang HTML, để bản mẫu "xem được tệp thật".
# Dùng: tao-pdf-mau.sh <trang.html> <thư mục ra>
# Trang HTML phải có dấu "BẢN MẪU MINH HOẠ", dữ liệu giả, không tên đơn vị thật.
# Khuôn sẵn: ../mau/phieu-ket-qua-mau.html. Xong thì upload cả hai bằng Artifact asset.
set -euo pipefail
RA="$2"; mkdir -p "$RA"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --no-pdf-header-footer --print-to-pdf="$RA/tep-mau.pdf" "file://$(cd "$(dirname "$1")" && pwd)/$(basename "$1")" 2>/dev/null
pdftoppm -png -r 110 -singlefile "$RA/tep-mau.pdf" "$RA/tep-mau"
ls -la "$RA/tep-mau.pdf" "$RA/tep-mau.png"
