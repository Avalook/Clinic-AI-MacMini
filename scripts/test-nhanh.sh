#!/usr/bin/env bash
# CHẠY TEST DB TẠI CHỖ MÀ KHÔNG LÀM BẨN DB CHUNG — mỗi lượt một database TẠM
# nhân bản từ KHUÔN sạch, chạy xong xoá.
#
# Vì sao: test DB để lại dữ liệu. Chạy thẳng vào DB `postgres` của
# `chung_test_db` thì nó phình: 06/10 dựng lại (3.009 `clinic_room` rác, test quầy
# thu ~5 phút/bài); 07/10 lại 2.283 phòng rác, 235 MB, một tệp từ 4 giây lên >15
# phút → dựng lại lần hai. CI không bị vì `ci-may.sh` nhân bản DB sạch mỗi lượt.
# Script này làm y như vậy ở máy dev:
#
#   khuon  = bootstrap + migration của origin/main (CÓ ghi sổ) + seed.
#            Đóng cửa (ALLOW_CONNECTIONS false) — không test nào nối thẳng vào được.
#   tam_<pid>_<cây> = CREATE DATABASE … TEMPLATE khuon (vài giây) → áp migration
#            của CÂY NÀY mà khuôn chưa có → pytest → DROP.
#
# Migration của nhánh KHÔNG vào khuôn: nó còn sửa được, ghim vào khuôn chung là
# lặp bẫy 06/10 (bản cũ trên khuôn, bản mới trên đĩa) và làm lệch phiên khác.
# Mỗi lượt áp bản TRÊN ĐĨA vào DB tạm — sửa migration là lượt sau thấy ngay.
#
# Dùng:
#   scripts/test-nhanh.sh src/tests/services/test_x_db.py        # một tệp: tuần tự
#   scripts/test-nhanh.sh tệp_a.py tệp_b.py                      # nhiều tệp/thư mục: -n 4
#   scripts/test-nhanh.sh                                        # cả bộ như CI: -n 6
#   scripts/test-nhanh.sh tệp.py -k ten_bai -x                   # tham số khác chuyển cho pytest
#   scripts/test-nhanh.sh -n 1 tệp_a.py tệp_b.py                 # ép số worker
#   scripts/test-nhanh.sh --giu tệp.py                           # giữ DB tạm để soi (in URL)
#   scripts/test-nhanh.sh --cap-nhat-khuon                       # main có migration mới → áp vào khuôn
#   scripts/test-nhanh.sh --dung-lai-khuon                       # dựng lại khuôn từ đầu (seed đổi, khuôn lệch)
#   scripts/test-nhanh.sh --don                                  # xoá DB tạm mồ côi rồi thoát
#
# Song song nhiều phiên an toàn: tên DB tạm theo pid + tên cây; dựng/cập nhật
# khuôn có khoá ở thư mục git CHUNG của mọi worktree và tráo khuôn bằng
# đổi tên (khuôn dựng xong mới thay, đang dựng dở không ai nhân bản nhầm).
#
# Biến môi trường: TEST_NHANH_CONTAINER (mặc định chung_test_db),
# TEST_NHANH_PYTHON (python có pytest; mặc định .venv của cây / cây khác).
# KHÔNG BAO GIỜ đụng :55433. KHÔNG xoá/reset DB `postgres` của container.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 2

CONTAINER="${TEST_NHANH_CONTAINER:-chung_test_db}"
KHUON=khuon

N=""
GIU=0
VIEC=chay
PYTEST_ARGS=()
CO_DICH=0
SO_DICH=0
CO_THU_MUC=0
while [ $# -gt 0 ]; do
  case "$1" in
    -n) N="${2:?-n cần số worker}"; shift 2; continue ;;
    -n[0-9]*) N="${1#-n}" ;;
    --giu) GIU=1 ;;
    --cap-nhat-khuon) VIEC=cap-nhat ;;
    --dung-lai-khuon) VIEC=dung-lai ;;
    --don) VIEC=don ;;
    -h|--help) sed -n '2,38p' "$0"; exit 0 ;;
    *)
      PYTEST_ARGS+=("$1")
      duong="${1%%::*}"
      if [ -d "$duong" ]; then CO_DICH=1; CO_THU_MUC=1; SO_DICH=$((SO_DICH + 1))
      elif [ -f "$duong" ]; then CO_DICH=1; SO_DICH=$((SO_DICH + 1)); fi
      ;;
  esac
  shift
