# shellcheck shell=bash
# Bộ biến môi trường của dashboard LOCAL — MỘT nguồn cho dev-up.sh (bước 4),
# dev-nap-lai.sh (web) và dev-giao-dien.sh (next dev).
#
# Vì sao tách: trước 01/10/2026 khối sáu biến này được chép tay ba lần (hai lần
# trong dev-up.sh, một lần trong dev-nap-lai.sh). Chép thêm lần thứ tư cho
# `next dev` là chờ ngày một bản lệch — ví dụ quên BACKEND_API_KEY thì mọi route
# proxy trả 401 mà giao diện chỉ báo "không đọc được dữ liệu".
#
# Gọi SAU khi đã nạp .env.thu-local (cần SUPABASE_API_PORT, SUPABASE_ANON_KEY,
# SUPABASE_SERVICE_ROLE_KEY). Tôn trọng PUBLIC_SUPABASE_URL (dev-up.sh: mở từ
# máy khác qua tunnel) và API_PORT. Giá trị dưới là của stack THỬ trên
# 127.0.0.1, không phải bí mật vận hành.

xuat_moi_truong_web() {
    local sb="http://127.0.0.1:${SUPABASE_API_PORT:-54421}"
    export NEXT_PUBLIC_SUPABASE_URL="${PUBLIC_SUPABASE_URL:-$sb}"
    export NEXT_PUBLIC_SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY:?thiếu SUPABASE_ANON_KEY — nạp .env.thu-local trước}"
    export SUPABASE_URL="$sb"
    export SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:?thiếu SUPABASE_SERVICE_ROLE_KEY}"
    export CLINIC_API_URL="http://127.0.0.1:${API_PORT:-8100}"
    export BACKEND_API_KEY="${BACKEND_API_KEY:-staging-local-api-key}"
}
