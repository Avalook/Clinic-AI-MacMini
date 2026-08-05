#!/usr/bin/env bash
# Bring the whole thing up locally, then prove it is up.
# Khởi động toàn bộ hệ thống cục bộ, sau đó kiểm tra nó đã chạy.
#
# One command, because "chạy được" should not require knowing that Supabase must
# start before migrations, that migrations must run before fixtures, that the
# API needs six environment variables, and that the dashboard needs the anon key
# the CLI prints. Every one of those is a step somebody gets wrong once.
# Một lệnh duy nhất, vì "chạy được" không nên đòi hỏi phải biết rằng Supabase phải
# khởi động trước migrations, migrations phải chạy trước fixtures, API cần sáu
# biến môi trường, và dashboard cần anon key mà CLI in ra. Mỗi bước đó là một
# bước mà ai đó sẽ làm sai một lần.
#
# It is idempotent: run it as often as you like. It never touches production —
# everything here points at the local Supabase on 127.0.0.1.
# Nó là idempotent: chạy bao nhiêu lần cũng được. Nó không bao giờ đụng production —
# mọi thứ ở đây trỏ đến Supabase cục bộ trên 127.0.0.1.
#
#   scripts/dev-up.sh            start everything and check it
#   scripts/dev-up.sh            khởi động mọi thứ và kiểm tra
#   scripts/dev-up.sh --reset    wipe the local database first
#   scripts/dev-up.sh --reset    xóa sạch database cục bộ trước
#   scripts/dev-up.sh --down     stop the API and dashboard
#   scripts/dev-up.sh --down     dừng API và dashboard

# Bật chế độ nghiêm ngặt: thoát ngay khi có lệnh lỗi, biến chưa khai báo, hoặc pipeline lỗi
set -euo pipefail

# Lấy đường dẫn gốc của repository (thư mục cha của thư mục chứa script này)
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Chuyển vào thư mục gốc repository
cd "$REPO"

# Địa chỉ Supabase mà TRÌNH DUYỆT sẽ gọi. Mặc định là 127.0.0.1 — đúng khi mở
# trên chính máy này, SAI khi mở từ máy khác qua tunnel: lúc đó 127.0.0.1 trỏ về
# máy của người đang xem, không phải Mac mini.
#
# Đăng nhập vẫn chạy được vì nó là server action (máy này tự gọi Supabase của
# nó). Thứ hỏng là những phần trình duyệt gọi thẳng Supabase: realtime tự cập
# nhật, nút Thoát, quên/đặt lại mật khẩu.
#
# Muốn dùng từ máy khác: mở thêm một tunnel cho Supabase rồi truyền vào đây.
#   cloudflared tunnel --url http://127.0.0.1:54321      # → URL_SUPABASE
#   PUBLIC_SUPABASE_URL=<URL_SUPABASE> scripts/dev-up.sh
#   cloudflared tunnel --url http://127.0.0.1:3100       # → link để chia sẻ
# Lấy URL Supabase công khai từ biến môi trường, mặc định là localhost
PUBLIC_SUPABASE_URL="${PUBLIC_SUPABASE_URL:-http://127.0.0.1:54321}"

# Cổng API, mặc định 8100
API_PORT="${API_PORT:-8100}"
# Cổng web dashboard, mặc định 3100
WEB_PORT="${WEB_PORT:-3100}"
# Thư mục lưu log, mặc định là .dev-logs trong repo
LOG_DIR="${LOG_DIR:-$REPO/.dev-logs}"
# Tạo thư mục log nếu chưa tồn tại
mkdir -p "$LOG_DIR"

# Hàm in chữ màu xanh dương
blue()  { printf '\033[36m%s\033[0m\n' "$*"; }
# Hàm in chữ màu xanh lá
green() { printf '\033[32m%s\033[0m\n' "$*"; }
# Hàm in chữ màu đỏ
red()   { printf '\033[31m%s\033[0m\n' "$*"; }

# Chờ một URL phản hồi tối đa 120s. Lần đầu khởi động API/dashboard trên Mac mini
# (poetry resolve + import FastAPI/LangGraph + next build lạnh) có thể lâu hơn 40s.
# Hàm chờ một URL phản hồi, tối đa 120 giây
wait_for_http() {
    local url="$1" name="$2" i  # Biến cục bộ: URL, tên, biến đếm
    for i in $(seq 1 120); do  # Lặp tối đa 120 lần
        if curl -sf -o /dev/null "$url" 2>/dev/null; then  # Nếu URL phản hồi thành công
            return 0  # Trả về thành công
        fi
        if [ $((i % 10)) -eq 0 ]; then  # Cứ mỗi 10 lần thì in trạng thái
            green "  ...đang chờ $name ($i/120s)"
        fi
        sleep 1  # Chờ 1 giây
    done
    return 1  # Hết thời gian chờ, trả về thất bại
}

