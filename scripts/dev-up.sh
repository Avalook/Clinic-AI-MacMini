#!/usr/bin/env bash
# Bring the whole thing up locally, then prove it is up.
#
# One command, because "chạy được" should not require knowing that Supabase must
# start before migrations, that migrations must run before fixtures, that the
# API needs six environment variables, and that the dashboard needs the anon key
# the CLI prints. Every one of those is a step somebody gets wrong once.
#
# It is idempotent: run it as often as you like. It never touches production —
# everything here points at an isolated local copy on 127.0.0.1.
#
#   scripts/dev-up.sh            start everything and check it
#   scripts/dev-up.sh --reset    wipe the TEST database first (chỉ volume của project clinicai_thu_db)
#   scripts/dev-up.sh --down     stop the API and dashboard
#
# "Ready." CHỈ in khi mọi bước đã qua — kể cả đăng nhập thật từng tài khoản thử
# và nạp đủ dữ liệu demo. Bước nào hỏng thì dừng ngay, thoát khác 0, chỉ ra log.
# Trước 11/09 đăng nhập hỏng và ngày demo hỏng vẫn in "Ready.", nên một stack
# rỗng trông y hệt một stack dùng được.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
#   cloudflared tunnel --url http://127.0.0.1:54421      # → URL_SUPABASE
#   PUBLIC_SUPABASE_URL=<URL_SUPABASE> scripts/dev-up.sh
#   cloudflared tunnel --url http://127.0.0.1:3100       # → link để chia sẻ
# Mặc định đặt ở bước 1, sau khi đọc cổng từ .env.thu-local.
PUBLIC_SUPABASE_URL="${PUBLIC_SUPABASE_URL:-}"

# TỰ NẠP LẠI KHI SỬA PYTHON — mặc định BẬT ở local.
#
# Hai phiên liên tiếp mất thời gian vì cùng một chuyện: sửa Python xong, gọi API,
# thấy hành vi CŨ, rồi đi tìm lỗi ở chỗ không có lỗi. Máy chủ chạy bản đã nạp
# vào bộ nhớ từ trước; không ai bảo nó biết file đã đổi.
#
# `--reload` trả tiền bằng một tiến trình theo dõi file và khoảng 1 giây mỗi lần
# nạp lại — rẻ hơn nhiều so với một lần đuổi theo con ma ấy. Tắt bằng
# `TU_NAP_LAI= scripts/dev-up.sh` khi cần đo tốc độ cho chuẩn.
TU_NAP_LAI="${TU_NAP_LAI-"--reload --reload-dir src/clinicai"}"
API_PORT="${API_PORT:-8100}"
WEB_PORT="${WEB_PORT:-3100}"
LOG_DIR="${LOG_DIR:-$REPO/.dev-logs}"
mkdir -p "$LOG_DIR"

# Mật khẩu chung của mọi tài khoản GIẢ trong supabase/fixtures (@dr4women.local).
# Ghi đè được qua môi trường — giá trị dưới chỉ là mặc định cho stack thử
# trên 127.0.0.1, không phải bí mật vận hành.
TEST_PW="${TEST_PW:-clinic-test-pw-123}"
TAI_KHOAN_THU="letan bs.a cskh dd.sa bs.sa thungan ql thuky truongca doitac danang"

