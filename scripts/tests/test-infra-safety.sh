#!/bin/bash
# Deterministic smoke tests for the destructive infrastructure scripts.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/clinicai-infra-test.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

FAKE_BIN="$TMP_ROOT/bin"
TEST_HOME="$TMP_ROOT/home"
TEST_ENV="$TMP_ROOT/test.env"
mkdir -p "$FAKE_BIN" "$TEST_HOME"
printf '%s\n' \
  'APP_ENV=test' \
  'DATABASE_URL=postgresql://test%2Ber:s%40cret@db.example.test:6543/clinic%5Ftest?sslmode=require' > "$TEST_ENV"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

make_pg_dump() {
  local mode="$1"
  if [ "$mode" = "fail" ]; then
    printf '%s\n' '#!/bin/bash' 'exit 42' > "$FAKE_BIN/pg_dump"
  elif [ "$mode" = "incomplete" ]; then
    printf '%s\n' \
      '#!/bin/bash' \
      '[ "${PGHOST:-}" = "db.example.test" ] || exit 81' \
      '[ "${PGPORT:-}" = "6543" ] || exit 82' \
      '[ "${PGUSER:-}" = "test+er" ] || exit 83' \
      '[ "${PGPASSWORD:-}" = "s@cret" ] || exit 84' \
      '[ "${PGDATABASE:-}" = "clinic_test" ] || exit 85' \
      '[ "${PGSSLMODE:-}" = "require" ] || exit 86' \
      '[[ "$*" != *"cret"* ]] || exit 87' \
      'echo "-- PostgreSQL database dump"' \
      'echo "CREATE TABLE public.patient (id uuid);"' \
      'echo "-- PostgreSQL database dump complete"' > "$FAKE_BIN/pg_dump"
  else
    printf '%s\n' \
      '#!/bin/bash' \
      'echo "-- PostgreSQL database dump"' \
      'echo "SELECT pg_catalog.set_config('\''search_path'\'', '\'''\'', false);"' \
      'echo "CREATE SCHEMA public;"' \
      'echo "CREATE TABLE public.patient (id uuid);"' \
      'echo "CREATE TABLE public.appointment (id uuid);"' \
      'echo "-- PostgreSQL database dump complete"' > "$FAKE_BIN/pg_dump"
  fi
  chmod +x "$FAKE_BIN/pg_dump"
}

test_backup_rejects_structurally_incomplete_dump() {
  make_pg_dump incomplete
  if HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    BACKUP_ENV_FILE="$TEST_ENV" "$ROOT/scripts/backup-db.sh"; then
    fail "backup accepted a dump missing a required core table"
  fi
  if find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' -type f 2>/dev/null | grep -q .; then
    fail "backup published a structurally incomplete archive"
  fi
}

make_psql() {
  cat > "$FAKE_BIN/psql" <<'PSQL'
#!/bin/bash
set -eu
args="$*"
[ "${PGHOST:-}" = "db.example.test" ] || exit 81
[ "${PGPORT:-}" = "6543" ] || exit 82
[ "${PGUSER:-}" = "test+er" ] || exit 83
[ "${PGPASSWORD:-}" = "s@cret" ] || exit 84
[ "${PGDATABASE:-}" = "clinic_test" ] || exit 85
[ "${PGSSLMODE:-}" = "require" ] || exit 86
[[ "$args" != *"cret"* ]] || exit 87
if [[ "$args" == *"current_database()"* ]]; then
  echo "clinic_test"
elif [[ "$args" == *"FROM pg_tables"* ]]; then
  echo "0"
elif [[ "$args" == *"to_regclass('public.patient')"* ]]; then
  printf 'patient|appointment\n'
else
  cat > "${FAKE_PSQL_STDIN:?}"
  [ "${FAKE_PSQL_FAIL:-0}" != "1" ] || exit 9
fi
PSQL
  chmod +x "$FAKE_BIN/psql"
}