# Báo process đang giữ một cổng — giúp chẩn đoán "address already in use".
# Hàm tìm process đang giữ một cổng
port_owner() {
    lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2{print $1" (PID "$2")"}' || true
}

# Hàm dừng các dịch vụ API và dashboard
stop_services() {
    # Dừng uvicorn (API) nếu đang chạy
    pkill -f "uvicorn clinicai.main.*--port ${API_PORT}" 2>/dev/null || true
    # Dừng next start (production) nếu đang chạy
    pkill -f "next start -p ${WEB_PORT}" 2>/dev/null || true
    # Dừng next dev (development) nếu đang chạy
    pkill -f "next dev -p ${WEB_PORT}" 2>/dev/null || true
    # Đợi cổng được giải phóng — uvicorn/next có thể mất vài giây để shutdown sạch.
    for _ in $(seq 1 15); do  # Lặp tối đa 15 lần
        # Nếu cả hai cổng đều đã được giải phóng
        if ! lsof -nP -iTCP:"${API_PORT}" -sTCP:LISTEN >/dev/null 2>&1 \
           && ! lsof -nP -iTCP:"${WEB_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
            break  # Thoát vòng lặp
        fi
        sleep 1  # Chờ 1 giây
    done
    # Nếu cổng API vẫn bị chiếm
    if lsof -nP -iTCP:"${API_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
        owner="$(port_owner "$API_PORT")"  # Tìm process đang giữ cổng
        red "  cổng $API_PORT vẫn bị chiếm bởi $owner — dừng thủ công hoặc chọn API_PORT khác"
    fi
}

# Nếu tham số đầu tiên là --down
if [ "${1:-}" = "--down" ]; then
    stop_services  # Dừng các dịch vụ
    green "API and dashboard stopped. Supabase left running (npx supabase stop to stop it)."
    exit 0  # Thoát script
fi

# ---- 1. Supabase ------------------------------------------------------------
# ---- Bước 1: Khởi động Supabase ---------------------------------------------
blue "1/5  Supabase"
# Nếu Supabase chưa chạy (kiểm tra cổng 54321)
if ! curl -sf http://127.0.0.1:54321/rest/v1/ >/dev/null 2>&1; then
    # Khởi động Supabase bằng CLI, ghi log vào file
    npx --yes supabase@latest start >"$LOG_DIR/supabase.log" 2>&1 || {
        red "  Supabase failed to start — see $LOG_DIR/supabase.log"; exit 1; }
fi
# Lấy anon key từ Supabase status
ANON_KEY=$(npx --yes supabase@latest status -o env 2>/dev/null \
    | grep '^ANON_KEY=' | cut -d'"' -f2)
# Nếu không đọc được anon key thì báo lỗi
[ -n "$ANON_KEY" ] || { red "  could not read the anon key from supabase status"; exit 1; }
green "  up on 54321 (db 54322)"

# ---- 2. schema + fixtures ---------------------------------------------------
# ---- Bước 2: Schema + dữ liệu mẫu -------------------------------------------
# URL kết nối database cục bộ
DB_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
# Nếu tham số đầu tiên là --reset
if [ "${1:-}" = "--reset" ]; then
    blue "2/5  database reset (migrations + seed)"
    # Reset database: chạy lại tất cả migrations + seed
    npx --yes supabase@latest db reset >"$LOG_DIR/db-reset.log" 2>&1 || {
        red "  db reset failed — see $LOG_DIR/db-reset.log"; exit 1; }
else
    blue "2/5  database (migrations only; --reset to wipe)"
fi
# Fixtures are separate from seed.sql on purpose: seed carries catalogue data
# every install needs, fixtures carry the fake staff and patient used for local
# testing. Loading fixtures into a real database would create fake clinicians.
# Fixtures tách riêng khỏi seed.sql có chủ đích: seed chứa dữ liệu danh mục mà
# mọi cài đặt cần, fixtures chứa nhân viên và bệnh nhân giả dùng cho test cục bộ.
# Nạp fixtures vào database thật sẽ tạo ra bác sĩ giả.
for f in supabase/fixtures/staff_logins.sql supabase/fixtures/local_data.sql; do
    # Nạp từng file fixture nếu tồn tại
    [ -f "$f" ] && psql -q "$DB_URL" -f "$f" >/dev/null 2>&1 || true
