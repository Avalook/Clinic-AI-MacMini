#!/usr/bin/env bash
# Kiểm R-042 trên STAGING, CHỈ ĐỌC: tài khoản vai PARTNER/DISPLAY có đọc được
# patient / appointment / lab_result / staff qua /rest/v1 không.
#
#   scripts/kiem-r042-staging.sh email-doi-tac@...
#
# Mật khẩu gõ tay khi được hỏi (không hiện, không lưu, không vào lịch sử shell).
# Staging đăng nhập bằng tài khoản PROD — gõ đúng mật khẩu prod của tài khoản ấy.
# Khoá anon (khoá công khai, nằm sẵn trong JS của trang) lấy từ .env.staging trên
# VPS bằng ssh chỉ đọc, không in ra. Đặt sẵn STAGING_ANON_KEY thì bỏ qua ssh.
#
# Kết quả mong muốn SAU bản vá: patient/appointment/lab_result = 0, staff = 1.
# TRƯỚC bản vá (lỗ hổng): các số > 0 — tức đối tác đọc được dữ liệu khách.
set -euo pipefail

BASE="${STAGING_URL:-https://staging.dr4women.io.vn}"
EMAIL="${1:?cách dùng: $0 email-tai-khoan-doi-tac}"

# Chốt chặn: chỉ chạy trên staging/local, không bao giờ trên prod.
case "$BASE" in
  https://staging.dr4women.io.vn|http://localhost*|http://127.0.0.1*) ;;
  *) echo "Từ chối: $BASE không phải staging/local. Script này không chạy trên prod." >&2; exit 2 ;;
esac

if [[ -z "${STAGING_ANON_KEY:-}" ]]; then
  STAGING_ANON_KEY="$(ssh clinic-vps-moi \
    "grep -E '^(NEXT_PUBLIC_SUPABASE_ANON_KEY|ANON_KEY)=' ~/clinicai-staging/.env.staging | head -1 | cut -d= -f2-" \
    | tr -d '"'\''\r')"
fi
[[ -n "$STAGING_ANON_KEY" ]] || { echo "Không lấy được khoá anon staging." >&2; exit 1; }

read -r -s -p "Mật khẩu của $EMAIL: " MAT_KHAU; echo

TOKEN="$(python3 -c '
import json, sys, urllib.request
base, key, email, pw = sys.argv[1:5]
req = urllib.request.Request(
    f"{base}/auth/v1/token?grant_type=password",
    data=json.dumps({"email": email, "password": pw}).encode(),
    headers={"apikey": key, "Content-Type": "application/json"},
)
try:
    print(json.load(urllib.request.urlopen(req, timeout=15))["access_token"])
except Exception as e:
    sys.exit(f"Đăng nhập hỏng: {e}")
' "$BASE" "$STAGING_ANON_KEY" "$EMAIL" "$MAT_KHAU")"
unset MAT_KHAU

# Tài khoản này đang là vai gì (đọc chính dòng membership của mình).
echo "Vai của tài khoản:"
curl -sS "$BASE/rest/v1/clinic_membership?select=role,is_active" \
  -H "apikey: $STAGING_ANON_KEY" -H "Authorization: Bearer $TOKEN"; echo

printf '\n%-12s %-8s %s\n' "bảng" "HTTP" "số dòng thấy được"
for BANG in patient appointment lab_result staff; do
  # HEAD + Prefer: count=exact → PostgREST trả tổng ở Content-Range, không tải dòng nào.
  HDR="$(curl -sS -o /dev/null -D - -I "$BASE/rest/v1/$BANG?select=id" \
    -H "apikey: $STAGING_ANON_KEY" -H "Authorization: Bearer $TOKEN" \
    -H "Prefer: count=exact")"
  CODE="$(printf '%s' "$HDR" | awk 'NR==1{print $2}')"
  SO="$(printf '%s' "$HDR" | tr -d '\r' | awk -F/ 'tolower($0) ~ /^content-range:/{print $2}')"
  printf '%-12s %-8s %s\n' "$BANG" "$CODE" "${SO:-?}"
done

echo
echo "Mẫu đúng câu kiểm toán (patient?select=id&limit=1):"
curl -sS "$BASE/rest/v1/patient?select=id&limit=1" \
  -H "apikey: $STAGING_ANON_KEY" -H "Authorization: Bearer $TOKEN"; echo
