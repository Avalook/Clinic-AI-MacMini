#!/bin/bash
# Kiểm khoá /rest/v1 QUA ĐƯỜNG THẬT (Caddy → PostgREST), đúng như kẻ ngoài gọi.
# Checklist mục 6 ý 2–4 của docs/ke-hoach/khoa-rest-v1-2210.md. CHỈ ĐỌC (GET/POST
# đọc), không ghi gì.
#
#   ENV_FILE=.env.staging URL=https://staging.dr4women.io.vn ./scripts/kiem-khoa-rest-http.sh
#   ENV_FILE=.env.prod    URL=https://dr4women.io.vn         ./scripts/kiem-khoa-rest-http.sh
#
# Script tự đọc SUPABASE_ANON_KEY trong ENV_FILE (không in ra). Sau phần không
# đăng nhập, nó HỎI tên đăng nhập + mật khẩu của từng tài khoản muốn thử (gõ
# trực tiếp, mật khẩu không hiện; Enter trống để bỏ qua) — nên thử ít nhất một
# tài khoản Đối tác, một Tivi, một nhân viên thường.

set -euo pipefail

ENV_FILE="${ENV_FILE:?đặt ENV_FILE=.env.staging hoặc .env.prod}"
URL="${URL:?đặt URL=https://staging.dr4women.io.vn hoặc https://dr4women.io.vn}"
DUOI="${DUOI_TEN_DANG_NHAP:-dr4women.vn}"

ANON="$(sed -n 's/^SUPABASE_ANON_KEY=//p' "$ENV_FILE" | tail -1 | tr -d '"'"'"'\r')"
[ -n "$ANON" ] || { echo "Không thấy SUPABASE_ANON_KEY trong $ENV_FILE" >&2; exit 2; }

HONG=0
dat() { printf '  ĐẠT   %s\n' "$*"; }
hong() { printf '  HỎNG  %s\n' "$*"; HONG=$((HONG + 1)); }

# GET một đường /rest/v1, in "mã|thân".
goi() {
  local tok="$1" duong="$2"
  curl -sS -o /tmp/kiem-khoa-rest.$$ -w '%{http_code}' "$URL/rest/v1/$duong" \
    -H "apikey: $ANON" -H "Authorization: Bearer $tok"
}

# Bị chặn = PostgREST trả 401/403 (permission denied), hoặc 404 cho /rpc lạ.
phai_chan() {
  local tok="$1" duong="$2" ma
  ma="$(goi "$tok" "$duong")"
  case "$ma" in
    401|403|404) dat "$duong → $ma" ;;
    *) hong "$duong → $ma $(head -c 120 /tmp/kiem-khoa-rest.$$)" ;;
  esac
}

NHAY_CAM="patient appointment payment visit prescription lab_result capability_grant payment_cycle clinic"

echo "== Không đăng nhập (anon key có sẵn trong trình duyệt ai cũng lấy được)"
for b in $NHAY_CAM staff clinic_membership; do phai_chan "$ANON" "$b?select=*&limit=1"; done

while true; do
  echo
  read -rp "Tên đăng nhập muốn thử (Enter trống = xong): " NICK
  [ -n "$NICK" ] || break
  read -rsp "Mật khẩu (không hiện): " MK; echo
  case "$NICK" in *@*) EMAIL="$NICK" ;; *) EMAIL="$NICK@$DUOI" ;; esac
  TOK="$(curl -sS -X POST "$URL/auth/v1/token?grant_type=password" \
          -H "apikey: $ANON" -H 'Content-Type: application/json' \
          --data "$(python3 -c 'import json,sys; print(json.dumps({"email": sys.argv[1], "password": sys.argv[2]}))' "$EMAIL" "$MK")" \
        | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("access_token", ""))
except Exception: print("")')"
  unset MK
  if [ -z "$TOK" ]; then echo "  (đăng nhập không được — kiểm lại tên/mật khẩu)"; continue; fi
  echo "== $EMAIL"
  for b in $NHAY_CAM; do phai_chan "$TOK" "$b?select=*&limit=1"; done
  phai_chan "$TOK" "staff?select=*"
  phai_chan "$TOK" "staff?select=national_id_number"
  phai_chan "$TOK" "staff?select=full_name,phone"
  phai_chan "$TOK" "rpc/clinic_hours_for_date?p_clinic_id=00000000-0000-0000-0000-000000000000&p_date=2026-01-01"
  # Đúng câu proxy.ts + màn đăng nhập: phải 200 và đúng MỘT hàng.
  ma="$(goi "$TOK" "staff?select=id,primary_department,is_active,auth_user_id")"
  so="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' /tmp/kiem-khoa-rest.$$ 2>/dev/null || echo "?")"
  if [ "$ma" = 200 ] && [ "$so" = 1 ]; then dat "staff?select=id,… → 200, đúng 1 hàng (của mình)"
  else hong "staff?select=id,… → $ma, $so hàng (phải 200 và 1)"; fi
  ma="$(goi "$TOK" "clinic_membership?select=clinic_id,role,is_active")"
  so="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' /tmp/kiem-khoa-rest.$$ 2>/dev/null || echo "?")"
  if [ "$ma" = 200 ] && [ "$so" != 0 ] && [ "$so" != "?" ]; then dat "clinic_membership → 200, $so hàng (của mình)"
  else hong "clinic_membership → $ma, $so hàng"; fi
done

rm -f /tmp/kiem-khoa-rest.$$
echo
if [ "$HONG" -gt 0 ]; then echo "CÓ $HONG MỤC HỎNG"; exit 1; fi
echo "TẤT CẢ ĐẠT"
