#!/bin/bash
# Đặt mật khẩu THẬT cho hai vai đăng nhập được.
#
# `01-vai-va-extension.sql` tạo chúng với một chuỗi tạm, vì file .sql không đọc
# được biến môi trường. Bước này chạy ngay sau đó (init chạy theo thứ tự tên
# file) và thay bằng mật khẩu thật.
#
# Quên bước này thì GoTrue và PostgREST không nối được, và thông báo lỗi là
# "password authentication failed" — đúng nhưng không nói vì sao.
set -euo pipefail
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<SQL
ALTER ROLE authenticator        PASSWORD '${POSTGRES_PASSWORD}';
ALTER ROLE supabase_auth_admin  PASSWORD '${POSTGRES_PASSWORD}';
ALTER ROLE supabase_admin       PASSWORD '${POSTGRES_PASSWORD}';
SQL
echo "đã đặt mật khẩu cho authenticator + supabase_auth_admin + supabase_admin"