blue()  { printf '\033[36m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }

# Chờ một URL phản hồi tối đa 120s. Lần đầu khởi động API/dashboard trên Mac mini
# (poetry resolve + import FastAPI/LangGraph + next build lạnh) có thể lâu hơn 40s.
wait_for_http() {
    local url="$1" name="$2" i
    for i in $(seq 1 120); do
        if curl -sf -o /dev/null "$url" 2>/dev/null; then
            return 0
        fi
        if [ $((i % 10)) -eq 0 ]; then
            green "  ...đang chờ $name ($i/120s)"
        fi
        sleep 1
    done
    return 1
}

# Báo process đang giữ một cổng — giúp chẩn đoán "address already in use".
port_owner() {
    lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2{print $1" (PID "$2")"}' || true
}

stop_services() {
    pkill -f "uvicorn clinicai.main.*--port ${API_PORT}" 2>/dev/null || true
    pkill -f "clinicai.worker --su-kien" 2>/dev/null || true
    pkill -f "next start -p ${WEB_PORT}" 2>/dev/null || true
    pkill -f "next dev -p ${WEB_PORT}" 2>/dev/null || true
    # Đợi cổng được giải phóng — uvicorn/next có thể mất vài giây để shutdown sạch.
    for _ in $(seq 1 15); do
        if ! lsof -nP -iTCP:"${API_PORT}" -sTCP:LISTEN >/dev/null 2>&1 \
           && ! lsof -nP -iTCP:"${WEB_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    if lsof -nP -iTCP:"${API_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
        owner="$(port_owner "$API_PORT")"
        red "  cổng $API_PORT vẫn bị chiếm bởi $owner — dừng thủ công hoặc chọn API_PORT khác"
    fi
}

if [ "${1:-}" = "--down" ]; then
    stop_services
    green "Đã dừng API và dashboard. Bộ Supabase thử vẫn chạy — dừng: docker compose -p clinicai_thu_db stop"
    exit 0
fi

# ---- 1. bộ Supabase tự dựng, GIỐNG MÁY CHỦ ----------------------------------
# VÌ SAO KHÔNG CÒN `npx supabase start`. Prod và staging trên máy chủ không chạy
# Supabase CLI và không dùng Supabase Cloud. Chúng chạy docker-compose.supabase.yml:
# postgres:17 gốc, GoTrue + PostgREST + Realtime ghim phiên bản, Caddy làm cổng,
# vai và extension do docker/supabase/init tạo, lược đồ nạp bằng psql. Bộ của CLI
# là một bộ KHÁC: ảnh Postgres riêng của Supabase dựng sẵn vai và extension, Kong
# thay Caddy, phiên bản trôi theo "latest". Xanh trên bộ đó không nói được gì về
# máy chủ.
#
# CÁCH LY — cùng ba điều dung-staging.sh đòi: tiền tố container riêng
# (`clinicai_thu`), khoá JWT riêng (sinh mới vào .env.thu-local, đã gitignore),
# cổng riêng (54421 cổng, 54422 database). Volume thuộc project `clinicai_thu_db`.
blue "1/5  bộ Supabase tự dựng (cùng file compose với máy chủ)"
SB_ENV="$REPO/.env.thu-local"
SB_PROJECT="clinicai_thu_db"
SB_PREFIX_DUNG="clinicai_thu"
SB_COMPOSE=(docker compose --env-file "$SB_ENV" -f "$REPO/docker-compose.supabase.yml" -p "$SB_PROJECT")
if [ ! -f "$SB_ENV" ]; then
    (
        umask 077
        {
            # Bộ sinh khoá tự in cổng mặc định của prod — bỏ, dùng cổng riêng.
            python3 "$REPO/scripts/sinh-khoa-supabase.py" | grep -vE '^SUPABASE_(API|DB)_PORT='
            echo "SUPABASE_PREFIX=${SB_PREFIX_DUNG}"
            echo "SUPABASE_API_PORT=54421"
            echo "SUPABASE_DB_PORT=54422"
            echo "SITE_URL=http://127.0.0.1:${WEB_PORT}"
            echo "REALTIME_DB_ENC_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
        } >"$SB_ENV"
    )
    green "  đã sinh khoá riêng vào .env.thu-local"
fi
set -a
# shellcheck disable=SC1090
. "$SB_ENV"
set +a
# Khoá trùng prod/staging là token đi chéo được — dừng, như dung-staging.sh.
for bien in SUPABASE_JWT_SECRET SUPABASE_DB_PASSWORD; do
    for khac in .env.prod .env.staging; do
        [ -f "$REPO/$khac" ] || continue
        b="$(grep -E "^${bien}=" "$REPO/$khac" | cut -d= -f2- || true)"
        if [ -n "$b" ] && [ "$b" = "${!bien}" ]; then
            red "  $bien trùng $khac — xoá .env.thu-local để sinh khoá mới"; exit 1
        fi
    done
done

# CHỐT ĐÍCH. Mọi bước sau (down -v, nạp lược đồ, fixture giả) chạm database QUA
# TÊN CONTAINER. Tiền tố bị sửa thành `clinicai` là `docker exec clinicai_db` —
# đúng tên container của PROD — và fixture sẽ tạo bác sĩ giả trong database thật.
# Nên không đoán, không mặc định: tiền tố, cổng, nhãn project, volume đều phải khớp.
if [ "${SUPABASE_PREFIX:-}" != "$SB_PREFIX_DUNG" ]; then
    red "  SUPABASE_PREFIX trong .env.thu-local phải là $SB_PREFIX_DUNG (đang là '${SUPABASE_PREFIX:-trống}') — dừng"
    exit 1
fi
if [ "${SUPABASE_API_PORT:-}" != "54421" ] || [ "${SUPABASE_DB_PORT:-}" != "54422" ]; then
    red "  cổng trong .env.thu-local phải là 54421/54422 (đang là ${SUPABASE_API_PORT:-?}/${SUPABASE_DB_PORT:-?}) — dừng"
    exit 1
fi
PUBLIC_SUPABASE_URL="${PUBLIC_SUPABASE_URL:-http://127.0.0.1:${SUPABASE_API_PORT}}"
DB_CONTAINER="${SB_PREFIX_DUNG}_db"
SB_VOLUME="${SB_PROJECT}_db_data"
psql_db() { docker exec -i "$DB_CONTAINER" psql -U postgres -d postgres -X -q -v ON_ERROR_STOP=1 "$@"; }

nhan_project_container() {
    docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$1" 2>/dev/null || true
}
nhan_project_volume() {
    docker volume inspect -f '{{ index .Labels "com.docker.compose.project" }}' "$1" 2>/dev/null || true
}
# Tên trùng mà nhãn khác (một stack khác tình cờ đặt cùng tên) cũng là sai đích.
kiem_dich() {
    local p
    if docker inspect "$DB_CONTAINER" >/dev/null 2>&1; then
        p="$(nhan_project_container "$DB_CONTAINER")"
        if [ "$p" != "$SB_PROJECT" ]; then
            red "  container $DB_CONTAINER thuộc project '${p:-không nhãn}', không phải $SB_PROJECT — dừng"
            exit 1
        fi
    fi
    if docker volume inspect "$SB_VOLUME" >/dev/null 2>&1; then
        p="$(nhan_project_volume "$SB_VOLUME")"
        if [ "$p" != "$SB_PROJECT" ]; then
            red "  volume $SB_VOLUME thuộc project '${p:-không nhãn}', không phải $SB_PROJECT — dừng"
            exit 1
        fi
    fi
}

kiem_dich
if [ "${1:-}" = "--reset" ]; then
    # `down -v` của compose chỉ gỡ volume mang nhãn project này. In ra trước khi
    # xoá để thấy tận mắt: không có bộ Supabase CLI cũ, không có container test
    # khác, không có gì của prod/staging.
    xoa="$(docker volume ls -q --filter "label=com.docker.compose.project=${SB_PROJECT}" | tr '\n' ' ')"
    blue "     --reset: xoá volume của bộ THỬ $SB_PROJECT: ${xoa:-(chưa có volume nào)}"
    "${SB_COMPOSE[@]}" down -v >"$LOG_DIR/supabase-down.log" 2>&1 || {
        red "  down -v hỏng — xem $LOG_DIR/supabase-down.log"; tail -5 "$LOG_DIR/supabase-down.log"; exit 1; }
fi
"${SB_COMPOSE[@]}" up -d >"$LOG_DIR/supabase.log" 2>&1 || {
    red "  bộ Supabase không lên — xem $LOG_DIR/supabase.log"; tail -5 "$LOG_DIR/supabase.log"; exit 1; }
wait_for_http "http://127.0.0.1:${SUPABASE_API_PORT}/health" "cổng Supabase" \
    && green "  cổng ${SUPABASE_API_PORT}, database ${SUPABASE_DB_PORT}" \
    || { red "  cổng Supabase không trả lời — xem: ${SB_COMPOSE[*]} logs"; exit 1; }

# Kiểm lại SAU khi lên: container phải tồn tại, đúng nhãn, và gắn đúng volume.
kiem_dich
docker inspect "$DB_CONTAINER" >/dev/null 2>&1 || { red "  không thấy $DB_CONTAINER sau khi dựng — dừng"; exit 1; }
vol_gan="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$DB_CONTAINER")"
if [ "$vol_gan" != "$SB_VOLUME" ]; then
    red "  $DB_CONTAINER gắn volume '${vol_gan:-không có}', không phải $SB_VOLUME — dừng"
    exit 1
fi
green "  đích đã kiểm: container $DB_CONTAINER · volume $SB_VOLUME · project $SB_PROJECT"

# Phiên bản THẬT đang chạy, không phải phiên bản ghi trong compose: tag `postgres:17`
# và `caddy:2-alpine` trôi, nên cùng một dòng compose cho ra ảnh khác nhau ở hai máy.
{
    printf 'Bộ thử %s — ghi lúc %s\n' "$SB_PROJECT" "$(date '+%Y-%m-%d %H:%M:%S %z')"
    for c in $("${SB_COMPOSE[@]}" ps -q); do
        ten="$(docker inspect -f '{{.Name}}' "$c" | sed 's#^/##')"
        anh="$(docker inspect -f '{{.Config.Image}}' "$c")"
        dig="$(docker image inspect -f '{{if .RepoDigests}}{{index .RepoDigests 0}}{{end}}' "$anh" 2>/dev/null | sed 's#.*@##')"
        printf '  %-30s %-28s %s\n' "$ten" "$anh" "${dig:-không có digest}"
    done
    printf '  %s\n' "$(docker exec "$DB_CONTAINER" postgres --version)"
} >"$LOG_DIR/phien-ban.txt"

# ---- 2. lược đồ + dữ liệu thử -----------------------------------------------
# Hai đường, đúng hai công cụ máy chủ dùng:
#   database trống → supabase-local-nap.sh: nâng auth.uid(), nạp cả chuỗi, ghi
#                    sổ. Chính script đã dựng clinicai_db của prod.
#   database đã có → apply-pending-migrations.sh --apply: chỉ áp cái còn thiếu,
#                    mỗi cái một giao dịch. Chính công cụ áp migration lên prod.
# Không có đường thứ ba: migration trước 20260730 không chạy lại lần hai được.
blue "2/5  lược đồ + dữ liệu thử"
for _ in $(seq 1 60); do
    docker exec "$DB_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 1
done
MOI=0
if [ "$(psql_db -tAc "SELECT to_regclass('supabase_migrations.schema_migrations') IS NOT NULL" | tr -d ' ')" != "t" ]; then
    MOI=1
    SUPABASE_DB_CONTAINER="$DB_CONTAINER" "$REPO/scripts/supabase-local-nap.sh" >"$LOG_DIR/schema.log" 2>&1 || {
        red "  nạp lược đồ hỏng — xem $LOG_DIR/schema.log"; tail -5 "$LOG_DIR/schema.log"; exit 1; }
    psql_db <"$REPO/supabase/seed.sql" >"$LOG_DIR/seed.log" 2>&1 || {
        red "  seed hỏng — xem $LOG_DIR/seed.log"; tail -5 "$LOG_DIR/seed.log"; exit 1; }
    green "  lược đồ dựng mới + seed"
else
    CLINIC_DB_CONTAINER="$DB_CONTAINER" "$REPO/scripts/apply-pending-migrations.sh" --apply >"$LOG_DIR/schema.log" 2>&1 || {
        red "  áp migration hỏng — xem $LOG_DIR/schema.log"; tail -12 "$LOG_DIR/schema.log"; exit 1; }
    green "  $(grep -E '^(Không còn|Đã áp)' "$LOG_DIR/schema.log" | tail -1)"
fi

# Fixtures tách khỏi seed có chủ ý: seed là danh mục mọi cài đặt đều cần, fixtures
# là nhân viên và bệnh nhân GIẢ. Nạp fixtures vào database thật là tạo bác sĩ giả.
# KHÔNG nuốt lỗi, KHÔNG bỏ qua file thiếu: fixture hỏng hay vắng thì màn hình rỗng
# trông y hệt "chưa có dữ liệu". luot_kham_demo.sql phải đứng SAU staff_logins.sql:
# nó gắn lịch vào bs.a.
for f in staff_logins.sql tai_khoan_da_vai_hom_nay.sql gan_phong_dich_vu_thieu_local.sql gia_thu_local.sql luot_kham_demo.sql local_data.sql; do
    [ -f "$REPO/supabase/fixtures/$f" ] || { red "  thiếu fixture $f — dừng"; exit 1; }
    psql_db <"$REPO/supabase/fixtures/$f" >"$LOG_DIR/fixture-$f.log" 2>&1 || {
        red "  fixture $f hỏng — xem $LOG_DIR/fixture-$f.log"; tail -5 "$LOG_DIR/fixture-$f.log"; exit 1; }
done
# seed nạp lại dịch vụ mà migration này ẩn đi — dung-staging.sh chạy lại nó y như vậy.
if [ "$MOI" = 1 ]; then
    psql_db <"$REPO/supabase/migrations/20260807000007_nam_dich_vu_kham.sql" >"$LOG_DIR/nam-dich-vu.log" 2>&1 || {
        red "  chạy lại 20260807000007_nam_dich_vu_kham hỏng — xem $LOG_DIR/nam-dich-vu.log"; exit 1; }
fi
# PostgREST giữ lược đồ trong bộ nhớ từ lúc khởi động; migration vừa áp không tự
# vào đó (gặp thật trên staging 07/08).
psql_db -c "NOTIFY pgrst, 'reload schema'" >/dev/null
green "  $(psql_db -tAc "SELECT count(*) FROM pg_tables WHERE schemaname='public'" | tr -d ' ') bảng, fixtures đã nạp"

# ---- 2b. một ngày làm việc để bấm ------------------------------------------
# Một stack "đã lên" mà bảng trống thì chưa chạy thử được. demo_clinic_day.sql
# dựng 40 bệnh nhân, 26 lịch hẹn, đẩy tới NHIỀU bước khác nhau. Chỉ chạy khi chưa
# có việc nào đang mở, để không chồng lượt giả lên việc đang dở.
open_items=$(psql_db -tAc "SELECT count(*) FROM work_item WHERE status IN ('PENDING','IN_PROGRESS')" | tr -d ' ')
if [ "${open_items:-0}" = "0" ]; then
    blue "2b/5 dựng một ngày làm việc giả lập"
    psql_db <"$REPO/supabase/fixtures/demo_clinic_day.sql" >"$LOG_DIR/demo-day.log" 2>&1 || {
        red "  dựng ngày giả lập hỏng — xem $LOG_DIR/demo-day.log"; tail -5 "$LOG_DIR/demo-day.log"; exit 1; }
fi
so_demo="$(psql_db -tAc "SELECT count(*) FROM patient WHERE patient_code LIKE 'DEMO-%'" | tr -d ' ')"
so_lk="$(psql_db -tAc "SELECT count(*) FROM appointment a JOIN patient p ON p.clinic_patient_id = a.clinic_patient_id WHERE p.patient_code LIKE 'LK-DEMO-%' AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date" | tr -d ' ')"
if [ "${so_demo:-0}" = "0" ] || [ "${so_lk:-0}" = "0" ]; then
    red "  dữ liệu demo rỗng: ${so_demo:-0} bệnh nhân DEMO-*, ${so_lk:-0} lịch LK-DEMO hôm nay — dừng"
    exit 1
fi
green "  ${so_demo} bệnh nhân DEMO-* · ${so_lk} lịch LK-DEMO hôm nay · $(psql_db -tAc "SELECT count(*) FROM work_item WHERE status IN ('PENDING','IN_PROGRESS')" | tr -d ' ') việc đang mở"

# ---- 2c. đăng nhập thật qua GoTrue, TỪNG tài khoản -------------------------
# Kiểm ở đây chứ không để cuối: next build mất vài phút, đừng bắt người chờ rồi
# mới báo fixture hỏng.
blue "2c/5 đăng nhập GoTrue từng tài khoản thử"
lay_token() {
    curl -s -X POST "http://127.0.0.1:${SUPABASE_API_PORT}/auth/v1/token?grant_type=password" \
        -H "apikey: $SUPABASE_ANON_KEY" -H 'Content-Type: application/json' \
        -d "{\"email\":\"$1\",\"password\":\"${TEST_PW}\"}" \
        | python3 -c 'import sys, json
try:
    print(json.load(sys.stdin).get("access_token", ""))
except Exception:
    print("")' 2>/dev/null || true
}
hong=""
for t in $TAI_KHOAN_THU; do
    [ -n "$(lay_token "$t@dr4women.local")" ] || hong="$hong $t"
done
if [ -n "$hong" ]; then
    red "  không đăng nhập được:$hong — xem: ${SB_COMPOSE[*]} logs auth"
    exit 1
fi
green "  cả $(echo $TAI_KHOAN_THU | wc -w | tr -d ' ') tài khoản đăng nhập được"

# ---- 3. API -----------------------------------------------------------------
blue "3/5  FastAPI"
if lsof -nP -iTCP:"${API_PORT}" -sTCP:LISTEN >/dev/null 2>&1 \
   && ! pgrep -f "uvicorn clinicai.main.*--port ${API_PORT}" >/dev/null 2>&1; then
    owner="$(port_owner "$API_PORT")"
    red "  cổng $API_PORT đang bị chiếm bởi $owner (không phải uvicorn clinicai) — dừng process đó hoặc đổi API_PORT"
    exit 1
fi
stop_services
PYTHONPATH=src \
SUPABASE_URL="http://127.0.0.1:${SUPABASE_API_PORT}" \
DATABASE_URL="postgresql+asyncpg://postgres:${SUPABASE_DB_PASSWORD}@127.0.0.1:${SUPABASE_DB_PORT}/postgres" \
SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-local-not-real}" \
BACKEND_API_KEY="${BACKEND_API_KEY:-staging-local-api-key}" \
CHECKPOINTER_BACKEND=memory APP_ENV=staging POS_ADAPTER=none \
    nohup poetry run uvicorn clinicai.main:app \
        --host 127.0.0.1 --port "$API_PORT" $TU_NAP_LAI >"$LOG_DIR/api.log" 2>&1 &