done

# ── psql trong container ────────────────────────────────────────────────────
command -v docker >/dev/null || { echo "Thiếu docker" >&2; exit 2; }
if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" != true ]; then
  cat >&2 <<HD
Container $CONTAINER không chạy. Nó là DB test CHUNG — không tự dựng ở đây.
Bật lại: docker start $CONTAINER
Chưa có hẳn (xem memory dung-lai-db-test-chung):
  docker run -d --name $CONTAINER -p 127.0.0.1:55600:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres postgres:17
HD
  exit 2
fi
CONG="$(docker port "$CONTAINER" 5432/tcp 2>/dev/null | head -1 | sed 's/.*://')"
[ -n "$CONG" ] || { echo "Container $CONTAINER không mở cổng 5432 ra máy." >&2; exit 2; }
[ "$CONG" != 55433 ] || { echo "Từ chối: :55433 không phải chỗ của script này." >&2; exit 2; }

# sql <db> <câu lệnh…> — mỗi -c chạy riêng (CREATE/DROP DATABASE không được nằm trong giao dịch).
sql() {
  local db="$1"; shift
  local lenh=()
  for c in "$@"; do lenh+=(-c "$c"); done
  # Không `-i`: hàm này không đọc stdin, mà `-i` thì nuốt stdin của vòng `while read` gọi nó.
  docker exec -e PGOPTIONS=--client-min-messages=warning "$CONTAINER" \
    psql -U postgres -d "$db" -v ON_ERROR_STOP=1 -qtA "${lenh[@]}" </dev/null
}
co_db() { [ "$(sql template1 "SELECT 1 FROM pg_database WHERE datname = '$1'")" = 1 ]; }
xoa_db() { sql template1 "DROP DATABASE IF EXISTS \"$1\" WITH (FORCE)" >/dev/null; }

# Nhân bản: thử lại vài lần — đúng lúc phiên khác tráo khuôn thì `khuon` vắng
# mặt một nháy, hoặc nguồn đang có người nối vào.
nhan_ban() {
  local nguon="$1" dich="$2" loi
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if loi="$(sql template1 "CREATE DATABASE \"$dich\" TEMPLATE \"$nguon\"" 2>&1)"; then return 0; fi
    sleep 1
  done
  echo "Không nhân bản được $nguon → $dich: $loi" >&2
  return 1
}

# ── Khoá dựng/cập nhật khuôn (chung mọi worktree) ───────────────────────────
KHOA="$(git rev-parse --path-format=absolute --git-common-dir)/test-nhanh-khuon.khoa"
lay_khoa() {
  local cho=0
  while ! mkdir "$KHOA" 2>/dev/null; do
    local giu
    giu="$(cat "$KHOA/pid" 2>/dev/null || true)"
    if [ -n "$giu" ] && ! kill -0 "$giu" 2>/dev/null; then
      echo "Khoá khuôn bỏ lại từ phiên đã chết (pid $giu) — lấy lại."
      rm -rf "$KHOA"; continue
    fi
    [ $cho = 0 ] && echo "Phiên khác đang dựng/cập nhật khuôn (pid ${giu:-?}, $(cat "$KHOA/noi" 2>/dev/null)) — chờ…"
    cho=$((cho + 1))
    [ $cho -gt 600 ] && { echo "Chờ khoá khuôn quá 10 phút — dừng." >&2; exit 2; }
    sleep 1
  done
  echo $$ >"$KHOA/pid"; echo "$REPO" >"$KHOA/noi"
}
tra_khoa() { rm -rf "$KHOA"; }

