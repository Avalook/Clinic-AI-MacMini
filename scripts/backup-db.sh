#!/bin/bash
# Sao lưu hằng đêm cho ClinicAI: lược đồ + dữ liệu `public`, KÈM một tệp thứ hai
# chứa `auth.users` + `auth.identities`.
#
# Hai câu đầu file này từng ghi "auth identities … require Supabase PITR/backup".
# Câu đó đúng thời database còn ở Supabase cloud. Từ 06/08/2026 hệ thống tự dựng
# GoTrue trên máy mình, nên KHÔNG CÒN AI sao lưu hộ phần auth — nếu file này
# không mang nó thì không ai mang cả, và khôi phục xong sẽ là một phòng khám đủ
# dữ liệu mà không ai đăng nhập được.
#
# Tệp auth đã được dump từ trước (xem phần "companion auth artifact"); chỉ có
# lời chú thích ở đây là cũ.
#
# 1. Reads DATABASE_URL from BACKUP_ENV_FILE or .env.prod (never guesses staging)
# 2. Runs pg_dump → gzip → ~/backups/clinicai/
# 3. Keeps last 7 daily backups, deletes older ones
# 4. Optionally pushes to Cloudflare R2 via rclone (if configured)
#
# Run manually:  ./scripts/backup-db.sh
# Or via LaunchDaemon (see scripts/launchdaemons/com.dr4women.db-backup.plist)
set -euo pipefail
umask 077

# LaunchDaemons do not load the interactive Homebrew shell profile. `pg_dump`
# from either the keg-only libpq package or PostgreSQL 17 must therefore be on
# the explicit command path. CLINIC_BACKUP_PATH is an escape hatch for a
# non-Homebrew host and deterministic tests.
DEFAULT_COMMAND_PATH="/opt/homebrew/opt/libpq/bin:/opt/homebrew/opt/postgresql@17/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH="${CLINIC_BACKUP_PATH:-${DEFAULT_COMMAND_PATH}${PATH:+:${PATH}}}"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
# Nhật ký. macOS dùng ~/Library/Logs; Linux thì thư mục ấy vô nghĩa, nên cho
# phép đặt bằng biến — systemd trên VPS trỏ vào ~/.local/state.
LOG="${CLINIC_BACKUP_LOG:-$HOME/Library/Logs/clinicai-backup.log}"
BACKUP_DIR="${CLINIC_BACKUP_DIR:-$HOME/backups/clinicai}"
KEEP_DAYS=7
MIN_ARCHIVE_BYTES="${BACKUP_MIN_ARCHIVE_BYTES:-1024}"

mkdir -p "$(dirname "$LOG")" "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

log "=== Backup starting ==="

case "$MIN_ARCHIVE_BYTES" in
    ''|*[!0-9]*) log "ERROR: BACKUP_MIN_ARCHIVE_BYTES must be a positive integer"; exit 1 ;;
esac
[ "$MIN_ARCHIVE_BYTES" -ge 1 ] || {
    log "ERROR: BACKUP_MIN_ARCHIVE_BYTES must be at least 1"
    exit 1
}

# Load DATABASE_URL from env file.
ENV_FILE="${BACKUP_ENV_FILE:-${REPO}/.env.prod}"
[ -f "$ENV_FILE" ] || { log "ERROR: env file not found: $ENV_FILE"; exit 1; }

DATABASE_URL=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)
[ -n "$DATABASE_URL" ] || { log "ERROR: DATABASE_URL not found in $ENV_FILE"; exit 1; }
SOURCE_APP_ENV=$(grep -E '^APP_ENV=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)
case "$SOURCE_APP_ENV" in
    production|staging|test|development) : ;;
    *) log "ERROR: APP_ENV must identify the backup source"; exit 1 ;;
esac

# Strip the +asyncpg driver suffix for pg_dump compatibility.
PG_URL="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"

