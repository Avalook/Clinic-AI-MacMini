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
# ĐẾM KÝ TỰ, KHÔNG IN MẬT KHẨU.
#
# Ô gõ mù nên không có cách nào biết cái gì thật sự vào được: dán hụt ra 0 ký
# tự, dán dính dấu cách ra thừa một, gõ tay sai một phím ra đúng số nhưng sai
# nội dung. Cả ba đều hiện ra y hệt nhau — "password authentication failed" —
# và người dùng gõ lại lần thứ ba vẫn không biết mình đang sửa cái gì.
#
# Con số này phân biệt được hai trong ba: 0 là dán hụt, và lệch so với độ dài
# mình đặt là gõ thiếu/thừa. Nó KHÔNG lộ gì — độ dài không giúp ai đoán ra mật
# khẩu.
#
# Không cần kiểm khoảng trắng đầu/cuối: `read` đã tự cắt chúng theo IFS mặc
# định. Thử rồi — dán chuỗi có hai dấu cách mỗi đầu vẫn ra đúng số ký tự ruột.
printf '            (nhận được %d ký tự)\n' "${#DBPASS}"
read -rp "SSL (require/prefer/disable) [require]: " SSLMODE; SSLMODE="${SSLMODE:-require}"

export PGPASSWORD="$DBPASS"
CN=(-h "$HOST" -p "$PORT" -d "$DBNAME" -U "$DBUSER" -X -tAq)
export PGSSLMODE="$SSLMODE"

LOI=0

doc "0 · Kết nối"
# IN NGUYÊN LỜI BÁO LỖI CỦA POSTGRES, đừng nuốt nó.
#
# Bản đầu nuốt stderr rồi in một câu chung chung "kiểm host/port/user/mật
# khẩu/SSL". Câu đó đúng mà vô dụng: nó liệt kê năm khả năng trong khi Postgres
# vừa nói thẳng ra là cái nào. "password authentication failed" và "no
# pg_hba.conf entry for host" và "SSL required" là ba việc phải sửa ở ba nơi
# khác nhau — bắt người dùng đoán giữa chúng là bắt họ thử mò năm lần.
if ! LOI_KETNOI="$(psql "${CN[@]}" -c "select 1" 2>&1 >/dev/null)"; then
    hong "không kết nối được. Postgres nói:"
    printf '\n%s\n\n' "$LOI_KETNOI" | sed 's/^/      /'
    case "$LOI_KETNOI" in
        *"password authentication failed"*)
            canh "Sai mật khẩu, hoặc sai tên đăng nhập. Đổi lại mật khẩu ở"
            canh "màn Users bên Viettel nếu không chắc." ;;
        *"no pg_hba.conf entry"*|*"pg_hba"*)
            canh "Máy chủ TỪ CHỐI địa chỉ này hoặc kiểu SSL này — không phải sai"
            canh "mật khẩu. Hỏi Viettel xem IP máy chủ đã được cho phép chưa." ;;
        *"SSL"*|*"ssl"*)
            canh "Vướng SSL. Thử lại với sslmode = prefer." ;;
        *"does not exist"*)
            canh "Tên database hoặc tên người dùng không tồn tại. Thử database"
            canh "'postgres' — mọi PostgreSQL đều có sẵn nó." ;;
        *"timeout"*|*"could not connect"*|*"Connection refused"*)
            canh "Không tới được máy. Cổng có thể mở nhưng dịch vụ không nghe,"
            canh "hoặc tường lửa chặn ở tầng sau." ;;
    esac
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
# ĐO HAI THỨ RIÊNG RA, VÌ CHÚNG QUYẾT ĐỊNH HAI CHUYỆN KHÁC NHAU.
#
# Bản đầu chạy `psql -c "select 1"` HAI MƯƠI LẦN rồi chia trung bình — mỗi lần
# là một tiến trình mới, một kết nối TCP mới, một lượt xác thực mới. Con số ra
# 208ms và bị đọc thành "mỗi truy vấn mất 208ms", trong khi phần lớn số đó là
# tiền BẮT TAY, thứ mà ứng dụng thật trả đúng một lần: asyncpg giữ sẵn một bể
# kết nối, không mở lại cho từng câu lệnh. Đo sai kiểu ấy suýt làm mình loại
# một database chỉ vì cách đo.
#
# Nay: T_mot = 1 kết nối + 1 truy vấn. T_hai_muoi = 1 kết nối + 20 truy vấn.
# Hiệu của chúng chia 19 = thời gian MỘT truy vấn trên kết nối có sẵn, đã trừ
# sạch tiền bắt tay. Còn tiền bắt tay in riêng, vì nó vẫn có ý nghĩa: bể kết
# nối lúc khởi động và lúc phải mở thêm kết nối đều phải trả nó.
MOT_CAU="select 1;"
HAI_MUOI="$(printf 'select 1;%.0s' $(seq 1 20))"

T0=$(python3 -c "import time;print(time.time())")
psql "${CN[@]}" -c "$MOT_CAU" >/dev/null 2>&1
T1=$(python3 -c "import time;print(time.time())")
psql "${CN[@]}" -c "$HAI_MUOI" >/dev/null 2>&1
T2=$(python3 -c "import time;print(time.time())")

read -r BAT_TAY MS <<<"$(python3 -c "
mot = ($T1 - $T0) * 1000
hai_muoi = ($T2 - $T1) * 1000
moi_cau = max((hai_muoi - mot) / 19, 0.0)
print(f'{mot - moi_cau:.0f} {moi_cau:.1f}')")"

echo "  $MS ms mỗi truy vấn (trên kết nối có sẵn — đây là con số ứng dụng thật chịu)"
echo "  ${BAT_TAY} ms để mở một kết nối mới (chỉ trả lúc bể kết nối khởi động)"
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
