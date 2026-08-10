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

# `stat` has two incompatible dialects, and the naive BSD-first form does not
# merely fail on Linux — it answers wrongly. GNU's -f is --file-system, so
# `stat -f '%Lp' path` treats the format as a second FILE: it errors on that
# one, prints the filesystem block for path, and exits 1. The `||` fallback
# then appends the real mode, and the caller compares a six-line dump against
# "600". Ask GNU first instead: BSD stat has no -c at all, so it rejects the
# option outright and prints nothing before the fallback runs.
file_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"
}

backup_test_env() {
  local lock_path="${CLINIC_BACKUP_LOCK:-$TMP_ROOT/backup.lock}"
  HOME="$TEST_HOME" \
    PATH="$FAKE_BIN:/usr/bin:/bin" \
    PG_DUMP_BIN="$FAKE_BIN/pg_dump" \
    BACKUP_MIN_ARCHIVE_BYTES=1 \
    BACKUP_ENV_FILE="$TEST_ENV" \
    CLINIC_BACKUP_LOCK="$lock_path" \
    FAKE_PG_DUMP_ONCE="${FAKE_PG_DUMP_ONCE:-}" \
    FAKE_PG_DUMP_STARTED="${FAKE_PG_DUMP_STARTED:-}" \
    FAKE_PG_DUMP_RELEASE="${FAKE_PG_DUMP_RELEASE:-}" \
    "$ROOT/scripts/backup-db.sh"
}

make_pg_dump() {
  local mode="$1"
  if [ "$mode" = "fail" ]; then
    printf '%s\n' '#!/bin/bash' 'exit 42' > "$FAKE_BIN/pg_dump"
  elif [ "$mode" = "slow" ]; then
    cat > "$FAKE_BIN/pg_dump" <<'PG_DUMP'
#!/bin/bash
set -eu
if [ "${1:-}" = "--version" ]; then
  echo "pg_dump (PostgreSQL) test"
  exit 0
fi
for arg in "$@"; do
  if [ "$arg" = "--table=auth.users" ]; then
    echo "COPY auth.users (instance_id, id, aud) FROM stdin;"
    printf '%s\t%s\t%s\n' "00000000-0000-0000-0000-000000000000" \
      "cf7ad02d-9788-4dfe-9296-9b0ea52c8a54" "authenticated"
    echo "\\."
    exit 0
  fi
done
if mkdir "${FAKE_PG_DUMP_ONCE:?}" 2>/dev/null; then
  touch "${FAKE_PG_DUMP_STARTED:?}"
  for _ in $(seq 1 200); do
    [ -f "${FAKE_PG_DUMP_RELEASE:?}" ] && break
    sleep 0.05
  done
  [ -f "$FAKE_PG_DUMP_RELEASE" ] || exit 91
fi
echo "-- PostgreSQL database dump"
# Same preamble as the `ok` fake: every archive this suite publishes has to look
# like a real pg_dump, or a later assertion picks the odd one out and fails for
# a reason that has nothing to do with what it is testing.
echo "SELECT pg_catalog.set_config('search_path', '', false);"
echo "CREATE SCHEMA public;"
echo "CREATE TABLE public.patient (id uuid);"
echo "CREATE TABLE public.appointment (id uuid);"
echo "-- PostgreSQL database dump complete"
PG_DUMP
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
      '# The auth companion is a second invocation with --table=auth.users.' \
      '# Model it, or the fake answers the auth dump with a public one.' \
      'for arg in "$@"; do' \
      '  if [ "$arg" = "--table=auth.users" ]; then' \
      '    echo "COPY auth.users (instance_id, id, aud) FROM stdin;"' \
      '    echo "00000000-0000-0000-0000-000000000000\tcf7ad02d-9788-4dfe-9296-9b0ea52c8a54\tauthenticated"' \
      '    echo "\\\\."' \
      '    exit 0' \
      '  fi' \
      'done' \
      'echo "-- PostgreSQL database dump"' \
      'echo "CREATE TABLE public.patient (id uuid);"' \
      'echo "-- PostgreSQL database dump complete"' > "$FAKE_BIN/pg_dump"
  else
    printf '%s\n' \
      '#!/bin/bash' \
      '# The auth companion is a second invocation with --table=auth.users.' \
      '# Model it, or the fake answers the auth dump with a public one.' \
      'for arg in "$@"; do' \
      '  if [ "$arg" = "--table=auth.users" ]; then' \
      '    echo "COPY auth.users (instance_id, id, aud) FROM stdin;"' \
      '    echo "00000000-0000-0000-0000-000000000000\tcf7ad02d-9788-4dfe-9296-9b0ea52c8a54\tauthenticated"' \
      '    echo "\\\\."' \
      '    exit 0' \
      '  fi' \
      'done' \
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
  if backup_test_env; then
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
  if backup_test_env; then
    fail "backup accepted a failed pg_dump"
  fi
  if find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' -type f 2>/dev/null | grep -q .; then
    fail "backup left an archive after pg_dump failure"
  fi
}

