#!/usr/bin/env bash
# CI CHẠY TRÊN MÁY — y hệt .github/workflows/ci.yml, không cần GitHub Actions.
#
# Tuyền 25/09/2026: "mình tự CI trên máy được không, không phụ thuộc github nữa".
# Hôm ấy GitHub từ chối chạy job ("recent account payments have failed"), còn
# repo private gói miễn phí không có luật bắt buộc CI trên `main` — nên cổng
# thật là: chạy lệnh này xanh rồi mới merge / deploy.
#
#   ./scripts/ci-may.sh                # 5 job, ảnh Docker bỏ qua (xem --anh)
#   ./scripts/ci-may.sh --anh          # + dựng ảnh linux/amd64 như CI (chậm trên Mac ARM)
#   ./scripts/ci-may.sh --bao-github   # gửi kết quả lên PR: commit status "ci-may/<job>"
#   ./scripts/ci-may.sh --sach         # npm ci lại từ đầu (như CI) thay vì dùng node_modules có sẵn
#
# Log từng job: .ci-may/<job>.log. Thoát 0 chỉ khi MỌI job xanh.
#
# KHÁC CI Ở ĐÂU (cố ý, nói thẳng):
#   * Chạy trên CÂY LÀM VIỆC, không phải bản commit sạch → có file chưa commit thì
#     cảnh báo, và KHÔNG gửi status lên GitHub (status gắn với commit).
#   * portability: không khởi động thử ảnh (Docker Desktop trên Mac không có
#     `--network host` như Linux). Deploy lên VPS dựng + khởi động ảnh amd64 thật
#     và có health check — đó là bước chứng minh ảnh chạy được.
#   * DB thử dùng container riêng (ci_may_test :55530, ci_may_db :55531), không
#     đụng DB test hằng ngày (:55500) và KHÔNG BAO GIỜ đụng :55433.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 2
LOG="$REPO/.ci-may"
mkdir -p "$LOG"

ANH=0
BAO=0
SACH=0
for a in "$@"; do
  case "$a" in
    --anh) ANH=1 ;;
    --bao-github) BAO=1 ;;
    --sach) SACH=1 ;;
    *) echo "Không hiểu tham số: $a" >&2; exit 2 ;;
  esac
done

# Giá trị GIẢ của DB thử / bản build thử — viết dạng `${…:-…}` để chốt bí mật
# trước commit (scripts/git-hooks/pre-commit) hiểu là tham chiếu, không phải bí mật.
MK_DB_THU="${CI_MAY_MK_DB:-postgres}"
KHOA_ANON_GIA="${CI_MAY_KHOA_ANON:-dummy-anon-key-for-build}"

VENV="$REPO/.venv/bin"
[ -x "$VENV/pytest" ] || { echo "Thiếu .venv — chạy: poetry install --no-root --with dev" >&2; exit 2; }
command -v docker >/dev/null || { echo "Thiếu docker" >&2; exit 2; }
command -v psql >/dev/null || { echo "Thiếu psql (brew install libpq)" >&2; exit 2; }

BAN="$(git rev-parse HEAD)"
BAN_NGAN="$(git rev-parse --short HEAD)"
BAN_BAN=0
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  BAN_BAN=1
  echo "⚠️  Có thay đổi CHƯA commit — kết quả là của cây làm việc, không phải $BAN_NGAN."
fi

# ── Các job ─────────────────────────────────────────────────────────────────

job_backend() {
  set -e
  "$VENV/ruff" check src/
  "$VENV/ruff" format --check src/
  "$VENV/mypy" src/
  python3 scripts/tests/tenant-scope-audit.py --check
  DB_CONTAINER=ci_may_test DB_PORT=55530 ./scripts/tests/dung-db-kiem.sh
  ANTHROPIC_API_KEY="" \
    DATABASE_URL_TEST="postgresql://postgres:${MK_DB_THU}@127.0.0.1:55530/postgres" \
    "$VENV/pytest" src/tests/ -q --tb=short -p no:cacheprovider \
    -m "not integration" --ignore=src/tests/integration \
    --cov=clinicai --cov-report=term --cov-fail-under=80
}

job_frontend() {
  set -e
  cd src/dashboard
  export NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co
  export NEXT_PUBLIC_SUPABASE_ANON_KEY="${KHOA_ANON_GIA}"
  export SKIP_ENV_VALIDATION=1 NEXT_TELEMETRY_DISABLED=1 PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
  if [ "$SACH" = 1 ] || [ ! -d node_modules ]; then npm ci; fi
  ./node_modules/.bin/tsc --noEmit
  npm run lint -- --max-warnings=0
  for t in audit ops boundary roster luu-nhap khung gio-ca bo-nho nhip hanh-trinh sua-mau phieu-kham thanh-ngay o-so; do
    npm run "test:$t"
  done
  # Dựng vào `.next` của CÂY NÀY (như CI). Đang chạy `next dev` ở chính cây
  # này thì tắt nó trước — hai tiến trình cùng ghi `.next`.
  npm run build
}

job_infra() {
  set -e
  ./scripts/tests/test-infra-safety.sh
}