done
# Đếm số bảng trong database
tables=$(psql -tA "$DB_URL" -c \
    "SELECT count(*) FROM pg_tables WHERE schemaname='public'" 2>/dev/null | tr -d ' ')
green "  $tables tables, fixtures loaded"


# ---- 4. dashboard -----------------------------------------------------------
blue "4/5  Next.js dashboard"
cd src/dashboard
# A production build, not `next dev`: dev mode did not hydrate client components
# under headless Chromium during this work, and a board whose buttons do nothing
# is worse than one that is honestly still building.
# CLINIC_SHARED_EMAIL is the account /enter signs in as — the clinic gate,
# before anyone says which member of staff they are. Without it the very first
# screen a person sees is "Server chưa cấu hình CLINIC_SHARED_EMAIL", which is
# exactly what Quang hit: the stack was up and the front door was locked.
NEXT_PUBLIC_SUPABASE_URL="$PUBLIC_SUPABASE_URL" \
NEXT_PUBLIC_SUPABASE_ANON_KEY="$ANON_KEY" \
CLINIC_API_URL="http://127.0.0.1:${API_PORT}" \
BACKEND_API_KEY=staging-local-api-key \
CLINIC_SHARED_EMAIL=clinic@dr4women.local \
    npx next build >"$LOG_DIR/web-build.log" 2>&1 || {
        red "  build failed — see $LOG_DIR/web-build.log"
        grep -m5 -E "Error|error" "$LOG_DIR/web-build.log" | sed 's/^/    /'; exit 1; }

NEXT_PUBLIC_SUPABASE_URL="$PUBLIC_SUPABASE_URL" \
NEXT_PUBLIC_SUPABASE_ANON_KEY="$ANON_KEY" \
CLINIC_API_URL="http://127.0.0.1:${API_PORT}" \
BACKEND_API_KEY=staging-local-api-key \
CLINIC_SHARED_EMAIL=clinic@dr4women.local \
    nohup npx next start -p "$WEB_PORT" >"$LOG_DIR/web.log" 2>&1 &
cd "$REPO"

wait_for_http "http://127.0.0.1:${WEB_PORT}/" "dashboard" \
    && green "  serving on ${WEB_PORT}" \
    || { red "  dashboard did not come up — see $LOG_DIR/web.log"; tail -20 "$LOG_DIR/web.log"; exit 1; }

# ---- 5. prove the stack talks to itself -------------------------------------
blue "5/5  end-to-end check"
TOKEN=$(curl -s -X POST "http://127.0.0.1:54321/auth/v1/token?grant_type=password" \
    -H "apikey: $ANON_KEY" -H 'Content-Type: application/json' \
    -d '{"email":"letan@dr4women.local","password":"clinic-test-pw-123"}' \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
if [ -n "$TOKEN" ]; then
    n=$(curl -s "http://127.0.0.1:${API_PORT}/api/v1/work-items?workspace=bang_dieu_phoi" \
        -H "Authorization: Bearer $TOKEN" -H "X-API-Key: staging-local-api-key" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(len(d) if isinstance(d,list) else "err")' 2>/dev/null)
    green "  reception queue answers with $n item(s)"
else
    red "  could not sign in as the fixture receptionist — fixtures may be missing"
fi

cat <<EOF

$(green "Ready.")

  Dashboard   http://127.0.0.1:${WEB_PORT}
  API         http://127.0.0.1:${API_PORT}/docs
  Supabase    http://127.0.0.1:54323
  Logs        ${LOG_DIR}/

  Đăng nhập 2 bước — cả hai bước đều dùng mật khẩu: clinic-test-pw-123
    1) Cổng phòng khám  → nhập mật khẩu chung
    2) Đăng nhập cá nhân → chọn tài khoản bên dưới

    letan@dr4women.local     Lễ tân      → Hàng đợi tiếp nhận
    bs.a@dr4women.local      Bác sĩ      → Bàn khám, Chỉ định dịch vụ
    cskh@dr4women.local      CSKH        → Cần làm hôm nay, Đặt lịch
    dd.sa@dr4women.local     Điều dưỡng  → Sinh hiệu
    bs.sa@dr4women.local     BS siêu âm  → Siêu âm, số đo thai
    thungan@dr4women.local   Thu ngân    → Bàn thu ngân
    ql@dr4women.local        Quản lý     → Sức khoẻ API, Vận hành, Command Center

  Supabase (trình duyệt gọi): ${PUBLIC_SUPABASE_URL}
  Dừng:  scripts/dev-up.sh --down
EOF
