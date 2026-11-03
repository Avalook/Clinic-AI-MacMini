#!/usr/bin/env bash
# SAO LƯU NỐI TIẾP bằng pgBackRest (docs/KE-HOACH-SAO-LUU-NOI-TIEP.md).
#
#   ./scripts/sao-luu-noi-tiep.sh bat         # một lần: tạo stanza + kiểm chép WAL
#   ./scripts/sao-luu-noi-tiep.sh full        # bản đầy đủ (timer: Chủ nhật)
#   ./scripts/sao-luu-noi-tiep.sh diff        # bản chênh lệch (timer: các đêm khác)
#   ./scripts/sao-luu-noi-tiep.sh info        # các bản đang có + khoảng WAL
#   ./scripts/sao-luu-noi-tiep.sh kiem        # pgbackrest check + verify
#   ./scripts/sao-luu-noi-tiep.sh dien-tap ["YYYY-MM-DD HH:MM:SS"]
#        # khôi phục vào container TẠM (không đụng DB thật), mặc định tới
#        # thời điểm mới nhất; in số dòng vài bảng chính để so với DB thật.
#
# pgBackRest chạy TRONG container DB (CLINIC_DB_CONTAINER, mặc định clinicai_db)
# bằng user postgres. Lệnh nặng chạy nice/ionice phía máy chủ — máy chung với
# phòng khám đang đón khách.
set -euo pipefail

DB="${CLINIC_DB_CONTAINER:-clinicai_db}"
STANZA=clinicai
REPO_DIR="${SUPABASE_DB_PGBACKREST_DIR:-/home/clinicai/pgbackrest}"
NICE=(nice -n 19)
command -v ionice >/dev/null 2>&1 && NICE+=(ionice -c3)

dung() { echo "!! $*" >&2; exit 1; }
pgbr() { "${NICE[@]}" docker exec -u postgres "$DB" pgbackrest --stanza="$STANZA" "$@"; }

docker exec "$DB" sh -c 'command -v pgbackrest' >/dev/null 2>&1 \
    || dung "$DB chưa chạy ảnh có pgBackRest (SUPABASE_DB_IMAGE=clinicai-db:17-pgbackrest)."

