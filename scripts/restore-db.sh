#!/bin/bash
# Restore a ClinicAI database backup.
#
# Usage (the target is mandatory — never infer production):
#   ./scripts/restore-db.sh <backup-file.sql.gz> staging
#   ALLOW_CUSTOM_RESTORE=1 ./scripts/restore-db.sh <backup> /absolute/path/to/test.env
#
# Restores run in one transaction with ON_ERROR_STOP and are validated afterward.
# Production additionally requires ALLOW_PROD_RESTORE=1.
set -euo pipefail
umask 077

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_FILE="${1:-}"
TARGET_SELECTOR="${2:-}"

if [ -z "$BACKUP_FILE" ] || [ -z "$TARGET_SELECTOR" ]; then
    echo "Usage: $0 <backup-file.sql.gz> <prod|staging|/absolute/path/to/env>"
    echo ""
    echo "Available backups:"
    ls -lh ~/backups/clinicai/clinicai_*.sql.gz 2>/dev/null || echo "  (none found in ~/backups/clinicai/)"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: file not found: $BACKUP_FILE"
    exit 1
fi

# Resolve the explicit target env file.
case "$TARGET_SELECTOR" in
    prod)
        ENV_FILE="${REPO}/.env.prod"
        TARGET_LABEL="PROD"
        [ "${ALLOW_PROD_RESTORE:-0}" = "1" ] || {
            echo "ERROR: production restore requires ALLOW_PROD_RESTORE=1" >&2
            exit 1
        }
        ;;
    staging)
        ENV_FILE="${REPO}/.env.staging"
        TARGET_LABEL="STAGING"
        ;;
    *)
        [ "${ALLOW_CUSTOM_RESTORE:-0}" = "1" ] || {
            echo "ERROR: custom env paths require ALLOW_CUSTOM_RESTORE=1" >&2
            exit 1
        }
        ENV_FILE="$TARGET_SELECTOR"
        TARGET_LABEL=$(basename "$ENV_FILE" | sed -E 's/^\.env\.//; s/\.env$//' | tr '[:lower:]' '[:upper:]')
        ;;
esac
[ -f "$ENV_FILE" ] || { echo "ERROR: env file not found: $ENV_FILE" >&2; exit 1; }

# Gate production by the resolved environment contents, not by the selector
# spelling. Otherwise an operator could bypass the guard with `/path/.env.prod`.
APP_ENV=$(grep -E '^APP_ENV=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)
case "$APP_ENV" in
    production) TARGET_LABEL="PROD"; TARGET_APP_ENV="production" ;;
    staging) TARGET_LABEL="STAGING"; TARGET_APP_ENV="staging" ;;
    test|development) TARGET_APP_ENV="$APP_ENV" ;;
    *) echo "ERROR: APP_ENV in target env must explicitly identify production, staging, test, or development" >&2; exit 1 ;;
esac

DATABASE_URL=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)
[ -n "$DATABASE_URL" ] || { echo "ERROR: DATABASE_URL not found"; exit 1; }

# Also recognize a copied/renamed production URL even if its APP_ENV was edited.
PROD_DATABASE_URL=""
if [ -f "${REPO}/.env.prod" ]; then
    PROD_DATABASE_URL=$(grep -E '^DATABASE_URL=' "${REPO}/.env.prod" | head -1 | cut -d= -f2- || true)
fi
if [ "$APP_ENV" = "production" ] || { [ -n "$PROD_DATABASE_URL" ] && [ "$DATABASE_URL" = "$PROD_DATABASE_URL" ]; }; then
    TARGET_LABEL="PROD"
    TARGET_APP_ENV="production"
    [ "${ALLOW_PROD_RESTORE:-0}" = "1" ] || {
        echo "ERROR: production restore requires ALLOW_PROD_RESTORE=1" >&2
        exit 1
    }
fi

PG_URL="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"

for required in gzip psql awk python3; do
    command -v "$required" >/dev/null 2>&1 || {
        echo "ERROR: required command not found: $required" >&2
        exit 1
    }
done

load_libpq_env() {
    local parsed_file
    parsed_file=$(mktemp "${TMPDIR:-/tmp}/clinicai-pgurl.XXXXXX")
    chmod 600 "$parsed_file"
    if ! printf '%s\n' "$PG_URL" | python3 "${REPO}/scripts/lib/parse-postgres-url.py" > "$parsed_file"; then
        rm -f "$parsed_file"
        echo "ERROR: DATABASE_URL could not be parsed safely" >&2
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

sha256_file() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        echo "ERROR: neither shasum nor sha256sum is available" >&2
        return 1
    fi
}