test_backup_includes_media_files() {
  # ẢNH SIÊU ÂM KHÔNG NẰM TRONG pg_dump, và cho tới 08/08/2026 chúng không nằm
  # trong bản sao lưu nào cả — `grep media` trong cả bốn script đều rỗng. Khôi
  # phục xong sẽ ra một phòng khám đủ bệnh án mà mọi phiếu siêu âm trỏ tới tệp
  # không còn tồn tại: image_refs đầy khoá, đĩa trống, không lỗi nào báo.
  make_pg_dump ok
  local media_root="$TMP_ROOT/media-src"
  mkdir -p "$media_root/test/clinic-1/ultrasound/us-1"
  printf 'ANH-SIEU-AM-GIA' > "$media_root/test/clinic-1/ultrasound/us-1/a.jpg"
  # Tệp đang ghi dở phải bị BỎ: media_service ghi .tmp rồi mới đổi tên, và cất
  # lại một tệp hỏng là cất lại đúng thứ nó tránh.
  printf 'GHI-DO' > "$media_root/test/clinic-1/ultrasound/us-1/b.jpg.tmp"

  local media_env="$TMP_ROOT/media.env"
  { cat "$TEST_ENV"; echo "MEDIA_DIR=$media_root"; } > "$media_env"

  rm -rf "$TEST_HOME/backups/clinicai"
  HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin"     PG_DUMP_BIN="$FAKE_BIN/pg_dump" BACKUP_MIN_ARCHIVE_BYTES=1     BACKUP_ENV_FILE="$media_env"     CLINIC_BACKUP_LOCK="$TMP_ROOT/backup-media.lock"     "$ROOT/scripts/backup-db.sh" || fail "backup failed with media present"

  local archive media
  archive="$(find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' ! -name '*_auth.sql.gz' -type f | head -1)"
  [ -n "$archive" ] || fail "backup did not create an archive"
  media="${archive%.sql.gz}_media.tar.gz"
  [ -f "$media" ] || fail "backup did not create the media artifact"
  gzip -t "$media" || fail "media artifact failed gzip validation"
  tar -tzf "$media" | grep -q 'a\.jpg' || fail "media artifact does not contain the image"
  # `A && fail` LÀ CÁI BẪY dưới `set -e`: khi grep KHÔNG tìm thấy gì (đúng cái
  # ta muốn), câu lệnh trả 1 và bash 5 trên CI giết cả suite ngay đó — trong khi
  # bash 3.2 trên macOS bỏ qua. Chạy được ở máy, đỏ trên CI, và thông báo lỗi
  # nói về một chuyện khác hẳn. Viết thành `if` là hết.
  if tar -tzf "$media" | grep -q '\.tmp$'; then
    fail "media artifact kept a half-written .tmp file"
  fi
  grep -q '^media_sha256=..*' "${archive}.manifest" ||     fail "manifest does not record the media checksum"
  grep -qx 'media_file_count=1' "${archive}.manifest" ||     fail "manifest does not record how many media files were archived"

  # Bản khôi phục phải mở ra đúng tệp ấy — "có tệp tar" chưa phải là "khôi phục được".
  local out="$TMP_ROOT/media-restored"
  mkdir -p "$out"
  tar -C "$out" -xzf "$media"
  [ -f "$out/clinic-1/ultrasound/us-1/a.jpg" ] ||     fail "media artifact does not restore to the original layout"
  grep -q 'ANH-SIEU-AM-GIA' "$out/clinic-1/ultrasound/us-1/a.jpg" ||     fail "restored media file does not match the original bytes"

  # Và người kiểm phải BẮT được khi tệp media bị hỏng — một tar hỏng vẫn là một
  # tệp có mặt trong thư mục, và "có bản sao lưu" là câu đọc từ danh sách tệp.
  printf 'RAC' >> "$media"
  if HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin"        CLINIC_BACKUP_DIR="$TEST_HOME/backups/clinicai"        "$ROOT/scripts/verify-backup.sh" >/dev/null 2>&1; then
    fail "verifier accepted a corrupted media artifact"
  fi
}