wait_for_http "http://127.0.0.1:${API_PORT}/health" "API" \
    && green "  healthy on ${API_PORT}" \
    || { red "  API did not come up — see $LOG_DIR/api.log"; tail -20 "$LOG_DIR/api.log"; exit 1; }

# NGƯỜI ĐƯA TIN SỰ KIỆN (24/09/2026). Thiếu nó thì khách check-in xong KHÔNG vào
# hàng nào: khối Hành trình (xếp hàng tư vấn / bác sĩ chính) chạy ở đây, không
# chạy trong API. Cùng biến môi trường với API — chỉ cần Postgres.
pkill -f "clinicai.worker --su-kien" 2>/dev/null || true
PYTHONPATH=src \
DATABASE_URL="postgresql+asyncpg://postgres:${SUPABASE_DB_PASSWORD}@127.0.0.1:${SUPABASE_DB_PORT}/postgres" \
SUPABASE_URL="http://127.0.0.1:${SUPABASE_API_PORT}" \
SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-local-not-real}" \
CHECKPOINTER_BACKEND=memory APP_ENV=staging POS_ADAPTER=none \
    nohup poetry run python -m clinicai.worker --su-kien >"$LOG_DIR/su-kien.log" 2>&1 &
sleep 2
if pgrep -f "clinicai.worker --su-kien" >/dev/null 2>&1; then
    green "  người đưa tin sự kiện đang chạy (log: $LOG_DIR/su-kien.log)"