# ---- status is written for every ATTEMPT, not only for successes ------------
# Three consecutive nights failed with "pg_dump: command not found" and nobody
# noticed, because a failing run exits before it writes anything: the status
# file kept describing the last SUCCESS and silence looked identical to health.
# Now the last line of the file is always the last thing that happened.
OPS_STATUS_ROOT=$(grep -E '^OPS_STATUS_DIR=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)
OPS_STATUS_ROOT=${OPS_STATUS_ROOT:-${HOME}/.clinicai/ops}
case "$OPS_STATUS_ROOT" in
    "~/"*) OPS_STATUS_ROOT="$HOME/${OPS_STATUS_ROOT#\~/}" ;;
    /*) : ;;
    *) OPS_STATUS_ROOT="${REPO}/${OPS_STATUS_ROOT}" ;;
esac
OPS_STATUS_ENV_DIR="${OPS_STATUS_ROOT}/${SOURCE_APP_ENV}"
mkdir -p "$OPS_STATUS_ENV_DIR"
chmod 700 "$OPS_STATUS_ENV_DIR"

BACKUP_SUCCEEDED=0
BACKUP_DECLINED=0
write_failure_status() {
    [ "$BACKUP_SUCCEEDED" = "1" ] && return 0
    # Declining because another run holds the lock is not a failed backup, and
    # recording it as one would make a manual run look like a broken nightly.
    [ "$BACKUP_DECLINED" = "1" ] && return 0
    local tmp
    tmp=$(mktemp "${OPS_STATUS_ENV_DIR}/.backup-status.XXXXXX") || return 0
    chmod 600 "$tmp"
    printf '%s\n' \
      '{' \
      '  "format_version": 1,' \
      "  \"attempted_at\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\"," \
      "  \"source_app_env\": \"${SOURCE_APP_ENV}\"," \
      "  \"target\": \"${TARGET_TAG:-unknown}\"," \
      '  "succeeded": false,' \
      '  "verified": false,' \
      '  "offsite_uploaded": false,' \
      "  \"detail\": \"see ${LOG}\"" \
      '}' > "$tmp"
    mv "$tmp" "${OPS_STATUS_ENV_DIR}/backup-status.json"
    chmod 600 "${OPS_STATUS_ENV_DIR}/backup-status.json"
    log "Recorded FAILED backup attempt in ${OPS_STATUS_ENV_DIR}/backup-status.json"
}
LOCK_OWNED=0
release_lock() {
    [ "$LOCK_OWNED" = "1" ] || return 0
    rmdir "$LOCK_DIR" 2>/dev/null || true
    LOCK_OWNED=0
}
trap 'release_lock; write_failure_status' EXIT

# ---- one publisher at a time ------------------------------------------------
# The nightly LaunchDaemon and a human running this by hand can land in the same
# second. Both would compute the same timestamped filename and write over each
# other's temp file, and the loser publishes a truncated archive that passes
# every integrity check because it IS a valid gzip of half a dump. mkdir is the
# atomic primitive available in POSIX sh; the second caller declines and says so
# rather than racing.
LOCK_DIR="${CLINIC_BACKUP_LOCK:-${BACKUP_DIR}/.backup.lock}"
if mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCK_OWNED=1
else
    BACKUP_DECLINED=1
    log "DECLINED: another backup is already active (lock: $LOCK_DIR)"
    exit 1
fi

if [ -n "${PG_DUMP_BIN:-}" ]; then
    [ -x "$PG_DUMP_BIN" ] || {
        log "ERROR: configured pg_dump is not executable: $PG_DUMP_BIN"
        exit 1
    }
else
    PG_DUMP_BIN=$(command -v pg_dump || true)
    [ -n "$PG_DUMP_BIN" ] || {
        log "ERROR: required command not found: pg_dump"
        exit 1
    }
fi
for required in gzip python3 awk wc find date mktemp; do
    command -v "$required" >/dev/null 2>&1 || {
        log "ERROR: required command not found: $required"
        exit 1
    }
done
if ! command -v shasum >/dev/null 2>&1 &&
   ! command -v sha256sum >/dev/null 2>&1; then
    log "ERROR: neither shasum nor sha256sum is available"
    exit 1
fi
PG_DUMP_VERSION=$("$PG_DUMP_BIN" --version 2>/dev/null || true)
log "Preflight OK: pg_dump=${PG_DUMP_BIN} (${PG_DUMP_VERSION:-version unavailable})"

load_libpq_env() {
    local parsed_file
    parsed_file=$(mktemp "${TMPDIR:-/tmp}/clinicai-pgurl.XXXXXX")
    chmod 600 "$parsed_file"
    if ! printf '%s\n' "$PG_URL" | python3 "${REPO}/scripts/lib/parse-postgres-url.py" > "$parsed_file"; then
        rm -f "$parsed_file"
        log "ERROR: DATABASE_URL could not be parsed safely"
        return 1
    fi
    {
        IFS= read -r PGHOST
        IFS= read -r PGPORT
        IFS= read -r PGUSER
        IFS= read -r PGPASSWORD
        IFS= read -r PGDATABASE
        IFS= read -r PGSSLMODE
    } < "$parsed_file"
    rm -f "$parsed_file"
    [ -n "$PGHOST" ] && [ -n "$PGPORT" ] && [ -n "$PGUSER" ] && [ -n "$PGDATABASE" ] || return 1
    export PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE
    if [ -n "$PGSSLMODE" ]; then export PGSSLMODE; else unset PGSSLMODE 2>/dev/null || true; fi
}
load_libpq_env

# ---- name the file after WHICH DATABASE it came from ------------------------
# A dump of the wrong database, filed beside the real ones under an identical
# name, is worse than no backup: it looks like protection. That happened here —
# three manual restore-drill runs against the local database landed in the
# production backup folder as clinicai_<timestamp>.sql.gz, and reading one of
# them led to the confident, wrong conclusion that production carried the
# multi-tenant schema. The only thing that distinguished them was fixture data
# buried inside the dump.
#
# The target's host now goes in the filename, so `ls` alone tells you. No
# credentials: just the host label (the Supabase project ref, or "local").
backup_target_tag() {
    local userinfo host ref
    userinfo=$(printf '%s' "$1" | sed -E 's|^[a-z+]+://||; s|@.*$||; s|:.*$||')
    host=$(printf '%s' "$1" | sed -E 's|^[a-z+]+://[^@]*@?||; s|[:/].*$||')

    # The project ref first, wherever it is. On a POOLER connection the host is
    # shared by every project in the region (aws-1-ap-northeast-2-pooler...) and
    # the ref is in the username as postgres.<ref> — tagging by host there would
    # have produced a name that still did not say which database it was, which
    # is the whole failure being fixed. Caught by running it for real.
    ref=$(printf '%s' "$userinfo" | sed -nE 's|^postgres\.([a-z0-9]{16,})$|\1|p')
    if [ -n "$ref" ]; then printf '%s' "$ref"; return; fi

    case "$host" in
        127.0.0.1|localhost|host.docker.internal) printf 'local' ;;
        db.*.supabase.co|*.supabase.co)
            printf '%s' "$host" | sed -E 's|^db\.||; s|\.supabase\.co$||' ;;
        "") printf 'unknown' ;;
        *) printf '%s' "$host" | tr -c 'a-zA-Z0-9' '-' ;;
    esac
}
TARGET_TAG=$(backup_target_tag "$PG_URL")
log "Backup target: ${SOURCE_APP_ENV} / ${TARGET_TAG}"

# Generate timestamped filename.
TIMESTAMP=$(date "+%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/clinicai_${SOURCE_APP_ENV}_${TARGET_TAG}_${TIMESTAMP}.sql.gz"
TEMP_FILE="${BACKUP_FILE}.tmp"
MANIFEST_FILE="${BACKUP_FILE}.manifest"
TEMP_MANIFEST="${MANIFEST_FILE}.tmp"
trap 'rm -f "$TEMP_FILE" "$TEMP_MANIFEST"; release_lock; write_failure_status' EXIT

sha256_file() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        log "ERROR: neither shasum nor sha256sum is available"
        return 1
    fi
}

# Run pg_dump and compress. pipefail is mandatory: gzip can succeed on an empty
# stream even when pg_dump was not found or exited non-zero.
log "Dumping database..."
if "$PG_DUMP_BIN" --format=plain --schema=public --no-owner --no-acl 2>> "$LOG" | gzip > "$TEMP_FILE"; then
    :
else
    rc=$?
    log "ERROR: pg_dump/gzip pipeline failed (exit code $rc)"
    exit 1
fi

# Verify both the gzip container and the SQL payload before publishing the file.
if ! gzip -t "$TEMP_FILE"; then
    log "ERROR: backup failed gzip integrity validation"
    exit 1
fi
ARCHIVE_BYTES=$(wc -c < "$TEMP_FILE" | tr -d ' ')
if [ "${ARCHIVE_BYTES:-0}" -lt "$MIN_ARCHIVE_BYTES" ]; then
    log "ERROR: compressed backup is implausibly small (${ARCHIVE_BYTES:-0} bytes; minimum ${MIN_ARCHIVE_BYTES})"
    exit 1
fi
UNCOMPRESSED_BYTES=$(gzip -cd "$TEMP_FILE" | wc -c | tr -d ' ')
if [ "${UNCOMPRESSED_BYTES:-0}" -lt 100 ]; then
    log "ERROR: dump payload is implausibly small (${UNCOMPRESSED_BYTES:-0} bytes)"
    exit 1
fi
if ! gzip -cd "$TEMP_FILE" | awk '
    /PostgreSQL database dump/ { seen_header = 1 }
    /PostgreSQL database dump complete/ { seen_complete = 1 }
    /^CREATE TABLE public\.patient[ (]/ { seen_patient = 1 }
    /^CREATE TABLE public\.appointment[ (]/ { seen_appointment = 1 }
    END { exit !(seen_header && seen_complete && seen_patient && seen_appointment) }
'; then
    log "ERROR: dump is missing completeness markers or required core tables"
    exit 1
fi

# ---- companion auth artifact ------------------------------------------------
# public alone is NOT restorable. staff.auth_user_id has a foreign key to
# auth.users, so loading this dump into a database without those rows dies with
# "violates foreign key constraint staff_auth_user_id_fkey" partway through —
# not with missing logins, with a failed restore. Found by actually restoring
# one (scripts/restore-drill.sh); every archive check ever written passed it.
#
# auth.users + auth.identities are what satisfy the key and what let a human log
# in afterwards. They are a few kilobytes. The rest of the auth schema
# (sessions, refresh tokens, MFA challenges) is deliberately excluded: it is
# short-lived state that GoTrue rebuilds, and restoring it into a managed
# project fights the platform's own migrations.
# Same base as its public companion, so the pair is obvious and the auth dump
# carries the target in its name too — it holds the login rows, so a copy from
# the wrong database is exactly as misleading as the schema one.
AUTH_FILE="${BACKUP_FILE%.sql.gz}_auth.sql.gz"
TEMP_AUTH="${AUTH_FILE}.tmp"
trap 'rm -f "$TEMP_FILE" "$TEMP_MANIFEST" "$TEMP_AUTH"; release_lock; write_failure_status' EXIT

log "Dumping auth identities..."
if "$PG_DUMP_BIN" --data-only --no-owner --no-acl \
        --table=auth.users --table=auth.identities 2>> "$LOG" | gzip > "$TEMP_AUTH"; then
    :
else
    rc=$?
    log "ERROR: auth dump failed (exit code $rc) — the public archive alone cannot be restored"
    exit 1
fi
if ! gzip -t "$TEMP_AUTH"; then
    log "ERROR: auth artifact failed gzip integrity validation"
    exit 1
fi
AUTH_RAW_BYTES=$(gzip -cd "$TEMP_AUTH" | wc -c | tr -d ' ')
if ! gzip -cd "$TEMP_AUTH" | grep -q 'COPY auth\.users'; then
    log "ERROR: auth artifact does not contain auth.users — restore would fail on the staff FK"
    exit 1
fi
AUTH_SHA256=$(sha256_file "$TEMP_AUTH")

# ---- companion media artifact -----------------------------------------------
# ẢNH VÀ VIDEO SIÊU ÂM KHÔNG NẰM TRONG DATABASE — và cho tới 08/08/2026 chúng
# không nằm trong bản sao lưu nào cả. `grep media` trong cả bốn script backup /
# restore / verify / offsite đều rỗng: file này chỉ pg_dump.
#
# Nghĩa là khôi phục xong sẽ ra một phòng khám có đủ bệnh án, đủ tài khoản, và
# mọi phiếu siêu âm trỏ tới những tệp không còn tồn tại — `image_refs` đầy khoá
# mà đĩa trống. Không lỗi nào báo; chỉ là ảnh không mở được, và không ai biết
# cho tới hôm cần xem lại.
#
# GIỮ ÍT BẢN HƠN BẢN DUMP, CÓ CHỦ Ý. Tệp media là BẤT BIẾN: mỗi tệp mang một
# UUID mới, không bao giờ bị ghi đè (media_service.safe_path). Nên bản mới nhất
# đã chứa trọn mọi bản cũ, và giữ bảy bản là nhân bảy lần cùng một số gigabyte
# trên một ổ 48G. Hai bản là đủ để một lần tar hỏng không mất trắng.
MEDIA_KEEP_DAYS="${BACKUP_MEDIA_KEEP_DAYS:-2}"
MEDIA_ROOT_HOST=$(grep -E '^MEDIA_DIR=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)
MEDIA_ROOT_HOST=${MEDIA_ROOT_HOST:-${REPO}/.media}
case "$MEDIA_ROOT_HOST" in
    "~/"*) MEDIA_ROOT_HOST="$HOME/${MEDIA_ROOT_HOST#\~/}" ;;
    /*) : ;;
    *) MEDIA_ROOT_HOST="${REPO}/${MEDIA_ROOT_HOST#./}" ;;
esac
# Cùng cách ghép với docker-compose.yml: ${MEDIA_DIR}/${APP_ENV}.
MEDIA_DIR_FOR_ENV="${MEDIA_ROOT_HOST}/${SOURCE_APP_ENV}"

MEDIA_FILE="${BACKUP_FILE%.sql.gz}_media.tar.gz"
TEMP_MEDIA="${MEDIA_FILE}.tmp"
trap 'rm -f "$TEMP_FILE" "$TEMP_MANIFEST" "$TEMP_AUTH" "$TEMP_MEDIA"; release_lock; write_failure_status' EXIT

MEDIA_COUNT=0
MEDIA_SHA256=""
MEDIA_BYTES=0
if [ -d "$MEDIA_DIR_FOR_ENV" ]; then
    MEDIA_COUNT=$(find "$MEDIA_DIR_FOR_ENV" -type f ! -name '*.tmp' | wc -l | tr -d ' ')
fi
if [ "$MEDIA_COUNT" -gt 0 ]; then
    command -v tar >/dev/null 2>&1 || {
        log "ERROR: required command not found: tar (needed for the media artifact)"
        exit 1
    }
    log "Archiving ${MEDIA_COUNT} media file(s) from ${MEDIA_DIR_FOR_ENV}..."
    # Bỏ `.tmp`: đó là những lần ghi đang dở (media_service ghi tệp tạm rồi đổi
    # tên). Đưa chúng vào bản sao lưu là cất lại một tệp hỏng.
    if tar -C "$MEDIA_DIR_FOR_ENV" --exclude='*.tmp' -czf "$TEMP_MEDIA" . 2>> "$LOG"; then
        :
    else
        rc=$?
        log "ERROR: media archive failed (exit code $rc)"
        exit 1
    fi
    gzip -t "$TEMP_MEDIA" || { log "ERROR: media archive failed gzip validation"; exit 1; }
    # Đọc lại danh sách trong tar: một tar rỗng vẫn là gzip hợp lệ, và "sao lưu
    # thành công" với 0 tệp bên trong là đúng thứ ta đang đi sửa.
    TAR_ENTRIES=$(tar -tzf "$TEMP_MEDIA" 2>/dev/null | grep -cv '/$' || true)
    [ "${TAR_ENTRIES:-0}" -ge 1 ] || {
        log "ERROR: media archive lists no files though ${MEDIA_COUNT} exist on disk"
        exit 1
    }
    MEDIA_SHA256=$(sha256_file "$TEMP_MEDIA")
    MEDIA_BYTES=$(wc -c < "$TEMP_MEDIA" | tr -d ' ')
else
    log "NOTICE: no media files under ${MEDIA_DIR_FOR_ENV} — no media artifact this run"
fi

ARCHIVE_SHA256=$(sha256_file "$TEMP_FILE")
cat > "$TEMP_MANIFEST" <<EOF
format_version=1
scope=public-schema-only
complete_supabase_dr=false
requires=supabase-cloud-pitr-and-auth-backup
source_app_env=${SOURCE_APP_ENV}
archive_sha256=${ARCHIVE_SHA256}
raw_bytes=${UNCOMPRESSED_BYTES}
auth_artifact=$(basename "$AUTH_FILE")
auth_sha256=${AUTH_SHA256}
auth_raw_bytes=${AUTH_RAW_BYTES}
media_artifact=$([ "$MEDIA_COUNT" -gt 0 ] && basename "$MEDIA_FILE" || echo none)
media_sha256=${MEDIA_SHA256}
media_file_count=${MEDIA_COUNT}
media_archive_bytes=${MEDIA_BYTES}
restore_order=auth-then-public
EOF

mv "$TEMP_FILE" "$BACKUP_FILE"
mv "$TEMP_AUTH" "$AUTH_FILE"
[ "$MEDIA_COUNT" -gt 0 ] && mv "$TEMP_MEDIA" "$MEDIA_FILE"
mv "$TEMP_MANIFEST" "$MANIFEST_FILE"
trap 'release_lock; write_failure_status' EXIT
chmod 600 "$BACKUP_FILE"
chmod 600 "$AUTH_FILE"
[ "$MEDIA_COUNT" -gt 0 ] && chmod 600 "$MEDIA_FILE"
chmod 600 "$MANIFEST_FILE"
trap release_lock EXIT
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Public-schema backup created and verified: $BACKUP_FILE ($SIZE, $UNCOMPRESSED_BYTES bytes raw)"
log "Auth identities: $AUTH_FILE ($AUTH_RAW_BYTES bytes raw) — restore BEFORE the public archive"
if [ "$MEDIA_COUNT" -gt 0 ]; then
    log "Media: $MEDIA_FILE (${MEDIA_COUNT} file(s), ${MEDIA_BYTES} bytes compressed)"
fi
log "NOTICE: sessions/MFA and Supabase platform config remain outside this backup; retain PITR."

# Prune old backups (keep last KEEP_DAYS days).
DELETED=$(find "$BACKUP_DIR" -name "clinicai_*.sql.gz" -mtime +${KEEP_DAYS} -print -delete 2>> "$LOG" | wc -l | tr -d ' ')
find "$BACKUP_DIR" -name "clinicai_*.sql.gz.manifest" -mtime +${KEEP_DAYS} -delete 2>> "$LOG"
find "$BACKUP_DIR" -name "clinicai_*_auth.sql.gz" -mtime +${KEEP_DAYS} -delete 2>> "$LOG"
[ "$DELETED" -gt 0 ] && log "Pruned $DELETED backup(s) older than ${KEEP_DAYS} days"
# Media giữ ÍT hơn — xem lý do ở phần tạo tệp. Đây là ổ 48G, và bảy bản của
# cùng một tập ảnh bất biến sẽ lấp nó trước khi ai kịp nhận ra.
MEDIA_DELETED=$(find "$BACKUP_DIR" -name "clinicai_*_media.tar.gz" -mtime +${MEDIA_KEEP_DAYS} -print -delete 2>> "$LOG" | wc -l | tr -d ' ')
[ "${MEDIA_DELETED:-0}" -gt 0 ] && log "Pruned $MEDIA_DELETED media archive(s) older than ${MEDIA_KEEP_DAYS} days"

# Optional: push to Cloudflare R2 via rclone.
# Configure rclone first: rclone config (provider: Cloudflare R2)
# Set R2_REMOTE and R2_BUCKET in .env.prod to enable.
R2_REMOTE=$(grep -E '^R2_REMOTE=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
R2_BUCKET=$(grep -E '^R2_BUCKET=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)

R2_UPLOADED=false
if [ -n "${R2_REMOTE:-}" ] && [ -n "${R2_BUCKET:-}" ] && command -v rclone > /dev/null 2>&1; then
    log "Uploading to R2: ${R2_REMOTE}:${R2_BUCKET}/..."
    if rclone copy "$BACKUP_FILE" "${R2_REMOTE}:${R2_BUCKET}/db-backups/" >> "$LOG" 2>&1 &&
       rclone copy "$AUTH_FILE" "${R2_REMOTE}:${R2_BUCKET}/db-backups/" >> "$LOG" 2>&1 &&
       { [ "$MEDIA_COUNT" -eq 0 ] ||
         rclone copy "$MEDIA_FILE" "${R2_REMOTE}:${R2_BUCKET}/db-backups/" >> "$LOG" 2>&1; } &&
       rclone copy "$MANIFEST_FILE" "${R2_REMOTE}:${R2_BUCKET}/db-backups/" >> "$LOG" 2>&1; then
        R2_UPLOADED=true
        log "R2 upload complete"
    else
        log "WARNING: R2 upload failed (backup is still saved locally)"
    fi
else
    log "R2 upload skipped (rclone/R2_REMOTE/R2_BUCKET not configured)"
fi

# Publish only sanitized backup metadata for the read-only Ops Center. The
# archive path, DB URL and backup contents never enter this status directory.
OPS_STATUS_TEMP=$(mktemp "${OPS_STATUS_ENV_DIR}/.backup-status.XXXXXX")
chmod 600 "$OPS_STATUS_TEMP"
COMPLETED_AT=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
printf '%s\n' \
  '{' \
  '  "format_version": 1,' \
  "  \"completed_at\": \"${COMPLETED_AT}\"," \
  '  "succeeded": true,' \
  "  \"source_app_env\": \"${SOURCE_APP_ENV}\"," \
  "  \"archive_bytes\": ${ARCHIVE_BYTES}," \
  '  "verified": true,' \
  "  \"offsite_uploaded\": ${R2_UPLOADED}," \
  '  "scope": "public-schema-only"' \
  '}' > "$OPS_STATUS_TEMP"
BACKUP_SUCCEEDED=1
mv "$OPS_STATUS_TEMP" "${OPS_STATUS_ENV_DIR}/backup-status.json"
chmod 600 "${OPS_STATUS_ENV_DIR}/backup-status.json"

# Summary.
COUNT=$(find "$BACKUP_DIR" -name "clinicai_*.sql.gz" | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log "=== Backup complete. $COUNT backup(s) in $BACKUP_DIR ($TOTAL_SIZE total) ==="

# --- Báo nhịp tim cho Uptime Kuma ------------------------------------------
#
# ĐẶT Ở ĐÂY, SAU MỌI THỨ KHÁC, LÀ CÓ CHỦ Ý. Nhịp tim này nói "đêm nay sao lưu
# ĐÃ CHẠY XONG VÀ ĐÃ VERIFY", nên nó chỉ được gửi khi thật sự tới được dòng này.
# Đặt sớm hơn thì nó chỉ nói "script đã khởi động" — và một cái chuông báo rằng
# script đã khởi động thì vô dụng đúng vào lúc script khởi động rồi chết giữa
# chừng.
#
# `set -e` ở đầu file làm phần còn lại: dump hỏng là script thoát trước khi tới
# đây, Kuma không nhận được gì, và sau 26 giờ im lặng nó tự chuyển đỏ.
#
# VÌ SAO CẦN, dù đã có script kéo về trên máy Mac cũng canh việc này: máy Mac
# phải đang bật mới canh được. Kuma sống trên chính VPS nên nó canh cả những đêm
# không ai mở máy. Hai lớp nhìn từ hai phía, không phải một lớp làm hai lần.
KUMA_PUSH_TOKEN_FILE="${KUMA_PUSH_TOKEN_FILE:-$HOME/.config/clinicai/kuma-push-backup}"
if [ -r "$KUMA_PUSH_TOKEN_FILE" ]; then
    KUMA_TOKEN=$(cat "$KUMA_PUSH_TOKEN_FILE")
    KUMA_URL="${KUMA_PUSH_BASE:-http://127.0.0.1:3001}/api/push/${KUMA_TOKEN}"
    # `|| true`: KHÔNG để một cái chuông hỏng biến thành một lần sao lưu hỏng.
    # Bản sao lưu đã nằm trên đĩa rồi; Kuma không với tới được chỉ có nghĩa là
    # Kuma đang chết, và đó là việc của Kuma.
    if curl -fsS --max-time 10 \
         "${KUMA_URL}?status=up&msg=$(printf '%s' "${COUNT} ban, ${TOTAL_SIZE}" | tr ' ' '+')" \
         >/dev/null 2>&1; then
        log "Kuma: đã báo nhịp tim sao lưu"
    else
        log "WARNING: không báo được nhịp tim cho Kuma (bản sao lưu VẪN AN TOÀN)"
    fi
else
    log "Kuma: chưa có token push ($KUMA_PUSH_TOKEN_FILE) — chạy scripts/setup-uptime-kuma.sh"
fi