test_backup_creates_verified_archive() {
  make_pg_dump ok
  backup_test_env
  archive="$(find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' ! -name '*_auth.sql.gz' -type f | head -1)"
  [ -n "$archive" ] || fail "backup did not create an archive"
  gzip -t "$archive" || fail "backup archive failed gzip validation"
  gzip -cd "$archive" | grep -q 'PostgreSQL database dump complete' || \
    fail "backup archive does not contain a complete dump marker"
  [ -f "${archive}.manifest" ] || fail "backup did not create a scope/checksum manifest"
  grep -qx 'complete_supabase_dr=false' "${archive}.manifest" || \
    fail "backup manifest incorrectly presents public data as full Supabase DR"
  # The public dump alone cannot be restored: staff.auth_user_id references
  # auth.users. Publishing it without the companion produces an archive that
  # passes every integrity check and still fails a real restore.
  auth_archive="${archive%.sql.gz}_auth.sql.gz"
  [ -f "$auth_archive" ] || fail "backup did not create the auth companion artifact"
  gzip -t "$auth_archive" || fail "auth companion failed gzip validation"
  gzip -cd "$auth_archive" | grep -q 'COPY auth\.users' || \
    fail "auth companion does not contain auth.users"
  grep -qx 'restore_order=auth-then-public' "${archive}.manifest" || \
    fail "manifest does not record the restore order"
  status_file="$TEST_HOME/.clinicai/ops/test/backup-status.json"
  [ -f "$status_file" ] || fail "backup did not publish sanitized Ops metadata"
  grep -q '"verified": true' "$status_file" || fail "Ops backup metadata is not verified"
  if grep -Eq 'DATABASE_URL|archive_path|db\.example|s@cret' "$status_file"; then
    fail "Ops backup metadata leaked a path or secret"
  fi
}

test_backup_command_preflight_is_explicit() {
  missing_pg_dump="$TMP_ROOT/bin/pg_dump-missing"
  if HOME="$TEST_HOME" PATH="$FAKE_BIN:/usr/bin:/bin" \
    PG_DUMP_BIN="$missing_pg_dump" BACKUP_MIN_ARCHIVE_BYTES=1 \
    BACKUP_ENV_FILE="$TEST_ENV" "$ROOT/scripts/backup-db.sh"; then
    fail "backup ignored an invalid explicit PG_DUMP_BIN"
  fi
  grep -q 'configured pg_dump is not executable' \
    "$TEST_HOME/Library/Logs/clinicai-backup.log" || \
    fail "backup preflight did not report the invalid pg_dump command"

  grep -Fq '/opt/homebrew/opt/libpq/bin' "$ROOT/scripts/backup-db.sh" || \
    fail "backup command PATH does not include Homebrew libpq"
  grep -Fq '/opt/homebrew/opt/postgresql@17/bin' "$ROOT/scripts/backup-db.sh" || \
    fail "backup command PATH does not include Homebrew PostgreSQL 17"
  grep -Fq '/opt/homebrew/opt/libpq/bin' \
    "$ROOT/scripts/launchdaemons/com.dr4women.db-backup.plist" || \
    fail "LaunchDaemon PATH does not include Homebrew libpq"
}

test_backup_rejects_small_archive_before_publish() {
  local small_home="$TMP_ROOT/small-home"
  mkdir -p "$small_home"
  make_pg_dump ok
  if HOME="$small_home" PATH="$FAKE_BIN:/usr/bin:/bin" \
    PG_DUMP_BIN="$FAKE_BIN/pg_dump" BACKUP_MIN_ARCHIVE_BYTES=999999999 \
    BACKUP_ENV_FILE="$TEST_ENV" "$ROOT/scripts/backup-db.sh"; then
    fail "backup published an archive below the configured minimum size"
  fi
  if find "$small_home/backups/clinicai" -name '*.sql.gz' -type f 2>/dev/null | grep -q .; then
    fail "backup left a published archive after the size preflight failed"
  fi
}

test_backup_verifier_rejects_stale_and_small_artifacts() {
  local archive
  archive="$(find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' ! -name '*_auth.sql.gz' -type f | head -1)"
  [ -n "$archive" ] || fail "no verified archive exists for artifact health tests"

  BACKUP_MIN_ARCHIVE_BYTES=1 BACKUP_MAX_AGE_HOURS=30 \
    "$ROOT/scripts/verify-backup.sh" "$archive" >/dev/null

  if BACKUP_MIN_ARCHIVE_BYTES=999999999 BACKUP_MAX_AGE_HOURS=30 \
    "$ROOT/scripts/verify-backup.sh" "$archive" >/dev/null 2>&1; then
    fail "backup verifier accepted an implausibly small archive"
  fi

  touch -t 200001010000 "$archive"
  if BACKUP_MIN_ARCHIVE_BYTES=1 BACKUP_MAX_AGE_HOURS=1 \
    "$ROOT/scripts/verify-backup.sh" "$archive" >/dev/null 2>&1; then
    fail "backup verifier accepted a stale archive"
  fi
}