# Mã nguồn origin/main (migration + bootstrap + seed + script áp) ra thư mục tạm,
# để khuôn luôn là MAIN dù đang đứng ở nhánh nào.
lay_main() {
  git fetch -q origin main 2>/dev/null || echo "⚠️  Không fetch được origin — dùng origin/main đang có."
  MAIN_SHA="$(git rev-parse --short origin/main)"
  MAIN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test-nhanh-main.XXXXXX")"
  git archive origin/main supabase/migrations supabase/tests/bootstrap_plain_postgres.sql \
    supabase/seed.sql scripts/apply-pending-migrations.sh | tar -x -C "$MAIN_DIR"
}

ap_migration() {  # ap_migration <db> <thư mục gốc chứa scripts/ + supabase/>
  PGDATABASE="$1" CLINIC_DB_CONTAINER="$CONTAINER" "$2/scripts/apply-pending-migrations.sh" --apply
}

# Tráo `khuon_moi` vào chỗ `khuon`, đóng cửa, ghi chú nguồn gốc. Gọi khi đang giữ khoá.
trao_khuon() {
  local moi="$1" ghi_chu="$2"
  if co_db "$KHUON"; then
    sql template1 "ALTER DATABASE \"$KHUON\" WITH IS_TEMPLATE false" >/dev/null
    xoa_db "$KHUON"
  fi
  sql template1 "ALTER DATABASE \"$moi\" RENAME TO \"$KHUON\"" \
    "ALTER DATABASE \"$KHUON\" WITH ALLOW_CONNECTIONS false IS_TEMPLATE true" \
    "COMMENT ON DATABASE \"$KHUON\" IS '$ghi_chu'" >/dev/null
}

seed_md5() { md5 -q "$1" 2>/dev/null || md5sum "$1" | cut -d' ' -f1; }

dung_khuon() {
  lay_khoa
  if [ "$VIEC" != dung-lai ] && co_db "$KHUON"; then tra_khoa; return 0; fi  # phiên khác vừa dựng xong
  local moi="khuon_moi_$$" bat_dau=$SECONDS
  echo "Dựng khuôn từ origin/main (một lần, ~1–3 phút)…"
  lay_main
  xoa_db "$moi"
  if sql template1 "CREATE DATABASE \"$moi\" TEMPLATE template0" >/dev/null \
    && docker exec -i "$CONTAINER" psql -U postgres -d "$moi" -v ON_ERROR_STOP=1 -q \
         <"$MAIN_DIR/supabase/tests/bootstrap_plain_postgres.sql" >/dev/null \
    && ap_migration "$moi" "$MAIN_DIR" >/dev/null \
    && docker exec -i "$CONTAINER" psql -U postgres -d "$moi" -v ON_ERROR_STOP=1 -q \
         <"$MAIN_DIR/supabase/seed.sql" >/dev/null; then
    trao_khuon "$moi" "main@$MAIN_SHA seed=$(seed_md5 "$MAIN_DIR/supabase/seed.sql") dung=$(date '+%d/%m %H:%M')"
    echo "Khuôn xong: main@$MAIN_SHA, $((SECONDS - bat_dau))s."
  else
    echo "Dựng khuôn HỎNG — khuôn cũ (nếu có) giữ nguyên." >&2
    xoa_db "$moi"; rm -rf "$MAIN_DIR"; tra_khoa; exit 1
  fi
  rm -rf "$MAIN_DIR"; tra_khoa
}

