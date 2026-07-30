#!/bin/bash
# Verify that the latest (or explicitly selected) ClinicAI public-schema backup
# is recent, non-trivial, intact, complete, and matches its sidecar checksum.
#
# Usage:
#   ./scripts/verify-backup.sh
#   ./scripts/verify-backup.sh ~/backups/clinicai/clinicai_<timestamp>.sql.gz
#
# Tunables for monitoring/tests:
#   BACKUP_MAX_AGE_HOURS=30
#   BACKUP_MIN_ARCHIVE_BYTES=1024
set -euo pipefail

DEFAULT_COMMAND_PATH="/opt/homebrew/opt/libpq/bin:/opt/homebrew/opt/postgresql@17/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH="${CLINIC_BACKUP_PATH:-${DEFAULT_COMMAND_PATH}${PATH:+:${PATH}}}"

BACKUP_DIR="${BACKUP_DIR:-${HOME}/backups/clinicai}"
MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-30}"
MIN_ARCHIVE_BYTES="${BACKUP_MIN_ARCHIVE_BYTES:-1024}"
BACKUP_FILE="${1:-}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

case "$MAX_AGE_HOURS" in
    ''|*[!0-9]*) fail "BACKUP_MAX_AGE_HOURS must be a non-negative integer" ;;
esac
case "$MIN_ARCHIVE_BYTES" in
    ''|*[!0-9]*) fail "BACKUP_MIN_ARCHIVE_BYTES must be a positive integer" ;;
esac
[ "$MIN_ARCHIVE_BYTES" -ge 1 ] || \
    fail "BACKUP_MIN_ARCHIVE_BYTES must be at least 1"

for required in find sort tail stat date wc gzip awk grep cut; do
    command -v "$required" >/dev/null 2>&1 || \
        fail "required command not found: $required"
done
if command -v shasum >/dev/null 2>&1; then
    SHA_COMMAND=shasum
elif command -v sha256sum >/dev/null 2>&1; then
    SHA_COMMAND=sha256sum
else
    fail "neither shasum nor sha256sum is available"
fi

if [ -z "$BACKUP_FILE" ]; then
    BACKUP_FILE=$(find "$BACKUP_DIR" -maxdepth 1 -type f \
        -name 'clinicai_*.sql.gz' ! -name '*_auth.sql.gz' \
        -print 2>/dev/null | LC_ALL=C sort | tail -n 1)
fi
[ -n "$BACKUP_FILE" ] || fail "no ClinicAI backup artifact found in $BACKUP_DIR"
[ -f "$BACKUP_FILE" ] || fail "backup artifact not found: $BACKUP_FILE"

MANIFEST_FILE="${BACKUP_FILE}.manifest"
[ -f "$MANIFEST_FILE" ] || fail "backup manifest not found: $MANIFEST_FILE"

ARCHIVE_BYTES=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
case "$ARCHIVE_BYTES" in
    ''|*[!0-9]*) fail "could not determine backup artifact size" ;;
esac
[ "$ARCHIVE_BYTES" -ge "$MIN_ARCHIVE_BYTES" ] || \
    fail "backup artifact is too small (${ARCHIVE_BYTES} bytes; minimum ${MIN_ARCHIVE_BYTES})"

MODIFIED_AT=$(stat -f '%m' "$BACKUP_FILE" 2>/dev/null || true)
case "$MODIFIED_AT" in
    ''|*[!0-9]*)
        MODIFIED_AT=$(stat -c '%Y' "$BACKUP_FILE" 2>/dev/null) || \
            fail "could not determine backup artifact modification time"
        ;;
esac
NOW=$(date +%s)
case "$MODIFIED_AT" in
    ''|*[!0-9]*) fail "invalid backup artifact modification time" ;;
esac
AGE_SECONDS=$((NOW - MODIFIED_AT))
[ "$AGE_SECONDS" -lt 0 ] && AGE_SECONDS=0
MAX_AGE_SECONDS=$((MAX_AGE_HOURS * 3600))
[ "$AGE_SECONDS" -le "$MAX_AGE_SECONDS" ] || \
    fail "backup artifact is stale (${AGE_SECONDS}s old; maximum ${MAX_AGE_SECONDS}s)"

gzip -t "$BACKUP_FILE" || fail "backup artifact failed gzip integrity validation"
gzip -cd "$BACKUP_FILE" | awk '
    /PostgreSQL database dump/ { seen_header = 1 }
    /PostgreSQL database dump complete/ { seen_complete = 1 }
    /^CREATE TABLE public\.patient[ (]/ { seen_patient = 1 }
    /^CREATE TABLE public\.appointment[ (]/ { seen_appointment = 1 }
    END { exit !(seen_header && seen_complete && seen_patient && seen_appointment) }
' || fail "backup artifact is missing completeness markers or core tables"

grep -qx 'format_version=1' "$MANIFEST_FILE" &&
grep -qx 'scope=public-schema-only' "$MANIFEST_FILE" &&
grep -qx 'complete_supabase_dr=false' "$MANIFEST_FILE" &&
grep -qx 'requires=supabase-cloud-pitr-and-auth-backup' "$MANIFEST_FILE" || \
    fail "backup manifest is unsupported or incomplete"

EXPECTED_SHA=$(grep -E '^archive_sha256=' "$MANIFEST_FILE" | head -n 1 | cut -d= -f2- || true)
if [ "$SHA_COMMAND" = "shasum" ]; then
    ACTUAL_SHA=$(shasum -a 256 "$BACKUP_FILE" | awk '{print $1}')
else
    ACTUAL_SHA=$(sha256sum "$BACKUP_FILE" | awk '{print $1}')
fi
[ -n "$EXPECTED_SHA" ] && [ "$EXPECTED_SHA" = "$ACTUAL_SHA" ] || \
    fail "backup checksum does not match its manifest"

echo "Backup verified: $(basename "$BACKUP_FILE") (${ARCHIVE_BYTES} bytes, ${AGE_SECONDS}s old)"