test_backup_lock_rejects_a_concurrent_publisher() {
  local lock_dir="$TMP_ROOT/concurrent-backup.lock"
  local once_dir="$TMP_ROOT/pg-dump-once"
  local started_file="$TMP_ROOT/pg-dump-started"
  local release_file="$TMP_ROOT/pg-dump-release"
  local first_output="$TMP_ROOT/backup-first.out"
  local second_output="$TMP_ROOT/backup-second.out"
  local first_pid second_rc archive

  make_pg_dump slow
  CLINIC_BACKUP_LOCK="$lock_dir" \
    FAKE_PG_DUMP_ONCE="$once_dir" \
    FAKE_PG_DUMP_STARTED="$started_file" \
    FAKE_PG_DUMP_RELEASE="$release_file" \
    backup_test_env >"$first_output" 2>&1 &
  first_pid=$!

  for _ in $(seq 1 100); do
    [ -f "$started_file" ] && break
    sleep 0.05
  done
  [ -f "$started_file" ] || {
    touch "$release_file"
    wait "$first_pid" 2>/dev/null || true
    fail "first backup never reached pg_dump"
  }

  second_rc=0
  CLINIC_BACKUP_LOCK="$lock_dir" \
    FAKE_PG_DUMP_ONCE="$once_dir" \
    FAKE_PG_DUMP_STARTED="$started_file" \
    FAKE_PG_DUMP_RELEASE="$release_file" \
    backup_test_env >"$second_output" 2>&1 || second_rc=$?

  touch "$release_file"
  wait "$first_pid" || fail "lock-owning backup failed: $(tail -3 "$first_output" | tr '\n' ' ')"

  [ "$second_rc" -ne 0 ] || \
    fail "backup accepted a second publisher while the first still held the lock"
  [ ! -d "$lock_dir" ] || fail "backup lock was not released after completion"
  grep -q 'another backup is already active' \
    "$TEST_HOME/Library/Logs/clinicai-backup.log" || \
    fail "concurrent backup rejection was not logged"

  archive="$(find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' ! -name '*_auth.sql.gz' \
    -type f | LC_ALL=C sort | tail -1)"
  [ -n "$archive" ] || fail "lock-owning backup did not publish an artifact"
  BACKUP_MIN_ARCHIVE_BYTES=1 BACKUP_MAX_AGE_HOURS=1 \
    "$ROOT/scripts/verify-backup.sh" "$archive" >/dev/null
}