# A public-only dump must never be mistaken for a full Supabase DR backup.
# The sidecar makes scope/checksum explicit and restore refuses legacy/untracked
# archives. Auth identities and managed schemas must be recoverable via Supabase
# cloud PITR/platform backup before this application-data restore is attempted.
MANIFEST_FILE="${BACKUP_FILE}.manifest"
[ -f "$MANIFEST_FILE" ] || {
    echo "ERROR: required backup manifest not found: $MANIFEST_FILE" >&2
    exit 1
}
grep -qx 'format_version=1' "$MANIFEST_FILE" &&
grep -qx 'scope=public-schema-only' "$MANIFEST_FILE" &&
grep -qx 'complete_supabase_dr=false' "$MANIFEST_FILE" &&
grep -qx 'requires=supabase-cloud-pitr-and-auth-backup' "$MANIFEST_FILE" || {
    echo "ERROR: unsupported or incomplete backup manifest" >&2
    exit 1
}
EXPECTED_SHA=$(grep -E '^archive_sha256=' "$MANIFEST_FILE" | head -1 | cut -d= -f2- || true)
ACTUAL_SHA=$(sha256_file "$BACKUP_FILE")
[ -n "$EXPECTED_SHA" ] && [ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || {
    echo "ERROR: backup checksum does not match its manifest" >&2
    exit 1
}
SOURCE_APP_ENV=$(grep -E '^source_app_env=' "$MANIFEST_FILE" | head -1 | cut -d= -f2- || true)
case "$SOURCE_APP_ENV" in
    production|staging|test|development) : ;;
    *) echo "ERROR: backup manifest has no valid source environment identity" >&2; exit 1 ;;
esac
if [ "$SOURCE_APP_ENV" != "$TARGET_APP_ENV" ] && [ "${ALLOW_CROSS_ENV_RESTORE:-0}" != "1" ]; then
    echo "ERROR: refusing $SOURCE_APP_ENV → $TARGET_APP_ENV restore without ALLOW_CROSS_ENV_RESTORE=1" >&2
    exit 1
fi

# Refuse corrupt/truncated/empty archives before touching the target.
gzip -t "$BACKUP_FILE" || { echo "ERROR: invalid gzip archive" >&2; exit 1; }
UNCOMPRESSED_BYTES=$(gzip -cd "$BACKUP_FILE" | wc -c | tr -d ' ')
[ "${UNCOMPRESSED_BYTES:-0}" -ge 100 ] || {
    echo "ERROR: dump payload is implausibly small (${UNCOMPRESSED_BYTES:-0} bytes)" >&2
    exit 1
}
gzip -cd "$BACKUP_FILE" | awk '
    /PostgreSQL database dump/ { seen_header = 1 }
    /PostgreSQL database dump complete/ { seen_complete = 1 }
    END { exit !(seen_header && seen_complete) }
' || { echo "ERROR: dump completeness markers are missing" >&2; exit 1; }

# Verify connectivity and require an empty target. This dump intentionally lacks
# destructive DROP statements, so an overwrite mode would be unsafe/misleading.
# The restore itself rolls back completely on the first SQL error.
TARGET_DB=$(psql -X -v ON_ERROR_STOP=1 -Atqc 'SELECT current_database();')
EXISTING_TABLES=$(psql -X -v ON_ERROR_STOP=1 -Atqc \
    "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';")
case "$EXISTING_TABLES" in
    ''|*[!0-9]*) echo "ERROR: could not validate target schema state" >&2; exit 1 ;;
esac
if [ "$EXISTING_TABLES" -gt 0 ]; then
    echo "ERROR: target already has $EXISTING_TABLES public tables." >&2
    echo "Restore this plain SQL backup only into a fresh database." >&2
    exit 1
fi

# Show backup info.
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ⚠️  DATABASE RESTORE — THIS WILL OVERWRITE CURRENT DATA    ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Backup file: $(basename "$BACKUP_FILE")"
echo "║  File size:   $SIZE"
echo "║  Target env:  $TARGET_LABEL ($ENV_FILE)"
echo "║  Target DB:   $TARGET_DB"
echo "║  Scope:       public schema only (source: $SOURCE_APP_ENV)"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
read -r -p "Type 'RESTORE $TARGET_LABEL' to confirm: " CONFIRM

