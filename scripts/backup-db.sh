#!/bin/bash
# Automated nightly public-schema application-data backup for ClinicAI.
# This is not a complete Supabase disaster-recovery artifact: auth identities,
# managed schemas, roles, and platform configuration require Supabase PITR/backup.
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

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$HOME/Library/Logs/clinicai-backup.log"
BACKUP_DIR="$HOME/backups/clinicai"
KEEP_DAYS=7

mkdir -p "$(dirname "$LOG")" "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

log "=== Backup starting ==="

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

for required in pg_dump gzip python3; do
    command -v "$required" >/dev/null 2>&1 || {
        log "ERROR: required command not found: $required"
        exit 1
    }
done

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

# Generate timestamped filename.
TIMESTAMP=$(date "+%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/clinicai_${TIMESTAMP}.sql.gz"
TEMP_FILE="${BACKUP_FILE}.tmp"
MANIFEST_FILE="${BACKUP_FILE}.manifest"
TEMP_MANIFEST="${MANIFEST_FILE}.tmp"
trap 'rm -f "$TEMP_FILE" "$TEMP_MANIFEST"' EXIT

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
if pg_dump --format=plain --schema=public --no-owner --no-acl 2>> "$LOG" | gzip > "$TEMP_FILE"; then
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

ARCHIVE_SHA256=$(sha256_file "$TEMP_FILE")
cat > "$TEMP_MANIFEST" <<EOF
format_version=1
scope=public-schema-only
complete_supabase_dr=false
requires=supabase-cloud-pitr-and-auth-backup
source_app_env=${SOURCE_APP_ENV}
archive_sha256=${ARCHIVE_SHA256}
raw_bytes=${UNCOMPRESSED_BYTES}
EOF

mv "$TEMP_FILE" "$BACKUP_FILE"
mv "$TEMP_MANIFEST" "$MANIFEST_FILE"
chmod 600 "$BACKUP_FILE"
chmod 600 "$MANIFEST_FILE"
trap - EXIT
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
ARCHIVE_BYTES=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
log "Public-schema backup created and verified: $BACKUP_FILE ($SIZE, $UNCOMPRESSED_BYTES bytes raw)"
log "NOTICE: Supabase auth/managed schemas and roles are outside this application-data backup; retain PITR/platform backups."

# Prune old backups (keep last KEEP_DAYS days).
DELETED=$(find "$BACKUP_DIR" -name "clinicai_*.sql.gz" -mtime +${KEEP_DAYS} -print -delete 2>> "$LOG" | wc -l | tr -d ' ')
find "$BACKUP_DIR" -name "clinicai_*.sql.gz.manifest" -mtime +${KEEP_DAYS} -delete 2>> "$LOG"
[ "$DELETED" -gt 0 ] && log "Pruned $DELETED backup(s) older than ${KEEP_DAYS} days"

# Optional: push to Cloudflare R2 via rclone.
# Configure rclone first: rclone config (provider: Cloudflare R2)
# Set R2_REMOTE and R2_BUCKET in .env.prod to enable.
R2_REMOTE=$(grep -E '^R2_REMOTE=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
R2_BUCKET=$(grep -E '^R2_BUCKET=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)

R2_UPLOADED=false
if [ -n "${R2_REMOTE:-}" ] && [ -n "${R2_BUCKET:-}" ] && command -v rclone > /dev/null 2>&1; then
    log "Uploading to R2: ${R2_REMOTE}:${R2_BUCKET}/..."
    if rclone copy "$BACKUP_FILE" "${R2_REMOTE}:${R2_BUCKET}/db-backups/" >> "$LOG" 2>&1 &&
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
OPS_STATUS_TEMP=$(mktemp "${OPS_STATUS_ENV_DIR}/.backup-status.XXXXXX")
chmod 600 "$OPS_STATUS_TEMP"
COMPLETED_AT=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
printf '%s\n' \
  '{' \
  '  "format_version": 1,' \
  "  \"completed_at\": \"${COMPLETED_AT}\"," \
  "  \"source_app_env\": \"${SOURCE_APP_ENV}\"," \
  "  \"archive_bytes\": ${ARCHIVE_BYTES}," \
  '  "verified": true,' \
  "  \"offsite_uploaded\": ${R2_UPLOADED}," \
  '  "scope": "public-schema-only"' \
  '}' > "$OPS_STATUS_TEMP"
mv "$OPS_STATUS_TEMP" "${OPS_STATUS_ENV_DIR}/backup-status.json"
chmod 600 "${OPS_STATUS_ENV_DIR}/backup-status.json"

# Summary.
COUNT=$(find "$BACKUP_DIR" -name "clinicai_*.sql.gz" | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log "=== Backup complete. $COUNT backup(s) in $BACKUP_DIR ($TOTAL_SIZE total) ==="