else
    red "  người đưa tin sự kiện KHÔNG chạy — xem $LOG_DIR/su-kien.log"; tail -20 "$LOG_DIR/su-kien.log"; exit 1
fi

# ---- 4. dashboard -----------------------------------------------------------
blue "4/5  Next.js dashboard"
cd src/dashboard
# A production build, not `next dev`: dev mode did not hydrate client components
# under headless Chromium during this work, and a board whose buttons do nothing
# is worse than one that is honestly still building.
NEXT_PUBLIC_SUPABASE_URL="$PUBLIC_SUPABASE_URL" \
NEXT_PUBLIC_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
SUPABASE_URL="http://127.0.0.1:${SUPABASE_API_PORT}" \
SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
CLINIC_API_URL="http://127.0.0.1:${API_PORT}" \
BACKEND_API_KEY="${BACKEND_API_KEY:-staging-local-api-key}" \
    npx next build >"$LOG_DIR/web-build.log" 2>&1 || {
        red "  build failed — see $LOG_DIR/web-build.log"
        grep -m5 -E "Error|error" "$LOG_DIR/web-build.log" | sed 's/^/    /'; exit 1; }

NEXT_PUBLIC_SUPABASE_URL="$PUBLIC_SUPABASE_URL" \
NEXT_PUBLIC_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
SUPABASE_URL="http://127.0.0.1:${SUPABASE_API_PORT}" \
SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
CLINIC_API_URL="http://127.0.0.1:${API_PORT}" \
BACKEND_API_KEY="${BACKEND_API_KEY:-staging-local-api-key}" \
    nohup npx next start -p "$WEB_PORT" >"$LOG_DIR/web.log" 2>&1 &
