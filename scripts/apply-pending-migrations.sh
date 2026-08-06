#!/bin/bash
# Áp các migration còn thiếu, và GHI SỔ đúng cái vừa áp.
#
# ------------------------------------------------------------------------------
# VÌ SAO VIẾT LẠI (06/08/2026)
#
# Bản cũ có ba khuyết tật khiến nó không dùng được nữa, và cái thứ ba là lý do
# một ràng buộc toàn vẹn nằm trên `main` suốt hai ngày mà production không có:
#
#   1. MẬT KHẨU DATABASE VIẾT THẲNG TRONG MÃ NGUỒN, ở dạng connection string
#      đầy đủ. Chưa bao giờ vào lịch sử git (file bị .gitignore chặn đúng vì lẽ
#      đó, repo này public) — nhưng nó là mật khẩu thật của dự án cloud cũ và
#      vẫn nên đổi. Cái giá của việc giấu file: nó nằm ngoài git nên không ai
#      xem lại nó bao giờ, và hai khuyết tật dưới đây sống sót rất lâu.
#
#   2. TRỎ SAI ĐÍCH. Nó trỏ vào dự án Supabase cloud CŨ, trong khi database thật
#      giờ là bộ tự dựng trên VPS. Chạy nó = sửa nhầm database.
#
#   3. DANH SÁCH MIGRATION CỐ ĐỊNH, chép tay, dừng ở 20260803000003. Mọi
#      migration viết sau đó vô hình với nó. Hậu quả có thật: ngày 06/08 phát
#      hiện `20260805000007_appointment_patient_slot_unique` (luật "một bệnh
#      nhân, một khung giờ, một lịch hẹn" — sinh ra sau sự cố một người bấm đặt
#      lịch ba lần) nằm trên main nhưng CHƯA HỀ áp lên production. Không ai thấy,
#      vì sổ ghi cũng không được cập nhật nên nhìn vào đâu cũng thấy "ổn".
#
# Bản này: đích lấy từ môi trường (không có bí mật trong file), danh sách pending
# TÍNH RA bằng cách so thư mục migration với sổ ghi, và mỗi migration được áp
# CÙNG dòng ghi sổ trong MỘT giao dịch — nên không bao giờ có cảnh "đã áp mà sổ
# chưa ghi" hay ngược lại.
# ------------------------------------------------------------------------------
#
# Dùng:
#   ./scripts/apply-pending-migrations.sh            # THỬ KHÔ — chỉ liệt kê
#   ./scripts/apply-pending-migrations.sh --apply    # áp thật
#
# Chọn đích bằng MỘT trong hai (không đặt gì thì script dừng và chỉ cách):
#   CLINIC_DB_DSN='postgresql://user:pw@host:5432/db'   # nối thẳng
#   CLINIC_DB_CONTAINER=clinicai_db                     # qua docker exec
#
# Ví dụ trên VPS:
#   ssh clinic-vps
#   cd ~/clinicai && CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh
#
# Áp trên máy khác thì chạy qua ssh, ĐỪNG mở cổng database ra ngoài.

set -euo pipefail

MIGRATIONS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/supabase/migrations"
MODE="${1:-}"

# ── Đích ──────────────────────────────────────────────────────────────────────
# Hai cách gọi psql, cùng một giao diện: đọc SQL từ stdin, in kết quả ra stdout.
if [[ -n "${CLINIC_DB_DSN:-}" ]]; then
  run_sql() { psql "$CLINIC_DB_DSN" -v ON_ERROR_STOP=1 -q "$@"; }
  DICH="DSN (${CLINIC_DB_DSN%%:*}://…)"
elif [[ -n "${CLINIC_DB_CONTAINER:-}" ]]; then
  run_sql() {
    docker exec -i "$CLINIC_DB_CONTAINER" \
      psql -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" \
           -v ON_ERROR_STOP=1 -q "$@"
  }
  DICH="container ${CLINIC_DB_CONTAINER}"
else
  cat >&2 <<'HD'
