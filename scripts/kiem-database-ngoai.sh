#!/usr/bin/env bash
#
# Kiểm một database bên ngoài (Viettel IDC, hay bất kỳ nhà cung cấp nào) có
# chạy nổi ClinicAI không — TRƯỚC khi chuyển dữ liệu sang.
#
#   ./scripts/kiem-database-ngoai.sh
#
# Hỏi thông tin kết nối ngay tại chỗ. MẬT KHẨU GÕ KHÔNG HIỆN KÝ TỰ và không
# vào lịch sử shell, không vào tệp nào.
#
# VÌ SAO PHẢI KIỂM TRƯỚC. Một database quản lý (managed) không phải Postgres
# trần: nhà cung cấp thường không cho đổi tham số máy chủ, không cấp vai có
# quyền cao, và chỉ cho cài extension trong danh sách trắng. Ba thứ ấy đều là
# thứ ClinicAI cần, và thiếu cái nào cũng hỏng theo một kiểu riêng:
#
#   thiếu PG15+          lược đồ KHÔNG dựng nổi — 7 view dùng security_invoker
#   thiếu wal_level      realtime nối được nhưng KHÔNG nhận sự kiện nào
#   thiếu vai REPLICATION/BYPASSRLS/CREATEROLE
#                        GoTrue không dựng được schema đăng nhập; backend không
#                        bỏ qua RLS được
#   thiếu extension      dò tên tiếng Việt không dấu và chống trùng lịch hỏng
#
# Cái thứ hai là cái tệ nhất: nó KHÔNG báo lỗi, chỉ im lặng không cập nhật.

set -euo pipefail

doc() { printf '\n\033[1m── %s\033[0m\n' "$*"; }
dat() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
hong() { printf '  \033[31m✗\033[0m %s\n' "$*"; }
canh() { printf '  \033[33m!\033[0m %s\n' "$*"; }

command -v psql >/dev/null || { echo "cần psql: sudo apt install -y postgresql-client" >&2; exit 1; }

read -rp "Host      : " HOST
read -rp "Port [5432]: " PORT; PORT="${PORT:-5432}"
read -rp "Database  : " DBNAME
read -rp "Username  : " DBUSER
# -s = không hiện ký tự. Mật khẩu chỉ sống trong biến môi trường của tiến trình
# này, không ghi ra đâu cả.
read -rsp "Password  : " DBPASS; echo
read -rp "SSL (require/prefer/disable) [require]: " SSLMODE; SSLMODE="${SSLMODE:-require}"

export PGPASSWORD="$DBPASS"
CN=(-h "$HOST" -p "$PORT" -d "$DBNAME" -U "$DBUSER" -X -tAq)
export PGSSLMODE="$SSLMODE"

LOI=0

doc "0 · Kết nối"
if ! psql "${CN[@]}" -c "select 1" >/dev/null 2>&1; then
    hong "không kết nối được — kiểm host/port/user/mật khẩu/SSL, và tường lửa phía Viettel"
    exit 1
fi
dat "kết nối được"

doc "1 · Phiên bản (cần ≥ 15)"
V=$(psql "${CN[@]}" -c "show server_version")
VMAJ=${V%%.*}
if [ "${VMAJ:-0}" -ge 15 ]; then dat "PostgreSQL $V"
else hong "PostgreSQL $V — 7 view dùng security_invoker, cần ≥ 15"; LOI=1; fi

doc "2 · wal_level (cần logical, cho realtime)"
W=$(psql "${CN[@]}" -c "show wal_level" 2>/dev/null || echo "?")
if [ "$W" = "logical" ]; then dat "wal_level = logical"
else
    hong "wal_level = $W"
    canh "realtime sẽ NỐI ĐƯỢC nhưng KHÔNG nhận sự kiện — hỏng im lặng."
    canh "Hỏi Viettel có đổi được không. Không được thì bỏ realtime, dùng"
    canh "cách tự làm mới màn hình (LiveBoardSync) — chậm hơn vài giây."
    LOI=1
fi

doc "3 · Tạo vai có quyền cao"
for Q in REPLICATION BYPASSRLS CREATEROLE; do
    if psql "${CN[@]}" -c "CREATE ROLE __thu_$Q $Q; DROP ROLE __thu_$Q;" >/dev/null 2>&1; then
        dat "tạo được vai có $Q"
    else
        hong "KHÔNG tạo được vai có $Q"
        [ "$Q" = "BYPASSRLS" ] && canh "BYPASSRLS là BẮT BUỘC — backend chạy bằng vai đó"
        [ "$Q" = "CREATEROLE" ] && canh "CREATEROLE cần cho GoTrue dựng schema đăng nhập"
        LOI=1
    fi
done

doc "4 · Sáu extension"
for E in pgcrypto uuid-ossp pg_trgm unaccent btree_gist pg_stat_statements; do
    if psql "${CN[@]}" -c "CREATE EXTENSION IF NOT EXISTS \"$E\"" >/dev/null 2>&1; then
        dat "$E"
    else
        hong "$E — không cài được"
        LOI=1
    fi
done

doc "5 · Tạo schema (auth · realtime · extensions)"
if psql "${CN[@]}" -c "CREATE SCHEMA IF NOT EXISTS __thu_schema; DROP SCHEMA __thu_schema;" >/dev/null 2>&1; then
    dat "tạo được schema mới"
else
    hong "KHÔNG tạo được schema — GoTrue cần schema auth riêng"; LOI=1
fi

doc "6 · Publication cho realtime"
if psql "${CN[@]}" -c "CREATE PUBLICATION __thu_pub; DROP PUBLICATION __thu_pub;" >/dev/null 2>&1; then
    dat "tạo được publication"
else
    hong "KHÔNG tạo được publication — chuỗi migration gọi ALTER PUBLICATION"; LOI=1
fi

doc "7 · Độ trễ từ máy này tới database"
# Con số này quyết định có phải gộp bớt truy vấn ở vài màn hình không. Đo bằng
# 20 lượt đi-về thật, không phải ping — ping đo đường mạng, cái mình cần là
# đường mạng CỘNG thời gian Postgres trả lời.
T0=$(python3 -c "import time;print(time.time())")
for _ in $(seq 1 20); do psql "${CN[@]}" -c "select 1" >/dev/null; done
T1=$(python3 -c "import time;print(time.time())")
MS=$(python3 -c "print(f'{($T1-$T0)*1000/20:.1f}')")
echo "  $MS ms mỗi lượt đi-về"
python3 -c "
ms=float('$MS')
print('  \033[32m✓\033[0m gần như không cảm nhận được' if ms<5 else
      '  \033[33m!\033[0m chấp nhận được, nhưng nên gộp bớt truy vấn ở màn nhiều dữ liệu' if ms<20 else
      '  \033[31m✗\033[0m CAO — mỗi màn hình gọi vài truy vấn là người dùng thấy chậm')"

unset PGPASSWORD
doc "Kết luận"
if [ "$LOI" -eq 0 ]; then
    dat "Đủ điều kiện. Chuyển sang được."
else
    hong "Có mục chưa đạt ở trên. Đọc phần chú thích của từng mục để biết mất gì."
fi
exit "$LOI"