test_restore_is_atomic_and_explicit() {
  make_psql
  archive="$(find "$TEST_HOME/backups/clinicai" -name '*.sql.gz' ! -name '*_auth.sql.gz' -type f | head -1)"
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

test_uptime_kuma_setup_is_fail_closed() {
  local setup="$ROOT/scripts/setup-uptime-kuma.sh"
  [ -x "$setup" ] || fail "Uptime Kuma setup script is missing or not executable"
  grep -Fq 'http://api:8000/health/db' "$setup" || \
    fail "Uptime Kuma must monitor database readiness, not process liveness"
  grep -Fq 'KUMA_PASS:?set KUMA_PASS' "$setup" || \
    fail "Uptime Kuma setup must require an explicit admin password"
  if grep -Fq 'clinicai-kuma-2026' "$setup"; then
    fail "Uptime Kuma setup contains a default admin password"
  fi
  if grep -Fq '`docker cp`' "$setup"; then
    fail "Uptime Kuma setup executes backticks while rendering its heredoc"
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
  grep -Fq 'ref: ${{ github.event.workflow_run.head_sha }}' "$ROOT/.github/workflows/cd.yml" || \
    fail "CD does not checkout the triggering commit"
  grep -Fq 'workflow_run:' "$ROOT/.github/workflows/cd.yml" || \
    fail "CD is not gated on completion of CI"
  grep -Fq "github.event.workflow_run.conclusion == 'success'" "$ROOT/.github/workflows/cd.yml" || \
    fail "CD does not require a successful CI conclusion"
  grep -Fq "github.event.workflow_run.event == 'push'" "$ROOT/.github/workflows/cd.yml" || \
    fail "CD can be triggered by an untrusted pull request workflow"
  grep -Fq 'github.event.workflow_run.head_repository.full_name == github.repository' \
    "$ROOT/.github/workflows/cd.yml" || \
    fail "CD does not require the completed CI run to belong to this repository"
  grep -Fq 'github.event.workflow_run.head_branch' "$ROOT/.github/workflows/cd.yml" || \
    fail "CD does not select the environment from the CI source branch"
  grep -Fq 'id: freshness' "$ROOT/.github/workflows/cd.yml" || \
    fail "CD does not compare a completed CI SHA with the current branch head"
  grep -Fq 'steps.freshness.outputs.deploy' "$ROOT/.github/workflows/cd.yml" || \
    fail "CD checkout/deploy steps are not gated by branch-head freshness"
  if grep -Eq '^  push:' "$ROOT/.github/workflows/cd.yml"; then
    fail "CD still deploys directly on push before CI succeeds"
  fi

  grep -Fq './scripts/tests/test-infra-safety.sh' "$ROOT/.github/workflows/ci.yml" || \
    fail "CI does not execute the infrastructure safety smoke tests"

  # A restore drill that nobody is told to run decays into a file in scripts/.
  # It found that the backup could not be restored at all, so the runbook has to
  # keep telling people to run it.
  [ -x "$ROOT/scripts/restore-drill.sh" ] || fail "restore drill is missing or not executable"
  grep -Fq './scripts/restore-drill.sh' "$ROOT/docs/OPS-RUNBOOK.md" || \
    fail "runbook does not tell anyone to run the restore drill"
  grep -Fq 'restore_order=auth-then-public' "$ROOT/scripts/backup-db.sh" || \
    fail "backup no longer records the restore order the drill depends on"
  for workflow in ci.yml cd.yml; do
    grep -Fq 'contents: read' "$ROOT/.github/workflows/$workflow" || \
      fail "$workflow does not use least-privilege repository contents access"
  done
}

test_deploy_precreates_bind_dirs() {
  # Docker tự tạo thư mục ổ bind bằng quyền DAEMON — tức root — khi nó chưa tồn
  # tại. Container thì chạy bằng appuser (uid 1000). Đo trên bản thật 08/08:
  # `touch /var/lib/clinicai/media/x` → Permission denied. Backend không ghi
  # nổi một tấm ảnh siêu âm nào suốt từ ngày dựng, và hỏng im lặng vì chưa ai
  # upload. Deploy phải tạo trước, bằng chính người deploy.
  local deploy="$ROOT/scripts/deploy-backend.sh"
  grep -Fq 'mkdir -p "$d"' "$deploy" ||     fail "deploy does not pre-create the bind-mount directories"
  grep -Fq 'MEDIA_BIND' "$deploy" ||     fail "deploy does not resolve MEDIA_DIR before compose up"
  # Phải chạy TRƯỚC `up -d`, không thì Docker đã tạo bằng root mất rồi.
  local mkdir_line up_line
  mkdir_line=$(grep -n 'mkdir -p "$d"' "$deploy" | head -1 | cut -d: -f1)
  up_line=$(grep -n '"${COMPOSE\[@\]}" up -d' "$deploy" | head -1 | cut -d: -f1)
  [ -n "$mkdir_line" ] && [ -n "$up_line" ] && [ "$mkdir_line" -lt "$up_line" ] ||     fail "bind directories are created after compose up (too late — Docker already made them root-owned)"
}

test_deploy_rolls_back_when_initial_up_fails() {
  local deploy_repo="$TMP_ROOT/deploy-rollback-repo"
  local previous_repo="$TMP_ROOT/deploy-previous-release"
  local deploy_secrets="$TMP_ROOT/deploy-rollback-secrets"
  local deploy_tmp="$TMP_ROOT/deploy-rollback-tmp"
  local docker_log="$TMP_ROOT/deploy-docker.log"
  local deploy_output="$TMP_ROOT/deploy-rollback.out"
  local previous_env="$deploy_secrets/previous.env"
  local sha

  mkdir -p "$deploy_repo/scripts" "$previous_repo" "$deploy_secrets" "$deploy_tmp"
  cp "$ROOT/scripts/deploy-backend.sh" "$deploy_repo/scripts/deploy-backend.sh"
  chmod +x "$deploy_repo/scripts/deploy-backend.sh"
  printf '%s\n' 'services: {}' > "$deploy_repo/docker-compose.yml"
  printf '%s\n' 'services: {}' > "$previous_repo/docker-compose.yml"
  touch "$deploy_repo/.new-release-marker" "$previous_repo/.previous-release-marker"
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
COMPOSE_PROFILES=
ENV
  cp "$deploy_secrets/.env.prod" "$previous_env"
  printf 'source=%s\nenv=%s\n' "$previous_repo" "$previous_env" \
    > "$deploy_secrets/.active-state-prod"

  cat > "$FAKE_BIN/docker" <<'DOCKER'
#!/bin/bash
set -eu
printf '%s|%s\n' "$PWD" "$*" >> "${FAKE_DOCKER_LOG:?}"
if [ "${1:-}" = "image" ] && [ "${2:-}" = "inspect" ]; then
  case "$*" in
    *clinicai-api:prod*) echo "sha256:old-api" ;;
    *clinicai-dashboard:prod*) echo "sha256:old-dashboard" ;;
    *) exit 1 ;;
  esac
  exit 0