test_backup_rejects_failed_dump() {
  make_pg_dump fail
  if HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    BACKUP_ENV_FILE="$TEST_ENV" "$ROOT/scripts/backup-db.sh"; then
    fail "backup accepted a failed pg_dump"
  fi
  if find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' -type f 2>/dev/null | grep -q .; then
    fail "backup left an archive after pg_dump failure"
  fi
}

test_backup_creates_verified_archive() {
  make_pg_dump ok
  HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    BACKUP_ENV_FILE="$TEST_ENV" "$ROOT/scripts/backup-db.sh"
  archive="$(find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' -type f | head -1)"
  [ -n "$archive" ] || fail "backup did not create an archive"
  gzip -t "$archive" || fail "backup archive failed gzip validation"
  gzip -cd "$archive" | grep -q 'PostgreSQL database dump complete' || \
    fail "backup archive does not contain a complete dump marker"
  [ -f "${archive}.manifest" ] || fail "backup did not create a scope/checksum manifest"
  grep -qx 'complete_supabase_dr=false' "${archive}.manifest" || \
    fail "backup manifest incorrectly presents public data as full Supabase DR"
  status_file="$TEST_HOME/.clinicai/ops/test/backup-status.json"
  [ -f "$status_file" ] || fail "backup did not publish sanitized Ops metadata"
  grep -q '"verified": true' "$status_file" || fail "Ops backup metadata is not verified"
  if grep -Eq 'DATABASE_URL|archive_path|db\.example|s@cret' "$status_file"; then
    fail "Ops backup metadata leaked a path or secret"
  fi
}

test_restore_is_atomic_and_explicit() {
  make_psql
  archive="$(find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' -type f | head -1)"
  stdin_capture="$TMP_ROOT/psql-input.sql"

  if printf 'RESTORE TEST\n' | HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    FAKE_PSQL_STDIN="$stdin_capture" "$ROOT/scripts/restore-db.sh" "$archive"; then
    fail "restore accepted an implicit target"
  fi

  printf 'RESTORE TEST\n' | HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    ALLOW_CUSTOM_RESTORE=1 FAKE_PSQL_STDIN="$stdin_capture" \
    "$ROOT/scripts/restore-db.sh" "$archive" "$TEST_ENV"
  grep -q 'PostgreSQL database dump complete' "$stdin_capture" || \
    fail "restore did not stream the verified dump to psql"
  if grep -qx 'CREATE SCHEMA public;' "$stdin_capture"; then
    fail "restore did not remove pg_dump's conflicting public-schema preamble"
  fi
  grep -Fqx "SELECT pg_catalog.set_config('search_path', 'public, pg_catalog', false);" "$stdin_capture" || \
    fail "restore did not establish the public search path for legacy schema functions"

  if printf 'RESTORE TEST\n' | HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    FAKE_PSQL_STDIN="$stdin_capture" FAKE_PSQL_FAIL=1 \
    ALLOW_CUSTOM_RESTORE=1 \
    "$ROOT/scripts/restore-db.sh" "$archive" "$TEST_ENV"; then
    fail "restore ignored a psql failure"
  fi

  cp "${archive}.manifest" "$TMP_ROOT/saved.manifest"
  printf '%s\n' 'archive_sha256=invalid' > "${archive}.manifest"
  if printf 'RESTORE TEST\n' | HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    FAKE_PSQL_STDIN="$stdin_capture" \
    ALLOW_CUSTOM_RESTORE=1 \
    "$ROOT/scripts/restore-db.sh" "$archive" "$TEST_ENV" >/dev/null 2>&1; then
    fail "restore accepted a backup with an invalid manifest"
  fi
  mv "$TMP_ROOT/saved.manifest" "${archive}.manifest"

  prod_env="$TMP_ROOT/custom-production.env"
  printf '%s\n' \
    'APP_ENV=production' \
    'DATABASE_URL=postgresql://tester:secret@db.example.test:5432/clinic_test' > "$prod_env"
  if printf 'RESTORE PROD\n' | HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    ALLOW_CUSTOM_RESTORE=1 FAKE_PSQL_STDIN="$stdin_capture" \
    "$ROOT/scripts/restore-db.sh" "$archive" "$prod_env" >/dev/null 2>&1; then
    fail "restore allowed a production env path without ALLOW_PROD_RESTORE=1"
  fi
}

