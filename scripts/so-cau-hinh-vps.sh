#!/usr/bin/env bash
# In dấu SHA-256 tệp cấu hình repo và lệnh CHỈ ĐỌC để Tuyền chạy trên VPS.
# Script này không kết nối SSH, không đọc .env*, không in nội dung cấu hình.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

repo_files() {
  /usr/bin/git -C "$ROOT" ls-files -z -- \
    'scripts/systemd/clinicai-*' \
    'caddy/Caddyfile' \
    'docker-compose*.yml' \
    'docker-compose*.yaml'
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

if [[ "${1:-}" == "--lenh" ]]; then
  cat <<'REMOTE'
ssh clinic-vps-moi 'sudo bash -s' <<'VPS'
set -euo pipefail
repo=/home/clinicai/clinicai
hash_one() {
  local f="$1" name="$2" sum
  [[ -f "$f" ]] || return 0
  sum="$(sha256sum "$f" | awk '{print $1}')"
  printf '%s  %s\n' "$sum" "$name"
}
for f in /etc/systemd/system/clinicai-*; do
  [[ -f "$f" ]] || continue
  hash_one "$f" "systemd/${f##*/}"
done
for f in "$repo/caddy/Caddyfile" "$repo"/docker-compose*.yml "$repo"/docker-compose*.yaml; do
  [[ -f "$f" ]] || continue
  hash_one "$f" "repo/${f#"$repo"/}"
done
VPS
REMOTE
  exit 0
fi

printf '%s\n' 'SHA-256 cấu hình repo (đối chiếu với kết quả VPS):'
while IFS= read -r -d '' rel; do
  [[ -f "$ROOT/$rel" ]] || continue
  case "$rel" in
    scripts/systemd/clinicai-*) name="systemd/${rel##*/}" ;;
    *) name="repo/$rel" ;;
  esac
  printf '%s  %s\n' "$(sha256 "$ROOT/$rel")" "$name"
done < <(repo_files)
printf '\n%s\n' 'Lệnh để Tuyền tự chạy trên VPS (script này không SSH):'
printf '%s\n' '  scripts/so-cau-hinh-vps.sh --lenh'
