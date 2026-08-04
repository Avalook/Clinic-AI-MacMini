#!/usr/bin/env bash
# Cấp tài khoản đăng nhập THẬT cho từng nhân sự trong clinic_roster.sql.
#
# BỐI CẢNH. supabase/fixtures/clinic_roster.sql nạp 35 nhân sự thật vào `staff`
# và `clinic_membership`, nhưng CỐ Ý để `staff.auth_user_id` NULL — nó không có
# email của ai. Mà identity.py đọc chính cột đó:
#
#     WHERE s.auth_user_id = $1::uuid
#
# Nên một nhân sự chưa gắn login thì MỌI request ghi của họ trả 403, và màn hình
# không nói được vì sao (họ đăng nhập được, chỉ là không làm được gì). Script
# này đóng khoảng trống đó.
#
# NÓ KHÔNG ĐẶT MẬT KHẨU CHO AI. Dùng luồng invite của Supabase: mỗi người nhận
# email chứa liên kết để TỰ đặt mật khẩu. Không có mật khẩu nào tồn tại trong
# script, trong git, trong lịch sử shell, hay trong tay người chạy script. Đó là
# khác biệt giữa "tài khoản đàng hoàng" và staff_logins.sql — fixture đó dùng
# MỘT mật khẩu yếu dùng chung và chỉ hợp lệ cho máy local.
#
# CÁCH DÙNG
#   1. Tạo scripts/staff-emails.csv (đã gitignore) — hai cột, có tiêu đề:
#
#        staff_id,email
#        d0000000-0000-4000-8000-000000000001,bs.thanh@dr4women.vn
#        d0000000-0000-4000-8000-000000000002,bs.hang@dr4women.vn
#
#      Lấy staff_id ở supabase/fixtures/clinic_roster.sql. Chỉ cần liệt kê
#      những người cần đăng nhập — ai chưa có email thì để lại, chạy lại sau.
#
#   2. export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... DATABASE_URL=...
#
#   3. ./scripts/provision-staff-logins.sh            # THỬ (không ghi gì)
#      ./scripts/provision-staff-logins.sh --apply    # gửi lời mời + gắn link
#
# CHẠY LẠI ĐƯỢC. Người đã có auth_user_id thì bỏ qua, không mời lại.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CSV="${STAFF_EMAILS_CSV:-${REPO}/scripts/staff-emails.csv}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

for tool in curl jq psql; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Cần $tool." >&2; exit 1; }
done

: "${SUPABASE_URL:?export SUPABASE_URL}"
: "${SUPABASE_SERVICE_ROLE_KEY:?export SUPABASE_SERVICE_ROLE_KEY}"
: "${DATABASE_URL:?export DATABASE_URL}"

if [[ ! -f "$CSV" ]]; then
    cat >&2 <<EOF
Không thấy $CSV

Tạo file đó trước (staff_id,email — xem phần đầu script). Nó nằm trong
.gitignore vì email công việc của nhân viên là dữ liệu cá nhân, và repo này
public.
EOF
    exit 1
fi

api() {
    curl -fsS -X "$1" "${SUPABASE_URL%/}/auth/v1/$2" \
        -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
        -H "Content-Type: application/json" \
        ${3:+-d "$3"}
}

echo "=== Nhân sự trong roster CHƯA có login ==="
psql "$DATABASE_URL" -At -F$'\t' <<'SQL'
SELECT s.id, s.full_name, m.role
  FROM public.staff s
  JOIN public.clinic_membership m ON m.staff_id = s.id AND m.is_active
 WHERE s.auth_user_id IS NULL
   AND s.is_active IS NOT FALSE
 ORDER BY m.role, s.full_name;
SQL
echo

[[ $APPLY -eq 0 ]] && echo "(THỬ — chưa gửi lời mời nào. Thêm --apply để chạy thật.)" && echo

linked=0; invited=0; skipped=0; failed=0

# Bỏ dòng tiêu đề; bỏ dòng trống và dòng bắt đầu bằng #.
tail -n +2 "$CSV" | grep -v '^[[:space:]]*$' | grep -v '^[[:space:]]*#' |
while IFS=, read -r staff_id email; do
    staff_id="$(echo "$staff_id" | tr -d '[:space:]')"
    email="$(echo "$email" | tr -d '[:space:]')"
    [[ -z "$staff_id" || -z "$email" ]] && continue

    existing=$(psql "$DATABASE_URL" -At -c \
        "SELECT coalesce(auth_user_id::text, '') FROM public.staff WHERE id = '$staff_id'")

    if [[ -z "$existing" ]]; then
        echo "  ✗ $staff_id — không có trong bảng staff (nạp clinic_roster.sql trước?)"
        failed=$((failed+1)); continue
    fi
    if [[ "$existing" != "" && "$existing" != "null" ]]; then
        echo "  ⊘ $email — đã gắn login, bỏ qua"
        skipped=$((skipped+1)); continue
    fi

    if [[ $APPLY -eq 0 ]]; then
        echo "  → sẽ mời $email và gắn vào $staff_id"
        continue
    fi

    # invite thay vì tạo user + đặt mật khẩu: người dùng tự đặt qua email.
    # Nếu email đã tồn tại trong auth.users thì invite trả 422 — lấy id sẵn có.
    uid=$(api POST invite "{\"email\":\"${email}\"}" 2>/dev/null | jq -r '.id // empty') || true
    if [[ -z "$uid" ]]; then
        uid=$(api GET "admin/users?filter=${email}" | jq -r '.users[0].id // empty') || true
    fi
    if [[ -z "$uid" ]]; then
        echo "  ✗ $email — không tạo/không tìm được tài khoản auth"
        failed=$((failed+1)); continue
    fi

    psql "$DATABASE_URL" -q -c \
        "UPDATE public.staff SET auth_user_id = '$uid', updated_at = now() WHERE id = '$staff_id'"
    echo "  ✓ $email → $staff_id"
    invited=$((invited+1)); linked=$((linked+1))
done

echo
echo "=== Còn lại chưa có login sau lần chạy này ==="
psql "$DATABASE_URL" -At -F$'\t' <<'SQL'
SELECT s.full_name, m.role
  FROM public.staff s
  JOIN public.clinic_membership m ON m.staff_id = s.id AND m.is_active
 WHERE s.auth_user_id IS NULL
   AND s.is_active IS NOT FALSE
 ORDER BY m.role, s.full_name;
SQL
echo
echo "Ai còn trong danh sách trên thì đăng nhập được nhưng MỌI thao tác ghi sẽ"
echo "trả 403 (identity.py tra staff.auth_user_id). Bổ sung email vào $CSV rồi"
echo "chạy lại — script bỏ qua người đã gắn."