test_compose_requires_explicit_runtime_env() {
  grep -Fq 'env_file: ["${CLINIC_ENV_FILE:?' "$ROOT/docker-compose.yml" || \
    fail "compose runtime env is not fail-closed"
  if grep -Fq 'env_file: [.env]' "$ROOT/docker-compose.yml"; then
    fail "compose still hardcodes the shared .env file"
  fi
}

test_deploy_is_pinned_and_serialized() {
  grep -Fq 'DEPLOY_EXPECTED_SHA' "$ROOT/scripts/deploy-backend.sh" || \
    fail "deploy script does not verify an expected commit"
  if grep -Eq 'cp +"?\$ENV_FILE"? +\.env|git pull --ff-only *\|\|' "$ROOT/scripts/deploy-backend.sh"; then
    fail "deploy script still copies shared env or swallows pull failure"
  fi
  grep -Fq 'group: clinicai-macmini-deploy' "$ROOT/.github/workflows/cd.yml" || \
    fail "prod and staging deployments are not globally serialized"
  grep -Fq 'ref: ${{ github.sha }}' "$ROOT/.github/workflows/cd.yml" || \
    fail "CD does not checkout the triggering commit"
}

test_deploy_exact_sha_smoke() {
  local deploy_repo="$TMP_ROOT/deploy-repo"
  local deploy_secrets="$TMP_ROOT/deploy-secrets"
  local deploy_tmp="$TMP_ROOT/deploy-tmp"
  mkdir -p "$deploy_repo/scripts" "$deploy_secrets" "$deploy_tmp"
  cp "$ROOT/scripts/deploy-backend.sh" "$deploy_repo/scripts/deploy-backend.sh"
  chmod +x "$deploy_repo/scripts/deploy-backend.sh"
  cat > "$deploy_secrets/.env.prod" <<'ENV'
APP_ENV=production
COMPOSE_PROJECT_NAME=clinicai_prod
IMAGE_TAG=prod
SITE_ADDRESS=:80
SUPABASE_URL=https://prod.example.test
SUPABASE_ANON_KEY=anon-test
SUPABASE_SERVICE_ROLE_KEY=service-test
DATABASE_URL=postgresql://test:test@db.example.test:5432/test
BACKEND_API_KEY=backend-test
ENV
  cat > "$FAKE_BIN/docker" <<'DOCKER'
#!/bin/bash
set -eu
if [ "${1:-}" = "image" ] && [ "${2:-}" = "inspect" ]; then
  exit 1
fi
if [ "${1:-}" = "inspect" ]; then
  echo healthy
  exit 0
fi
for arg in "$@"; do
  if [ "$arg" = "ps" ]; then
    echo fake-container-id
    exit 0
  fi
done
exit 0
DOCKER
  chmod +x "$FAKE_BIN/docker"

  git -C "$deploy_repo" init -q
  git -C "$deploy_repo" add scripts/deploy-backend.sh
  git -C "$deploy_repo" -c user.name=Test -c user.email=test@example.test commit -qm init
  local sha
  sha="$(git -C "$deploy_repo" rev-parse HEAD)"

  HOME="$TEST_HOME" TMPDIR="$deploy_tmp" PATH="$FAKE_BIN:/usr/bin:/bin" \
    CLINIC_PATH_PREFIX="$FAKE_BIN" CLINIC_ENV_DIR="$deploy_secrets" \
    CLINIC_DEPLOY_LOCK="$deploy_tmp/deploy.lock" DEPLOY_EXPECTED_SHA="$sha" \
    DEPLOY_SOURCE_BRANCH=main "$deploy_repo/scripts/deploy-backend.sh" prod >/dev/null
  [ ! -e "$deploy_repo/.env" ] || fail "deploy copied secrets into a shared .env"
  [ -f "$deploy_secrets/.active-state-prod" ] || fail "deploy did not atomically record active release state"
  active_env="$(grep -E '^env=' "$deploy_secrets/.active-state-prod" | cut -d= -f2-)"
  [ -f "$active_env" ] || fail "active env revision does not exist"
  [ "$(stat -f '%Lp' "$active_env" 2>/dev/null || stat -c '%a' "$active_env")" = "600" ] || \
    fail "active env revision is not mode 600"

  if HOME="$TEST_HOME" TMPDIR="$deploy_tmp" PATH="$FAKE_BIN:/usr/bin:/bin" \
    CLINIC_PATH_PREFIX="$FAKE_BIN" CLINIC_ENV_DIR="$deploy_secrets" \
    CLINIC_DEPLOY_LOCK="$deploy_tmp/deploy.lock" DEPLOY_EXPECTED_SHA=0000000000000000000000000000000000000000 \
    DEPLOY_SOURCE_BRANCH=main "$deploy_repo/scripts/deploy-backend.sh" prod >/dev/null 2>&1; then
    fail "deploy accepted the wrong commit SHA"
  fi
}

