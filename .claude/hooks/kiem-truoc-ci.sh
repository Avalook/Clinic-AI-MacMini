#!/usr/bin/env bash
# PreToolUse (Bash): trước khi CHẠY scripts/ci-may.sh, chạy các bước NHANH của job
# backend (ruff, mypy, tenant-scope, bản đồ code). Đỏ thì chặn CI — sửa trước,
# khỏi mất một lượt CI ~15 phút chỉ vì quên `ban-do-code.py` hay mypy (05/11/2026:
# hai lượt CI đỏ oan như vậy trong một buổi).
#
# - Chỉ bắt khi ci-may.sh là LỆNH được chạy (đầu một đoạn lệnh, sau ; && || | ( hoặc
#   sau nohup/time/env/bash/sh/exec và các gán biến). `grep … ci-may.sh`, `cat`,
#   `sed -n`, `git diff scripts/ci-may.sh` đều KHÔNG bị bắt (bản đầu bắt nhầm — agent
#   soát #… 05/11).
# - Thoát 2 + stderr = Claude thấy lỗi, CI không chạy. Thiếu .venv/công cụ → thoát 0
#   (để ci-may.sh tự báo), hook không bao giờ chặn vì chính nó hỏng.
# - Bỏ qua: gán BO_KIEM_TRUOC_CI=1 ngay trước lệnh (chỉ khi Tuyền cho phép, ghi lý do).
set -u

quyet="$(python3 -c '
import json, re, shlex, sys
try:
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "")
except Exception:
    print("BO"); sys.exit()
VO = {"nohup", "time", "env", "bash", "sh", "exec", "command", "caffeinate"}
chay = bo_qua = False
for doan in re.split(r"&&|\|\||[;|&\n()]", cmd):
    try:
        tu = shlex.split(doan, posix=True)
    except ValueError:
        tu = doan.split()
    sau_vo = False
    while tu:
        t = tu[0]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
            bo_qua = bo_qua or t.startswith("BO_KIEM_TRUOC_CI=1")
        elif t in VO:
            sau_vo = True
        elif sau_vo and t.startswith("-"):
            pass
        else:
            break
        tu = tu[1:]
    if tu and tu[0].endswith("ci-may.sh") and "--help" not in tu:
        chay = True
print("BO" if (not chay or bo_qua) else "KIEM")
' 2>/dev/null)"

[ "$quyet" = "KIEM" ] || exit 0

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