fi
if [ "${1:-}" = "tag" ]; then
  exit 0
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
  if [ "$arg" = "up" ]; then
    if [ -f "$PWD/.new-release-marker" ]; then
      exit 42
    fi
    if [ -f "$PWD/.previous-release-marker" ]; then
      exit "${FAKE_ROLLBACK_UP_FAIL:-0}"
    fi
  fi
done
exit 0
DOCKER
  chmod +x "$FAKE_BIN/docker"

  git -C "$deploy_repo" init -q
  git -C "$deploy_repo" add .new-release-marker docker-compose.yml scripts/deploy-backend.sh
  git -C "$deploy_repo" -c user.name=Test -c user.email=test@example.test commit -qm init
  sha="$(git -C "$deploy_repo" rev-parse HEAD)"

  if HOME="$TEST_HOME" TMPDIR="$deploy_tmp" PATH="$FAKE_BIN:/usr/bin:/bin" \
    CLINIC_PATH_PREFIX="$FAKE_BIN" CLINIC_ENV_DIR="$deploy_secrets" \
    CLINIC_DEPLOY_LOCK="$deploy_tmp/deploy.lock" DEPLOY_EXPECTED_SHA="$sha" \
    DEPLOY_SOURCE_REF=main FAKE_DOCKER_LOG="$docker_log" \
    "$deploy_repo/scripts/deploy-backend.sh" prod >"$deploy_output" 2>&1; then
    fail "deploy reported success after the new compose up failed"
  fi
  grep -q 'deploy-previous-release|.* up -d' "$docker_log" || \
    fail "deploy did not run compose up from the previous release"
  grep -q 'rollback health verified' "$deploy_output" || \
    fail "deploy did not health-check a successful rollback"
  grep -q 'tag sha256:old-api clinicai-api:prod' "$docker_log" || \
    fail "deploy did not restore the previous API image tag"
  grep -q 'tag sha256:old-dashboard clinicai-dashboard:prod' "$docker_log" || \
    fail "deploy did not restore the previous dashboard image tag"
  grep -Fxq "source=$previous_repo" "$deploy_secrets/.active-state-prod" || \
    fail "failed deployment replaced the previous active release state"

  : > "$docker_log"
  if HOME="$TEST_HOME" TMPDIR="$deploy_tmp" PATH="$FAKE_BIN:/usr/bin:/bin" \
    CLINIC_PATH_PREFIX="$FAKE_BIN" CLINIC_ENV_DIR="$deploy_secrets" \
    CLINIC_DEPLOY_LOCK="$deploy_tmp/deploy.lock" DEPLOY_EXPECTED_SHA="$sha" \
    DEPLOY_SOURCE_REF=main FAKE_DOCKER_LOG="$docker_log" \
    FAKE_ROLLBACK_UP_FAIL=43 \
    "$deploy_repo/scripts/deploy-backend.sh" prod >"$deploy_output" 2>&1; then
    fail "deploy reported success when both new and rollback compose up failed"
  fi
  grep -q 'deploy-previous-release|.* up -d' "$docker_log" || \
    fail "deploy did not attempt the rollback compose up"
  grep -q 'rollback compose up failed' "$deploy_output" || \
    fail "set -e cut off controlled handling of a failed rollback compose up"
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
    DEPLOY_SOURCE_REF=main "$deploy_repo/scripts/deploy-backend.sh" prod >/dev/null
  [ ! -e "$deploy_repo/.env" ] || fail "deploy copied secrets into a shared .env"
  [ -f "$deploy_secrets/.active-state-prod" ] || fail "deploy did not atomically record active release state"
  active_env="$(grep -E '^env=' "$deploy_secrets/.active-state-prod" | cut -d= -f2-)"
  [ -f "$active_env" ] || fail "active env revision does not exist"
  [ "$(file_mode "$active_env")" = "600" ] || \
    fail "active env revision is not mode 600"

  if HOME="$TEST_HOME" TMPDIR="$deploy_tmp" PATH="$FAKE_BIN:/usr/bin:/bin" \
    CLINIC_PATH_PREFIX="$FAKE_BIN" CLINIC_ENV_DIR="$deploy_secrets" \
    CLINIC_DEPLOY_LOCK="$deploy_tmp/deploy.lock" DEPLOY_EXPECTED_SHA=0000000000000000000000000000000000000000 \
    DEPLOY_SOURCE_REF=main "$deploy_repo/scripts/deploy-backend.sh" prod >/dev/null 2>&1; then
    fail "deploy accepted the wrong commit SHA"
  fi

  # Trunk-based moved this check from an equality test on a branch name to a
  # pattern test on a ref, and a pattern is much easier to get subtly wrong.
  # Both directions matter: prod must not accept a staging tag, and staging must
  # not accept main. The second one is what stops "just deploy staging quickly"
  # from putting untagged trunk on the staging stack.
  local ref_output="$deploy_tmp/wrong-ref.log"
  cp "$deploy_secrets/.env.prod" "$deploy_secrets/.env.staging"

  # The assertion is on the message, not just on a non-zero exit. Every later
  # gate in this script also exits non-zero, so "it failed" would keep passing
  # even if the ref check were deleted outright.
  local pair
  for pair in "prod staging-2026-01-01" "staging main"; do
    set -- $pair
    if HOME="$TEST_HOME" TMPDIR="$deploy_tmp" PATH="$FAKE_BIN:/usr/bin:/bin" \
      CLINIC_PATH_PREFIX="$FAKE_BIN" CLINIC_ENV_DIR="$deploy_secrets" \
      CLINIC_DEPLOY_LOCK="$deploy_tmp/deploy.lock" DEPLOY_EXPECTED_SHA="$sha" \
      DEPLOY_SOURCE_REF="$2" \
      "$deploy_repo/scripts/deploy-backend.sh" "$1" >"$ref_output" 2>&1; then
      fail "$1 accepted ref $2"
    fi
    grep -q "must deploy from" "$ref_output" || \
      fail "$1 rejected ref $2, but not because of the ref: $(cat "$ref_output")"
  done

  rm -f "$deploy_secrets/.env.staging"

  printf '%s\n' \
    'COMPOSE_PROFILES=workers' \
    'RABBITMQ_URL=' \
    'RABBITMQ_PASSWORD=' >> "$deploy_secrets/.env.prod"
  if HOME="$TEST_HOME" TMPDIR="$deploy_tmp" PATH="$FAKE_BIN:/usr/bin:/bin" \
    CLINIC_PATH_PREFIX="$FAKE_BIN" CLINIC_ENV_DIR="$deploy_secrets" \
    CLINIC_DEPLOY_LOCK="$deploy_tmp/deploy.lock" DEPLOY_EXPECTED_SHA="$sha" \
    DEPLOY_SOURCE_REF=main "$deploy_repo/scripts/deploy-backend.sh" prod >/dev/null 2>&1; then
    fail "workers profile accepted an empty RabbitMQ password/URL"
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

