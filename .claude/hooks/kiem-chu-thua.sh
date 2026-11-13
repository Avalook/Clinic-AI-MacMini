#!/usr/bin/env bash
# PostToolUse (Edit|Write|MultiEdit): chặn chữ / khung cảnh báo tự thêm vào giao diện.
#
# Vì sao: AI hay tự chèn "⚠ Lưu ý…", khung vàng/đỏ, dòng giải thích kỹ thuật lên
# màn của nhân viên mà không ai giao (Tuyền 13/11/2026). Luật nằm ở
# .claude/rules/giao-dien.md mục 7; hook này là phần máy kiểm.
#
# - Chỉ soi DÒNG MỚI THÊM (diff so với HEAD; tệp chưa track thì cả tệp) trong
#   src/dashboard/app/** và src/dashboard/components/** — không quét code cũ.
# - Cảnh báo ĐƯỢC GIAO thì đặt chú thích `canh-bao-duoc-giao: <trích phiếu>` trên
#   cùng dòng hoặc 2 dòng ngay trên. soat-thiet-ke (Luật 9) đối chiếu mọi chú
#   thích đó với mục "CẢNH BÁO CẦN CÓ" của phiếu giao việc.
# - Thoát 2 + stderr = Claude đọc được và sửa tiếp. Thiếu công cụ → thoát 0 im lặng.
set -u

file="$(python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print((d.get("tool_input") or {}).get("file_path",""))
except Exception:
    print("")' 2>/dev/null)"

case "$file" in
  *.tsx|*.ts) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

root="$(cd "$(dirname "$file")" && git rev-parse --show-toplevel 2>/dev/null)" || exit 0
case "$file" in
  "$root"/src/dashboard/app/*|"$root"/src/dashboard/components/*) ;;
  *) exit 0 ;;
esac
case "$file" in
  *.test.ts|*.test.tsx|*.test.mts) exit 0 ;;
esac
rel="${file#"$root"/}"
cd "$root" || exit 0

if git ls-files --error-unmatch -- "$rel" >/dev/null 2>&1; then
  diff_text="$(git diff -U0 --no-color HEAD -- "$rel" 2>/dev/null)"
  mode=diff
else
  diff_text="$(cat -- "$rel")"
  mode=full
fi
[ -n "$diff_text" ] || exit 0

# read -d '' thay cho py_src="$(cat <<'PY' …)": bash 3.2 của macOS đọc sai heredoc
# nằm trong $(…) khi thân có backtick lẻ → lỗi cú pháp, hook chặn mọi lần sửa .tsx.
IFS= read -r -d '' py_src <<'PY'
import os, re, sys
rel = sys.argv[1]
mode = os.environ.get("MODE", "diff")
MAU = [
    (re.compile("⚠"), "ký hiệu ⚠"),
    (re.compile(r"\b(AlertTriangle|AlertCircle|TriangleAlert|CircleAlert|AlertOctagon)\b"), "icon cảnh báo"),
    (re.compile(r"<CanhBao\w*"), "component CanhBao"),
    (re.compile(r"(>|[\"'`])\s*(Lưu ý|Chú ý|Cảnh báo|Lưu ý:|Warning|Note:)", re.I), "chữ 'Lưu ý / Chú ý / Cảnh báo'"),
    (re.compile(r"\b(bg|border)-(amber|yellow|orange|red)-(50|100|200)\b"), "khung màu vàng/đỏ"),
]
DAU = "canh-bao-duoc-giao"
lines = []
for raw in sys.stdin.read().splitlines():
    if mode == "diff":
        if raw.startswith("+++") or not raw.startswith("+"):
            lines.append(None)  # ngắt: dòng không mới
            continue
        lines.append(raw[1:])
    else:
        lines.append(raw)
bao = []
for i, ln in enumerate(lines):
    if ln is None:
        continue
    gan = [x for x in lines[max(0, i - 2): i + 1] if x]
    if any(DAU in x for x in gan):
        continue
    for re_, ten in MAU:
        if re_.search(ln):
            bao.append(f"  - {ten}: {ln.strip()[:110]}")
            break
if bao:
    print(f"Giao diện: {rel} vừa thêm {len(bao)} dòng có chữ/khung cảnh báo (luật giao-dien.md mục 7):")
    print("\n".join(bao[:10]))
    if len(bao) > 10:
        print(f"  … và {len(bao) - 10} dòng nữa")
    print("→ Phiếu giao việc KHÔNG yêu cầu thì GỠ ĐI. Có yêu cầu thì thêm chú thích")
    print("  `canh-bao-duoc-giao: <trích đúng câu trong phiếu>` ngay trên dòng đó.")
PY
out="$(printf '%s\n' "$diff_text" | MODE="$mode" python3 -c "$py_src" "$rel")"
if [ -n "$out" ]; then
  echo "$out" >&2
  exit 2
fi
exit 0
