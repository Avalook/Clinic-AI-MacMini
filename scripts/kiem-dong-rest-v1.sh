#!/usr/bin/env bash
# KIỂM /rest/v1 VÀ /realtime/v1 ĐÃ ĐÓNG, ĐĂNG NHẬP VẪN CHẠY (23/11/2026) — CHỈ ĐỌC.
#
# Vì sao có: caddy/Caddyfile đóng hai đường này (khoá anon nằm trong JS trình
# duyệt, RLS lọc theo phòng khám chứ không theo vai → để mở là Đối tác/TV đọc
# thẳng ~110 bảng). Script này là phép thử sau mỗi lần deploy Caddy.
#
# Chạy TRÊN VPS, trong thư mục của môi trường cần kiểm:
#
#   cd ~/clinicai-staging && ./scripts/kiem-dong-rest-v1.sh .env.staging
#   cd /home/clinicai/clinicai && ./scripts/kiem-dong-rest-v1.sh .env.prod
#
# Hỏi email + mật khẩu của MỘT nhân viên ngay tại terminal (gõ ẩn, không lưu,
# không in ra), lấy token qua /auth/v1/token như trình duyệt, rồi gọi thử các
# đường. Không ghi gì: chỉ GET, và một POST đăng nhập (đúng như bấm Đăng nhập).
# Đọc dữ liệu thì chỉ lấy MÃ TRẠNG THÁI, không in dòng nào.
#
# Thoát 0 = ĐẠT hết; 1 = có dòng HỎNG; 2 = sai cách gọi.
set -uo pipefail

ENV_FILE="${1:-}"
[ -f "$ENV_FILE" ] || { echo "Dùng: $0 .env.staging | .env.prod"; exit 2; }
lay() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d "\"'"; }
GOC="$(lay NEXT_PUBLIC_SUPABASE_URL)"
ANON="$(lay SUPABASE_ANON_KEY)"
[ -n "$GOC" ] && [ -n "$ANON" ] || {
    echo "Thiếu NEXT_PUBLIC_SUPABASE_URL hoặc SUPABASE_ANON_KEY trong $ENV_FILE"; exit 2; }

echo "Kiểm $GOC"
read -r -p "Email nhân viên: " EMAIL
read -r -s -p "Mật khẩu (gõ ẩn): " MK; echo
# Ghép JSON bằng python để mật khẩu có ký tự đặc biệt không vỡ câu lệnh.
THAN="$(python3 -c 'import json,sys; print(json.dumps({"email": sys.argv[1], "password": sys.argv[2]}))' "$EMAIL" "$MK")"
unset MK
TOKEN="$(curl -s -m 15 -X POST "$GOC/auth/v1/token?grant_type=password" \
    -H "apikey: $ANON" -H 'Content-Type: application/json' --data-binary "$THAN" \
    | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("access_token",""))
except Exception: print("")')"
unset THAN

hong=0
dong() { # nhãn · mã thật · mã cần
    if [ "$2" = "$3" ]; then printf '  ĐẠT\t%s\t%s\n' "$2" "$1"
    else printf '  HỎNG\t%s\t%s  (cần %s)\n' "$2" "$1" "$3"; hong=1; fi
}
ma() { curl -s -o /dev/null -m 15 -w '%{http_code}' "$@"; }

if [ -n "$TOKEN" ]; then dong "đăng nhập /auth/v1/token" 200 200
else dong "đăng nhập /auth/v1/token (sai mật khẩu?)" "không-token" 200; fi
A=(-H "apikey: $ANON" -H "Authorization: Bearer $TOKEN")
dong "/auth/v1/user — token nhân viên"        "$(ma "${A[@]}" "$GOC/auth/v1/user")" 200
dong "/rest/v1/patient — token nhân viên"     "$(ma "${A[@]}" "$GOC/rest/v1/patient?select=*&limit=1")" 403
dong "/rest/v1/appointment — token nhân viên" "$(ma "${A[@]}" "$GOC/rest/v1/appointment?select=*&limit=1")" 403
dong "/rest/v1/ danh mục bảng — không token"  "$(ma -H "apikey: $ANON" "$GOC/rest/v1/")" 403
dong "/rest/v1 không gạch chéo"               "$(ma -H "apikey: $ANON" "$GOC/rest/v1")" 403
dong "/realtime/v1/websocket"                 "$(ma "$GOC/realtime/v1/websocket?apikey=$ANON&vsn=1.0.0")" 403
dong "/login"                                 "$(ma "$GOC/login")" 200

if [ "$hong" = 0 ]; then echo "KẾT QUẢ: ĐẠT"; else echo "KẾT QUẢ: HỎNG — xem dòng HỎNG"; fi
exit "$hong"