test_compose_has_bounded_runtime_defaults() {
  grep -Fq 'RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-}' "$ROOT/docker-compose.yml" || \
    fail "RabbitMQ still has a default password"
  if grep -Fq 'clinicai_dev_pass' \
      "$ROOT/docker-compose.yml" "$ROOT/.env.example" \
      "$ROOT/.env.prod.example" "$ROOT/.env.staging.example"; then
    fail "RabbitMQ config contains a shared fallback password"
  fi
  grep -Fq 'RabbitMQ password is required when the workers profile is enabled' \
    "$ROOT/docker-compose.yml" || \
    fail "RabbitMQ container does not fail closed when workers are enabled"

  grep -Fq 'x-clinic-service-defaults:' "$ROOT/docker-compose.yml" || \
    fail "compose does not define shared security/logging defaults"
  [ "$(grep -Fc '<<: *clinic-service-defaults' "$ROOT/docker-compose.yml")" -ge 10 ] || \
    fail "not every compose service inherits the security/logging defaults"
  [ "$(grep -Ec '^    mem_limit:' "$ROOT/docker-compose.yml")" -ge 10 ] || \
    fail "not every compose service has a memory limit"
  [ "$(grep -Ec '^    pids_limit:' "$ROOT/docker-compose.yml")" -ge 10 ] || \
    fail "not every compose service has a PID limit"
}