cap_nhat_khuon() {
  co_db "$KHUON" || { dung_khuon; return; }
  lay_khoa
  local moi="khuon_moi_$$"
  lay_main
  xoa_db "$moi"
  nhan_ban "$KHUON" "$moi" || { rm -rf "$MAIN_DIR"; tra_khoa; exit 1; }
  local truoc sau
  truoc="$(sql "$moi" "SELECT count(*) FROM supabase_migrations.schema_migrations")"
  if ! ap_migration "$moi" "$MAIN_DIR"; then
    echo "Áp migration main vào khuôn HỎNG — khuôn giữ nguyên." >&2
    xoa_db "$moi"; rm -rf "$MAIN_DIR"; tra_khoa; exit 1
  fi
  sau="$(sql "$moi" "SELECT count(*) FROM supabase_migrations.schema_migrations")"
  if [ "$truoc" = "$sau" ]; then
    xoa_db "$moi"; echo "Khuôn đã đủ migration của main@$MAIN_SHA."
  else
    local cu
    cu="$(sql template1 "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = '$KHUON'")"
    trao_khuon "$moi" "main@$MAIN_SHA seed=$(sed -n 's/.*seed=\([^ ]*\).*/\1/p' <<<"$cu") cap-nhat=$(date '+%d/%m %H:%M')"
    echo "Khuôn cập nhật: +$((sau - truoc)) migration (main@$MAIN_SHA)."
  fi
  rm -rf "$MAIN_DIR"; tra_khoa
}

# ── DB tạm mồ côi (phiên chết giữa chừng) ───────────────────────────────────
don_mo_coi() {
  local db pid
  while read -r db; do
    [ -n "$db" ] || continue
    pid="$(sed -nE 's/^(tam|khuon_moi)_([0-9]+).*/\2/p' <<<"$db")"
    [ -n "$pid" ] || continue
    [ "$pid" = $$ ] && continue
    if ! kill -0 "$pid" 2>/dev/null; then
      xoa_db "$db" && echo "Xoá DB mồ côi $db"
    fi
  done < <(sql template1 "SELECT datname FROM pg_database WHERE datname ~ '^(tam|khuon_moi)_[0-9]+'")
}

don_mo_coi
case "$VIEC" in
  don) exit 0 ;;
  dung-lai) dung_khuon; exit 0 ;;
  cap-nhat) cap_nhat_khuon; exit 0 ;;
esac
co_db "$KHUON" || dung_khuon

