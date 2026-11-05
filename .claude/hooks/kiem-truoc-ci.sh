#!/usr/bin/env bash
# PreToolUse (Bash): trước khi chạy scripts/ci-may.sh, chạy các bước NHANH của job
# backend (ruff, mypy, tenant-scope, bản đồ code). Đỏ thì chặn CI — sửa trước,
# khỏi mất một lượt CI ~15 phút chỉ vì quên `ban-do-code.py` hay mypy (05/11/2026:
# hai lượt CI đỏ oan như vậy trong một buổi).
#
# - Chỉ bắt lệnh có `ci-may.sh`; mọi lệnh khác thoát 0 ngay.
# - Thoát 2 + stderr = Claude thấy lỗi, CI không chạy. Thiếu .venv/công cụ → thoát 0
#   (để ci-may.sh tự báo), hook không bao giờ chặn vì chính nó hỏng.
# - Bỏ qua: đặt BO_KIEM_TRUOC_CI=1 trong lệnh (chỉ khi Tuyền cho phép, ghi lý do).
set -u

cmd="$(python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print((d.get("tool_input") or {}).get("command",""))
except Exception:
    print("")' 2>/dev/null)"

case "$cmd" in
  *ci-may.sh*) ;;
  *) exit 0 ;;
esac
case "$cmd" in
  *BO_KIEM_TRUOC_CI=1*|*--help*) exit 0 ;;
esac

root="$(git rev-parse --show-toplevel 2>/dev/null)" || root="${CLAUDE_PROJECT_DIR:-}"
[ -n "$root" ] && [ -f "$root/scripts/ci-may.sh" ] || exit 0
cd "$root" || exit 0
V="$root/.venv/bin"
[ -x "$V/ruff" ] && [ -x "$V/mypy" ] || exit 0

loi=""
chay() {  # chay "<tên bước>" lệnh...
  local ten="$1"; shift
  local out
  if ! out="$("$@" 2>&1)"; then
    loi+=$'\n'"── $ten ĐỎ:"$'\n'"$(printf '%s\n' "$out" | tail -25)"
  fi
}

chay "ruff check src/"          "$V/ruff" check --quiet --output-format concise src/
chay "ruff format --check src/" "$V/ruff" format --check --quiet src/
chay "bản đồ code (--kiem)"     python3 scripts/ban-do-code.py --kiem
[ -f scripts/tests/tenant-scope-audit.py ] && \
  chay "tenant-scope-audit"     python3 scripts/tests/tenant-scope-audit.py --check
chay "mypy src/"                "$V/mypy" src/

if [ -n "$loi" ]; then
  {
    echo "Chưa chạy ci-may.sh: bước kiểm nhanh trước CI đỏ. Sửa, commit, rồi chạy CI lại."
    echo "(bản đồ lệch → python3 scripts/ban-do-code.py rồi commit docs/BAN-DO-CODE.md)"
    printf '%s\n' "$loi"
  } >&2
  exit 2
fi

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Chưa chạy ci-may.sh: còn thay đổi CHƯA commit. CI phải chạy trên một SHA đã commit (luật chỉ merge SHA đã CI xanh)." >&2
  exit 2
fi
exit 0