case "${1:-}" in
  bat)
    [ "$(docker exec -u postgres "$DB" psql -tAc 'SHOW archive_mode')" = on ] \
        || dung "archive_mode chưa bật — đặt SUPABASE_DB_ARCHIVE_MODE=on rồi dựng lại DB."
    # pgBackRest tự tạo repo/spool nhưng KHÔNG tạo log-path (thử 03/11: chỉ
    # cảnh báo rồi chạy không ghi log — lỗi sau này không còn dấu vết).
    docker exec -u postgres "$DB" mkdir -p /var/lib/pgbackrest/log
    pgbr stanza-create
    pgbr check   # ép đổi một đoạn WAL và chờ nó vào kho — chứng minh archive_command chạy
    ;;
  full|diff)
    pgbr --type="$1" backup
    pgbr info
    ;;
  info)
    pgbr info
    ;;
  kiem)
    pgbr check
    pgbr verify
    ;;
  dien-tap)
    # Khôi phục vào container TẠM dùng cùng ảnh, kho gắn CHỈ ĐỌC. archive_mode
    # tắt trong bản tạm: bản khôi phục mà chép WAL ngược vào kho thật là làm
    # hỏng dòng thời gian của chính kho đó.
    DICH="${2:-}"
    ANH="$(docker inspect -f '{{.Config.Image}}' "$DB")"
    TAM="clinicai_dien_tap_$(date +%s)"
    # Thư mục dữ liệu tạm = volume Docker (thuộc postgres được mà không cần
    # sudo; restore từ chối thư mục không thuộc user chạy nó). Chỉ xoá đúng
    # container/volume tạo ở đây.
    TAM_DATA="${TAM}_data"
    trap 'docker rm -f "$TAM" >/dev/null 2>&1 || true; docker volume rm "$TAM_DATA" >/dev/null 2>&1 || true' EXIT
    docker volume create "$TAM_DATA" >/dev/null
    docker run --rm -v "$TAM_DATA:/d" "$ANH" sh -c 'chown postgres:postgres /d && chmod 700 /d'
    # pgBackRest trong container chạy giờ UTC: "12:32:40" không ghi múi giờ
    # bị hiểu là 12:32 UTC = lệch 7 tiếng (thử 03/11). Giờ người dùng gõ là
    # giờ Việt Nam → tự gắn +07 khi chưa có múi giờ.
    case "$DICH" in ""|*[+-][0-9][0-9]|*[+-][0-9][0-9]:[0-9][0-9]|*[+-][0-9][0-9][0-9][0-9]) ;;
                    *) DICH="$DICH+07" ;; esac
    LOAI=(); [ -n "$DICH" ] && LOAI=(--type=time "--target=$DICH" --target-action=promote)
    # Kho gắn CHỈ ĐỌC nên mọi chỗ pgBackRest định ghi (log, hàng chờ archive-get
    # bất đồng bộ trong spool) phải chuyển ra /tmp — kể cả restore_command mà
    # restore ghi vào bản tạm, Postgres gọi nó suốt lúc phát lại WAL.
    # restore dọn spool → spool ra /tmp; archive-get đồng bộ (không spool, và
    # pgBackRest từ chối --spool-path khi --archive-async=n).
    RIENG="--log-path=/tmp --spool-path=/tmp/pgbackrest-spool"
    LAY="pgbackrest --stanza=$STANZA --archive-async=n --log-path=/tmp archive-get %f \"%p\""
    # shellcheck disable=SC2086  # RIENG là hai cờ, cố ý tách từ
    "${NICE[@]}" docker run --rm -u postgres \
        -v "$REPO_DIR:/var/lib/pgbackrest:ro" -v "$TAM_DATA:/var/lib/postgresql/data" \
        "$ANH" pgbackrest --stanza="$STANZA" $RIENG \
        "--recovery-option=restore_command=$LAY" ${LOAI[@]+"${LOAI[@]}"} restore
    # wal_level/slot giống DB thật: bản sao lưu từ máy wal_level=logical có slot
    # logical thì Postgres từ chối mở với wal_level thấp hơn.
    docker run -d --name "$TAM" -u postgres \
        -v "$REPO_DIR:/var/lib/pgbackrest:ro" -v "$TAM_DATA:/var/lib/postgresql/data" \
        "$ANH" postgres -c archive_mode=off -c shared_buffers=64MB \
        -c wal_level=logical -c max_replication_slots=8 -c max_wal_senders=8 \
        -c shared_preload_libraries=pg_stat_statements >/dev/null
    for _ in $(seq 1 120); do
        docker exec -u postgres "$TAM" psql -tAc 'SELECT NOT pg_is_in_recovery()' 2>/dev/null \
            | grep -qx t && break
        sleep 2
    done
    docker exec -u postgres "$TAM" psql -tAc 'SELECT NOT pg_is_in_recovery()' | grep -qx t \
        || dung "bản tạm không xong khôi phục sau 240 giây — xem: docker logs $TAM"
    DEM="SELECT 'visit', count(*)::text FROM public.visit UNION ALL
         SELECT 'payment', count(*)::text FROM public.payment UNION ALL
         SELECT 'tep_ket_qua', count(*)::text FROM public.tep_ket_qua UNION ALL
         SELECT 'auth.users', count(*)::text FROM auth.users UNION ALL
         SELECT 'moi_nhat', max(recorded_at)::text FROM public.event_log"
    echo "== bản khôi phục"; docker exec -u postgres "$TAM" psql -tA -F' ' -c "$DEM"
    echo "== DB thật lúc này"; docker exec -u postgres "$DB" psql -tA -F' ' -c "$DEM"
    ;;
  *)
    sed -n '2,13p' "$0"; exit 2 ;;
esac