test_compose_renders_every_profile_safely() {
  if ! command -v docker >/dev/null 2>&1 ||
     ! docker compose version >/dev/null 2>&1; then
    echo "SKIP: docker compose is unavailable; CI portability job must run this check"
    return
  fi

  RABBITMQ_PASSWORD= RABBITMQ_URL= CLINIC_ENV_FILE=.env.prod.example \
    docker compose --env-file "$ROOT/.env.prod.example" \
      -f "$ROOT/docker-compose.yml" -p clinicai_infra_test config --quiet

  CLINIC_ENV_FILE=.env.prod.example \
    docker compose --env-file "$ROOT/.env.prod.example" \
      -f "$ROOT/docker-compose.yml" -p clinicai_infra_test \
      --profile '*' config --format json |
    python3 -c '
import json
import sys

services = json.load(sys.stdin)["services"]
expected = {
    "api", "caddy", "cloudflared", "dashboard", "dozzle",
    "notification-relay", "pos-relay", "rabbitmq", "uptime-kuma", "worker",
}
assert set(services) == expected, set(services)
for name, service in services.items():
    assert service.get("mem_limit"), (name, "mem_limit")
    assert service.get("pids_limit"), (name, "pids_limit")
    assert service.get("security_opt") == ["no-new-privileges:true"], (
        name,
        "security_opt",
    )
    assert service.get("logging", {}).get("options") == {
        "max-file": "5",
        "max-size": "10m",
    }, (name, "logging")
'
}

test_repository_hygiene_and_test_doc_are_safe() {
  grep -Fqx '.headroom/' "$ROOT/.gitignore" || \
    fail "local Headroom agent memory is not ignored"
  grep -E 'Mật khẩu phòng khám.*secret manager' \
    "$ROOT/docs/Hướng dẫn test Dashboard.md" >/dev/null || \
    fail "dashboard test guide does not direct testers to the secret manager"
  if grep -E 'Mật khẩu phòng khám' "$ROOT/docs/Hướng dẫn test Dashboard.md" | \
      grep -vq 'secret manager'; then
    fail "dashboard test guide still embeds the clinic password"
  fi
}

test_runbook_installs_the_real_launchdaemon_template() {
  local runbook="$ROOT/docs/OPS-RUNBOOK.md"
  local backend_template="$ROOT/docker/com.dr4women.clinic-backend.plist"

  [ -f "$backend_template" ] || fail "backend LaunchDaemon template is missing"
  grep -Fq 'docker/com.dr4women.clinic-backend.plist' "$runbook" || \
    fail "runbook does not install the real backend LaunchDaemon template"
  if grep -Fq 'scripts/launchdaemons/com.dr4women.clinic-backend.plist' "$runbook"; then
    fail "runbook still names a nonexistent backend LaunchDaemon file"
  fi
  for marker in __USER__ __HOME__ __REPO__; do
    grep -Fq "$marker" "$runbook" || \
      fail "runbook does not render backend LaunchDaemon marker $marker"
  done
  grep -Fq 'plutil -lint "$BACKEND_PLIST"' "$runbook" || \
    fail "runbook does not lint the rendered backend LaunchDaemon"
  grep -Fq 'launchctl bootstrap system' "$runbook" || \
    fail "runbook does not bootstrap LaunchDaemons in the system domain"
  grep -Fq 'launchctl kickstart -k system/com.dr4women.db-backup' "$runbook" || \
    fail "runbook does not run the reinstalled backup daemon immediately"
  if grep -Eq 'sudo launchctl load|clinic-backend\.plist.*2>/dev/null' "$runbook"; then
    fail "runbook still uses deprecated or error-swallowing LaunchDaemon commands"
  fi
}

test_backup_rejects_failed_dump
test_backup_rejects_structurally_incomplete_dump
test_backup_creates_verified_archive
test_backup_command_preflight_is_explicit
test_backup_rejects_small_archive_before_publish
test_backup_lock_rejects_a_concurrent_publisher
test_restore_is_atomic_and_explicit
test_uptime_kuma_setup_is_fail_closed
test_backup_verifier_rejects_stale_and_small_artifacts
test_compose_requires_explicit_runtime_env
test_deploy_is_pinned_and_serialized
test_deploy_precreates_bind_dirs
test_deploy_rolls_back_when_initial_up_fails
test_deploy_exact_sha_smoke
test_boot_is_bash32_safe_and_uses_shared_lock
test_compose_has_bounded_runtime_defaults
test_compose_renders_every_profile_safely
test_repository_hygiene_and_test_doc_are_safe
test_runbook_installs_the_real_launchdaemon_template
# ĐỂ CUỐI CÙNG, CÓ CHỦ Ý: bài này cố ý làm hỏng một tệp media để thử người kiểm.
# Các bài khác lấy "tệp .sql.gz đầu tiên tìm thấy" trong cùng thư mục, nên một
# tệp hỏng còn sót lại là chúng kiểm nhầm bản sao lưu — và báo một lỗi nói về
# chuyện khác hẳn.
test_backup_includes_media_files
echo "infra safety smoke tests: PASS"