# ── Python có pytest ────────────────────────────────────────────────────────
PY="${TEST_NHANH_PYTHON:-}"
if [ -z "$PY" ]; then
  GOC="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
  for p in "$REPO/.venv/bin/python" "$GOC/.venv/bin/python" "$GOC"/.claude/worktrees/*/.venv/bin/python; do
    if [ -x "$p" ] && "$p" -c "import pytest" 2>/dev/null; then PY="$p"; break; fi
  done
fi
[ -n "$PY" ] || { echo "Không tìm thấy python có pytest — poetry install --no-root --with dev, hoặc đặt TEST_NHANH_PYTHON." >&2; exit 2; }

if [ $CO_DICH = 0 ]; then
  # Không chỉ tệp nào → cả bộ, đúng bộ lọc của CI.
  PYTEST_ARGS=(src/tests/ -m "not integration" --ignore=src/tests/integration ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"})
  N="${N:-6}"
elif [ "$SO_DICH" -gt 1 ] || [ $CO_THU_MUC = 1 ]; then
  N="${N:-4}"
else
  N="${N:-1}"
fi
if [ "$N" -gt 1 ] && ! "$PY" -c "import xdist" 2>/dev/null; then
  "$(dirname "$PY")/pip" install -q "pytest-xdist==3.6.1" || { echo "⚠️  Không cài được pytest-xdist — chạy tuần tự."; N=1; }
fi

# ── DB tạm ──────────────────────────────────────────────────────────────────
CAY="$(basename "$REPO" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9\n' '_' | cut -c1-30)"
TAM="tam_$$_${CAY}"
DB_TAM=("$TAM")
don_dep() {
  local ma=$?
  if [ $GIU = 1 ]; then
    echo "Giữ DB tạm (--giu): ${DB_TAM[*]} — xoá: scripts/test-nhanh.sh --don (sau khi phiên này thoát) hoặc DROP tay."
  else
    for db in "${DB_TAM[@]}"; do xoa_db "$db" 2>/dev/null; done
  fi
  exit $ma
}
trap don_dep EXIT
trap 'exit 130' INT TERM

bat_dau=$SECONDS
nhan_ban "$KHUON" "$TAM" || exit 1

# Khuôn so với cây đang đứng: thiếu (migration nhánh / main mới) → áp vào DB tạm;
# thừa (cây cũ hơn khuôn) → cảnh báo.
DA_AP="$(sql "$TAM" "SELECT version FROM supabase_migrations.schema_migrations")"
CAY_CO="$(ls supabase/migrations/*.sql 2>/dev/null | xargs -n1 basename | sed 's/_.*//')"
THIEU="$(comm -23 <(sort -u <<<"$CAY_CO") <(sort -u <<<"$DA_AP") | grep . || true)"
THUA="$(comm -13 <(sort -u <<<"$CAY_CO") <(sort -u <<<"$DA_AP") | grep . || true)"
if [ -n "$THIEU" ]; then
  so_thieu="$(grep -c . <<<"$THIEU")"
  tren_main="$(git ls-tree --name-only origin/main supabase/migrations/ 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/_.*//' | grep -cxF -f <(echo "$THIEU") || true)"
  echo "Khuôn thiếu $so_thieu migration của cây này → áp vào DB tạm (khuôn không đổi):"
  sed 's/^/  • /' <<<"$THIEU"
  if [ "${tren_main:-0}" -gt 0 ]; then
    echo "  ⚠️  $tren_main cái đã có trên origin/main — chạy scripts/test-nhanh.sh --cap-nhat-khuon cho các lượt sau khỏi áp lại."
  fi
  if ! ap_migration "$TAM" "$REPO" >/dev/null; then
    echo "Áp migration của cây vào DB tạm HỎNG — xem lỗi phía trên (migration nhánh sai?)." >&2
    exit 1
  fi
fi
if [ -n "$THUA" ]; then
  echo "⚠️  Khuôn có $(grep -c . <<<"$THUA") migration cây này KHÔNG có ($(head -3 <<<"$THUA" | tr '\n' ' ')…) — cây cũ hơn main? Rebase, hoặc chấp nhận lệch."
fi
GHI_CHU="$(sql template1 "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = '$KHUON'")"
SEED_KHUON="$(sed -n 's/.*seed=\([^ ]*\).*/\1/p' <<<"$GHI_CHU")"
if [ -n "$SEED_KHUON" ] && [ "$SEED_KHUON" != "$(seed_md5 supabase/seed.sql)" ]; then
  echo "⚠️  supabase/seed.sql của cây khác seed trong khuôn — bài phụ thuộc seed mới thì: scripts/test-nhanh.sh --dung-lai-khuon"
fi

URL_GOC="postgresql://postgres:postgres@127.0.0.1:${CONG}"
MOI_WORKER=()
if [ "$N" -gt 1 ]; then
  # Mỗi worker một DB (như ci-may): `${TAM}_gwK`, nhân bản từ DB tạm đã đủ migration.
  for k in $(seq 0 $((N - 1))); do
    DB_TAM+=("${TAM}_gw$k")
    nhan_ban "$TAM" "${TAM}_gw$k" || exit 1
  done
  MOI_WORKER=(env "TEST_DB_TIEN_TO_WORKER=${TAM}_")
  PYTEST_ARGS=(-n "$N" --dist loadfile ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"})
fi
echo "DB tạm $TAM ($N worker) sẵn sàng sau $((SECONDS - bat_dau))s — khuôn: ${GHI_CHU:-?}"
[ $GIU = 1 ] && echo "DATABASE_URL_TEST=$URL_GOC/$TAM"

ANTHROPIC_API_KEY="" DATABASE_URL_TEST="$URL_GOC/$TAM" \
  ${MOI_WORKER[@]+"${MOI_WORKER[@]}"} "$PY" -m pytest ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"}