job_portability() {
  set -e
  if grep -rnE '(/Users/|/home/[a-z]+/)' \
       docker-compose.yml Dockerfile.api src/dashboard/Dockerfile.dashboard \
       .env.example .env.prod.example .env.staging.example \
     | grep -v '^\S*: *#'; then
    echo "LỖI: đường dẫn riêng của một máy trong cấu hình đã commit (ADR-0013)"
    return 1
  fi
  for example in .env.prod.example .env.staging.example; do
    echo "-- $example"
    CLINIC_ENV_FILE="$example" docker compose --env-file "$example" config >/dev/null
  done
  if [ "$ANH" = 1 ]; then
    docker buildx build --platform linux/amd64 -f Dockerfile.api -t clinicai-api:ci --load .
    docker buildx build --platform linux/amd64 -f src/dashboard/Dockerfile.dashboard \
      --build-arg NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co \
      --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY="${KHOA_ANON_GIA}" \
      -t clinicai-dashboard:ci --load src/dashboard
    for image in clinicai-api:ci clinicai-dashboard:ci; do
      arch=$(docker image inspect "$image" --format '{{.Architecture}}')
      echo "$image -> $arch"
      [ "$arch" = "amd64" ]
    done
  else
    echo "(bỏ qua dựng ảnh amd64 — thêm --anh để dựng; deploy VPS dựng thật)"
  fi
}

job_database() {
  set -e
  if grep -nE '^\\(un)?restrict|FROM stdin' supabase/migrations/*.sql supabase/seed.sql; then
    echo "LỖI: cú pháp chỉ psql hiểu — Supabase CLI không chạy được"
    return 1
  fi
  docker rm -f ci_may_db >/dev/null 2>&1 || true
  docker run -d --name ci_may_db -e POSTGRES_PASSWORD="${MK_DB_THU}" -p 127.0.0.1:55531:5432 \
    postgres:17 >/dev/null
  trap 'docker rm -f ci_may_db >/dev/null 2>&1 || true' EXIT
  for _ in $(seq 1 60); do
    docker exec ci_may_db pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 1
  done
  sleep 2
  export PGPASSWORD="${MK_DB_THU}"
  P="psql -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55531 -U postgres -d postgres"
  $P -f supabase/tests/bootstrap_plain_postgres.sql
  for m in supabase/migrations/*.sql; do echo "-- $m"; $P -f "$m"; done
  echo "== chạy lại migration từ 20260730"
  for m in supabase/migrations/*.sql; do
    v="$(basename "$m" | cut -d_ -f1)"
    [ "$v" \< "20260730000000" ] && continue
    $P -f "$m"
  done
  echo "== kiểm lược đồ"
  for t in supabase/tests/*.sql; do
    [ "$(basename "$t")" = bootstrap_plain_postgres.sql ] && continue
    echo "-- $t"
    $P -f "$t"
  done
}

# ── Chạy song song, gom kết quả ─────────────────────────────────────────────

JOBS="backend frontend infra portability database"
BAT_DAU=$(date +%s)
PIDS=""
for j in $JOBS; do
  rm -f "$LOG/$j.rc" "$LOG/$j.giay"
  (
    s=$(date +%s)
    # Vỏ con riêng: `set -e` trong job chỉ thoát job, vẫn ghi được mã kết quả.
    ( "job_$j" ) >"$LOG/$j.log" 2>&1
    echo $? >"$LOG/$j.rc"
    echo "$(( $(date +%s) - s ))" >"$LOG/$j.giay"
  ) &
  PIDS="$PIDS $!"
done
# shellcheck disable=SC2086
wait $PIDS

kq() { [ "$(cat "$LOG/$1.rc" 2>/dev/null)" = 0 ] && echo success || echo failure; }
giay() { cat "$LOG/$1.giay" 2>/dev/null || echo "?"; }

echo
echo "CI trên máy · $BAN_NGAN$([ "$BAN_BAN" = 1 ] && echo ' (+ thay đổi chưa commit)') · $(( $(date +%s) - BAT_DAU ))s"
DO=0
for j in $JOBS; do
  if [ "$(kq "$j")" = success ]; then dau="✅"; else dau="❌"; DO=1; fi
  printf '  %s %-12s %4ss   .ci-may/%s.log\n' "$dau" "$j" "$(giay "$j")" "$j"
done
for j in $JOBS; do
  if [ "$(kq "$j")" != success ]; then
    echo
    echo "── $j (20 dòng cuối) ──"
    tail -20 "$LOG/$j.log"
  fi
done

if [ "$BAO" = 1 ]; then
  if [ "$BAN_BAN" = 1 ]; then
    echo "Không gửi status: còn thay đổi chưa commit."
  elif [ -z "$(git branch -r --contains "$BAN" 2>/dev/null)" ]; then
    echo "Không gửi status: $BAN_NGAN chưa đẩy lên GitHub (git push trước)."
  else
    for j in $JOBS; do
      gh api "repos/{owner}/{repo}/statuses/$BAN" -f state="$(kq "$j")" \
        -f context="ci-may/$j" -f description="CI trên máy — $(giay "$j")s" >/dev/null \
        && echo "  đã gửi ci-may/$j = $(kq "$j")"
    done
  fi
fi
exit $DO