test_boot_is_bash32_safe_and_uses_shared_lock() {
  local boot_repo="$TMP_ROOT/boot-repo"
  local active_repo="$TMP_ROOT/active-release"
  local boot_lock="$TMP_ROOT/boot.lock"
  mkdir -p "$boot_repo/scripts" "$active_repo" "$TEST_HOME/Library/Logs"
  cp "$ROOT/scripts/clinic-backend-boot.sh" "$boot_repo/scripts/clinic-backend-boot.sh"
  printf '%s\n' 'services: {}' > "$active_repo/docker-compose.yml"
  printf '%s\n' \
    'APP_ENV=production' \
    'DATABASE_URL=postgresql://tester:secret@db.example.test:5432/clinic_test' > "$boot_repo/.env.prod"
  printf 'source=%s\nenv=%s\n' "$active_repo" "$boot_repo/.env.prod" > "$boot_repo/.active-state-prod"

  HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" CLINIC_PATH_PREFIX="$FAKE_BIN" \
    CLINIC_DEPLOY_LOCK="$boot_lock" \
    /bin/bash "$boot_repo/scripts/clinic-backend-boot.sh" "$boot_repo"
  if ! grep -q 'compose up -d OK' "$TEST_HOME/Library/Logs/clinic-backend-boot.log"; then
    sed -n '1,120p' "$TEST_HOME/Library/Logs/clinic-backend-boot.log" >&2
    fail "boot script did not use the control repo env with the active release"
  fi

  mkdir "$boot_lock"
  HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" CLINIC_PATH_PREFIX="$FAKE_BIN" \
    CLINIC_DEPLOY_LOCK="$boot_lock" \
    /bin/bash "$boot_repo/scripts/clinic-backend-boot.sh" "$boot_repo"
  rmdir "$boot_lock"
  grep -q 'deployment/self-heal already active' "$TEST_HOME/Library/Logs/clinic-backend-boot.log" || \
    fail "boot script did not honor the shared deploy lock"
}

test_backup_rejects_failed_dump
test_backup_rejects_structurally_incomplete_dump
test_backup_creates_verified_archive
test_restore_is_atomic_and_explicit
test_compose_requires_explicit_runtime_env
test_deploy_is_pinned_and_serialized
test_deploy_exact_sha_smoke
test_boot_is_bash32_safe_and_uses_shared_lock
echo "infra safety smoke tests: PASS"
