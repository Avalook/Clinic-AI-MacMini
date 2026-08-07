#!/usr/bin/env bash
# Đặt lại mật khẩu MỌI tài khoản về mật khẩu mặc định.
# Đi qua API quản trị của GoTrue chứ không UPDATE thẳng auth.users: GoTrue tự
# băm đúng cách và tự huỷ phiên đang mở. Sửa tay cột encrypted_password là dễ
# ra một hàng băm mà GoTrue không đọc được, và cả phòng khám mất đường vào.
set -euo pipefail
ENVF="$1"; CONG="$2"; MK="$3"
cd ~/clinicai
set -a; . "$ENVF"; set +a
KEY="${SUPABASE_SERVICE_ROLE_KEY:?thiếu SUPABASE_SERVICE_ROLE_KEY}"
B="http://127.0.0.1:${CONG}/auth/v1"
ids=$(curl -s "$B/admin/users?per_page=200" -H "apikey: $KEY" -H "Authorization: Bearer $KEY" \
      | python3 -c 'import sys,json;[print(u["id"],u["email"]) for u in json.load(sys.stdin).get("users",[])]')
[ -n "$ids" ] || { echo "!! không đọc được danh sách tài khoản"; exit 1; }
echo "$ids" | while read -r id mail; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$B/admin/users/$id" \
    -H "apikey: $KEY" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"password\":\"$MK\"}")
  printf "  %-28s %s\n" "$mail" "$code"
done