cd "$REPO"

wait_for_http "http://127.0.0.1:${WEB_PORT}/login" "dashboard" \
    && green "  serving on ${WEB_PORT}" \
    || { red "  dashboard did not come up — see $LOG_DIR/web.log"; tail -20 "$LOG_DIR/web.log"; exit 1; }

# ---- 5. prove the stack talks to itself -------------------------------------
blue "5/5  kiểm đầu-cuối qua API"
TOKEN="$(lay_token letan@dr4women.local)"
[ -n "$TOKEN" ] || { red "  mất đăng nhập lễ tân giữa chừng — dừng"; exit 1; }
goi_api() {
    curl -s -o "$LOG_DIR/api-check.json" -w '%{http_code}' "http://127.0.0.1:${API_PORT}$1" \
        -H "Authorization: Bearer $TOKEN" -H "X-API-Key: staging-local-api-key" || true
}
ma="$(goi_api '/api/v1/work-items?workspace=bang_dieu_phoi')"
n="$(python3 -c 'import sys, json
d = json.load(open(sys.argv[1]))
print(len(d) if isinstance(d, list) else "")' "$LOG_DIR/api-check.json" 2>/dev/null || true)"
if [ "$ma" != "200" ] || [ -z "$n" ]; then
    red "  /work-items trả HTTP $ma — xem $LOG_DIR/api-check.json và $LOG_DIR/api.log"; exit 1