if [ "$CONFIRM" != "RESTORE $TARGET_LABEL" ]; then
    echo "Aborted."
    exit 1
fi

echo "Restoring..."
# Append the invariant assertion to the same psql input. With
# --single-transaction + ON_ERROR_STOP, missing core tables now abort before
# COMMIT instead of being discovered after a partial-but-committed restore.
# A stock/fresh PostgreSQL database already owns an empty `public` schema.
# The live schema also contains legacy SQL functions whose bodies resolve
# public extension/functions during data load. Rewrite only these two exact
# pg_dump preamble statements; filtering anything broader could alter data SQL.
if { gzip -cd "$BACKUP_FILE" | awk '
    $0 == "CREATE SCHEMA public;" { next }
    $0 == "SELECT pg_catalog.set_config('\''search_path'\'', '\'''\'', false);" {
        print "SELECT pg_catalog.set_config('\''search_path'\'', '\''public, pg_catalog'\'', false);"
        next
    }
    { print }
'; printf '%s\n' \
    "DO \$verify\$ BEGIN IF to_regclass('public.patient') IS NULL OR to_regclass('public.appointment') IS NULL THEN RAISE EXCEPTION 'core-table validation failed'; END IF; END \$verify\$;"; } | \
    psql -X -v ON_ERROR_STOP=1 --single-transaction --quiet; then
    CORE_TABLES=$(psql -X -v ON_ERROR_STOP=1 -Atqc \
        "SELECT coalesce(to_regclass('public.patient')::text, '') || '|' || coalesce(to_regclass('public.appointment')::text, '');")
    if [ "$CORE_TABLES" != "patient|appointment" ]; then
        echo "ERROR: restore completed but core-table validation failed ($CORE_TABLES)." >&2
        exit 1
    fi
    echo "✅ Restore complete and validated."
else
    echo "❌ Restore failed; ON_ERROR_STOP + single transaction rolled back all changes." >&2
    exit 1
fi

# ---- media files ------------------------------------------------------------
# Database khôi phục xong mà thư mục ảnh trống thì mọi phiếu siêu âm trỏ tới
# những khoá không còn tệp — `image_refs` đầy, đĩa rỗng, không lỗi nào báo.
#
# KHÔNG TỰ GIẢI NÉN ĐÈ. Đích đến là thư mục media đang chạy của một môi trường
# thật, và một lệnh `tar -x` chạy nhầm vào đó là ghi đè ảnh bệnh nhân bằng bản
# cũ hơn. Nên: mặc định chỉ NÓI RA phải làm gì; chỉ giải nén khi người chạy
# khai rõ RESTORE_MEDIA_TO=<thư mục>.
MEDIA_NAME=$(grep -E '^media_artifact=' "$MANIFEST_FILE" | head -n 1 | cut -d= -f2- || true)
if [ -z "$MEDIA_NAME" ]; then
    echo "⚠️  Bản sao lưu này theo định dạng cũ (không khai media). Ảnh siêu âm KHÔNG được khôi phục."
elif [ "$MEDIA_NAME" = "none" ]; then
    echo "ℹ️  Bản sao lưu không kèm tệp media (lúc sao lưu chưa có ảnh nào)."
else
    MEDIA_PATH="$(dirname "$BACKUP_FILE")/${MEDIA_NAME}"
    if [ ! -f "$MEDIA_PATH" ]; then
        echo "⚠️  Manifest khai có media nhưng không thấy tệp: $MEDIA_PATH" >&2
        echo "    Database đã khôi phục; ẢNH THÌ CHƯA." >&2
        exit 1
    fi
    if [ -n "${RESTORE_MEDIA_TO:-}" ]; then
        mkdir -p "$RESTORE_MEDIA_TO"
        tar -C "$RESTORE_MEDIA_TO" -xzf "$MEDIA_PATH"
        SO_TEP=$(find "$RESTORE_MEDIA_TO" -type f | wc -l | tr -d ' ')
        echo "✅ Đã giải nén media vào $RESTORE_MEDIA_TO (${SO_TEP} tệp)."
    else
        echo "ℹ️  Media nằm ở: $MEDIA_PATH"
        echo "    Giải nén bằng:  RESTORE_MEDIA_TO=<thư mục media> $0 ... "
        echo "    hoặc thủ công:  tar -C <thư mục media> -xzf '$MEDIA_PATH'"
    fi
fi
