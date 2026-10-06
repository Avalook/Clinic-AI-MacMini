#!/usr/bin/env bash
# PostToolUse (Edit|Write|MultiEdit): kiểm ngay file Python vừa sửa bằng đúng
# ruff mà CI dùng, để lỗi lint/định dạng hiện ra tại chỗ thay vì đỏ ở ci-may.sh.
#
# - Phiên bản ruff đọc từ pyproject.toml (CI ghim; ruff trên PATH có thể khác bản
#   và định dạng khác) — chạy qua `uvx`, ~50ms khi đã có cache.
# - Thoát 2 + stderr = Claude đọc được lỗi và sửa tiếp. Thiếu công cụ hay không
#   phải file Python → thoát 0 im lặng: hook không bao giờ được chặn việc sửa.
# - Lỗi kiểu (type) do LSP pyright/typescript báo, không làm ở đây (mypy quá chậm
#   cho mỗi lần sửa — vẫn chạy ở CI).
set -u

file="$(python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print((d.get("tool_input") or {}).get("file_path",""))
except Exception:
    print("")' 2>/dev/null)"

case "$file" in
  *.py) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

root="$(cd "$(dirname "$file")" && git rev-parse --show-toplevel 2>/dev/null)" || exit 0
case "$file" in
  "$root"/src/*|"$root"/scripts/*) ;;
  *) exit 0 ;;
esac

ver="$(sed -n 's/.*"ruff (==\([0-9.]*\))".*/\1/p' "$root/pyproject.toml" 2>/dev/null | head -1)"
if [ -n "$ver" ] && command -v uvx >/dev/null 2>&1; then
  ruff=(uvx --quiet "ruff@$ver")
elif [ -x "$root/.venv/bin/ruff" ]; then
  ruff=("$root/.venv/bin/ruff")
else
  exit 0
fi

cd "$root" || exit 0
out="$("${ruff[@]}" check --quiet --output-format concise "$file" 2>&1)"; rc_check=$?
fmt="$("${ruff[@]}" format --check --quiet "$file" 2>&1)"; rc_fmt=$?

if [ $rc_check -ne 0 ] || [ $rc_fmt -ne 0 ]; then
  {
    echo "ruff ${ver:-?} (bản CI) báo lỗi ở ${file#"$root"/} — sửa trước khi đi tiếp:"
    [ $rc_check -ne 0 ] && echo "$out"
    [ $rc_fmt -ne 0 ] && echo "Chưa đúng định dạng → chạy: uvx ruff@${ver} format ${file#"$root"/}"
  } >&2
  exit 2
fi
exit 0