Chưa chọn đích. Đặt MỘT trong hai biến môi trường:

  CLINIC_DB_CONTAINER=clinicai_db     # chạy ngay trên máy có database
  CLINIC_DB_DSN='postgresql://…'      # nối thẳng

Cố ý KHÔNG có giá trị mặc định: một script migration đoán lấy đích là một script
migration có ngày sửa nhầm database.
HD
  exit 2
fi

# ── Sổ ghi ────────────────────────────────────────────────────────────────────
# Dùng `supabase_migrations.schema_migrations` vì đó là sổ mà `supabase db push`
# đọc. Có thêm `public.schema_migrations` trong lược đồ (0 dòng, dấu tích của
# một công cụ khác) — CỐ Ý không đụng, hai sổ ghi cho một việc là cách chắc chắn
# nhất để chúng lệch nhau.
run_sql <<'SQL' >/dev/null
CREATE SCHEMA IF NOT EXISTS supabase_migrations;
CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
    version text PRIMARY KEY,
    name    text,
    statements text[]
);
SQL

DA_AP="$(run_sql -tAc 'SELECT version FROM supabase_migrations.schema_migrations' | tr -d ' \r')"

# ── Tính danh sách còn thiếu ──────────────────────────────────────────────────
PENDING=()
for f in "$MIGRATIONS_DIR"/*.sql; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f")"
  version="${base%%_*}"
  if ! grep -qx "$version" <<<"$DA_AP"; then
    PENDING+=("$base")
  fi
done

echo "Đích: $DICH"
echo "Đã ghi sổ: $(grep -c . <<<"$DA_AP" || true) migration"
echo ""

if [[ ${#PENDING[@]} -eq 0 ]]; then
  echo "Không còn migration nào để áp."
  exit 0
fi

echo "Còn thiếu ${#PENDING[@]}:"
for m in "${PENDING[@]}"; do
  echo "  • $m  ($(wc -l <"$MIGRATIONS_DIR/$m" | tr -d ' ') dòng)"
done
echo ""

if [[ "$MODE" != "--apply" ]]; then
  echo "Đây là THỬ KHÔ. Chạy lại với --apply để áp thật."
  exit 0
fi

# ── Áp ────────────────────────────────────────────────────────────────────────
# Migration VÀ dòng ghi sổ nằm trong CÙNG một giao dịch: hoặc cả hai, hoặc không
# cái nào. Đây là chỗ bản cũ sai — nó áp xong mới ghi sổ ở bước riêng (và thực
# tế là không ghi), nên sổ nói dối mà không ai biết.
#
# Không migration nào trong repo dùng CREATE INDEX CONCURRENTLY (đã kiểm), nên
# gói tất cả vào giao dịch là an toàn. Nếu sau này có, migration đó phải tự
# quản và script này phải được sửa CÓ Ý THỨC — đừng lặng lẽ bỏ BEGIN.
APPLIED=0
for m in "${PENDING[@]}"; do
  version="${m%%_*}"
  name="${m#*_}"; name="${name%.sql}"
  printf '  → %s ... ' "$m"

  if {
      echo "BEGIN;"
      cat "$MIGRATIONS_DIR/$m"
      echo ";"
      printf "INSERT INTO supabase_migrations.schema_migrations (version, name) VALUES ('%s','%s');\n" \
             "$version" "$name"
      echo "COMMIT;"
     } | run_sql >/tmp/clinic-migration-out.txt 2>&1; then
    echo "xong"
    APPLIED=$((APPLIED + 1))
  else
    echo "HỎNG"
    sed 's/^/      /' /tmp/clinic-migration-out.txt | tail -12
    echo ""
    echo "  Dừng ở cái đầu tiên hỏng. Migration này đã được huỷ bỏ hoàn toàn"
    echo "  (giao dịch rollback), sổ ghi không có dòng nào cho nó. Sửa rồi chạy lại."
    exit 1
  fi
done

echo ""
echo "Đã áp $APPLIED migration."