fi
green "  hàng đợi tiếp nhận: $n việc"
ma="$(goi_api '/api/v1/luot-kham/bang')"
if [ "$ma" != "200" ]; then
    red "  /luot-kham/bang trả HTTP $ma — xem $LOG_DIR/api-check.json và $LOG_DIR/api.log"; exit 1
fi
green "  màn lượt khám trả lời (HTTP 200)"

cat <<EOF

$(green "Ready.")

  Dashboard   http://127.0.0.1:${WEB_PORT}
  API         http://127.0.0.1:${API_PORT}/docs
  Supabase    http://127.0.0.1:${SUPABASE_API_PORT}  (bộ tự dựng giống máy chủ · database 127.0.0.1:${SUPABASE_DB_PORT})
  Logs        ${LOG_DIR}/

  Phiên bản đang chạy ($LOG_DIR/phien-ban.txt):
$(sed '1d' "$LOG_DIR/phien-ban.txt")

  Đăng nhập tại /login — email bên dưới, mật khẩu: ${TEST_PW}

    letan@dr4women.local     Lễ tân      → Hàng đợi tiếp nhận
    bs.a@dr4women.local      Bác sĩ      → Bàn khám, Chỉ định dịch vụ
    cskh@dr4women.local      CSKH        → Cần làm hôm nay, Đặt lịch
    dd.sa@dr4women.local     Điều dưỡng  → Sinh hiệu
    bs.sa@dr4women.local     BS siêu âm  → Siêu âm, số đo thai
    thungan@dr4women.local   Thu ngân    → Bàn thu ngân
    ql@dr4women.local        Quản lý     → Sức khoẻ API, Vận hành, Command Center
    thuky@dr4women.local     Thư ký y khoa → Bệnh án, nháp chỉ định của BÁC SĨ MÌNH
                             (chưa phân = không thấy gì: ql phân ở Cấu hình → Thư ký)
    truongca@dr4women.local  Trưởng ca   → Điều phối, cảnh báo, chuyển bác sĩ
    doitac@dr4women.local    Đối tác     → Tải kết quả xét nghiệm (bản thử local)
    danang@dr4women.local    Đa vai hôm nay → Tiếp đón + Thu ngân + Đo sinh hiệu (lịch trực thử)

  ${so_lk} khách LK-DEMO hẹn từ 18:00 hôm nay với BS A, chờ lễ tân check-in.
  (Màn /luot-kham chỉ quản lý mở — đã ẩn khỏi menu, 15/09/2026.)

  Supabase (trình duyệt gọi): ${PUBLIC_SUPABASE_URL}
  Dừng:  scripts/dev-up.sh --down
EOF
