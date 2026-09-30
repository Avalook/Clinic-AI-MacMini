#!/usr/bin/env bash
# Bộ eval vàng — flow sống còn, chạy nhanh, không cần DB/dịch vụ ngoài.
# Danh sách + lý do: docs/eval-vang.md. Dùng bởi lệnh /nghiem-thu.
#   bash scripts/kiem-vang.sh          # backend
#   bash scripts/kiem-vang.sh --full   # kèm frontend (tsc + eslint)
set -uo pipefail
cd "$(dirname "$0")/.."

VANG=(
  src/tests/test_booking_service.py
  src/tests/unit/test_booking_override_minutes.py
  src/tests/unit/test_capacity_cell_state.py
  src/tests/services/test_capacity_roster_gate.py
  src/tests/services/test_capacity_quote_params.py
  src/tests/services/test_slot_hold.py
  src/tests/test_queue_order.py
  src/tests/test_no_queue_rule_in_dashboard.py
  src/tests/test_identity.py
  src/tests/test_api_auth.py
  src/tests/unit/test_auth_service.py
  src/tests/test_me_contract.py
  src/tests/test_vai_man_hinh.py
  src/tests/test_nav_role_drift.py
  src/tests/test_tenant_scope_audit.py
  src/tests/test_payment_service.py
  src/tests/services/test_checkout_blockers.py
  src/tests/test_trang_thai_luot_kham_khong_bo_sot.py
  src/tests/services/test_gate_rule.py
)

# Tìm Python có đủ deps: ưu tiên poetry env ĐÃ CÓ pytest; không thì quét venv pypoetry.
# (Tránh bẫy: `poetry run` với env chưa install sẽ tự tạo venv RỖNG rồi "Command not found".)
PY=""
POETRY_PY="$(poetry env info -p 2>/dev/null)/bin/python"
[[ -x "$POETRY_PY" && -x "$(dirname "$POETRY_PY")/pytest" ]] && PY="$POETRY_PY"
if [[ -z "$PY" ]]; then
  for v in "$HOME"/Library/Caches/pypoetry/virtualenvs/clinicai-*/bin; do
    [[ -x "$v/pytest" ]] && PY="$v/python" && break
  done
fi
[[ -z "$PY" ]] && { echo "Không tìm thấy venv có pytest — chạy: poetry install"; exit 2; }
echo "════ EVAL VÀNG · backend (${#VANG[@]} file) · $(basename "$(dirname "$(dirname "$PY")")") ════"
"$PY" -m pytest "${VANG[@]}" -q -m "not db and not integration" --no-header
BE=$?

FE=0
if [[ "${1:-}" == "--full" ]]; then
  echo; echo "════ EVAL VÀNG · frontend ════"
  ( cd src/dashboard && npx tsc --noEmit && npx eslint . --max-warnings 0 )
  FE=$?
fi

echo; echo "════ KẾT QUẢ ════"
[[ $BE -eq 0 ]] && echo "  backend : PASS" || echo "  backend : FAIL ($BE)"
[[ "${1:-}" == "--full" ]] && { [[ $FE -eq 0 ]] && echo "  frontend: PASS" || echo "  frontend: FAIL ($FE)"; }
exit $(( BE || FE ))
