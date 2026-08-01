#!/usr/bin/env bash
# Đọc phản hồi chủ sản phẩm đã gửi từ Bảng điều khiển.
#
# Đây là đầu kia của vòng lặp: Quang bấm, thấy sai, chụp màn hình và viết một
# câu; tôi chạy lệnh này ở đầu phiên sau và biết ngay hỏng ở đâu, ở màn nào,
# với vai gì — thay vì hỏi lại và bắt anh mô tả lại từ đầu.
#
#   scripts/read-feedback.sh            # phản hồi chưa xử lý
#   scripts/read-feedback.sh --all      # tất cả
#   scripts/read-feedback.sh --done ID  # đánh dấu đã sửa

set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${FEEDBACK_DB_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"

if [ "${1:-}" = "--done" ]; then
    [ -n "${2:-}" ] || { echo "usage: $0 --done <id>" >&2; exit 2; }
    psql -q "$DB" -c "UPDATE owner_feedback SET status='da_sua', resolved_at=now() WHERE id='$2'"
    echo "  đã đánh dấu $2 là đã sửa"
    exit 0
fi

WHERE="WHERE status = 'moi'"
[ "${1:-}" = "--all" ] && WHERE=""

psql -tA -F'|' "$DB" -c "
  SELECT id, to_char(created_at,'DD/MM HH24:MI'), severity, status,
         coalesce(page_url,'-'), coalesce(role_at_time,'-'),
         coalesce(image_path,''), replace(comment, chr(10), ' ')
    FROM owner_feedback $WHERE ORDER BY created_at DESC" 2>/dev/null |
while IFS='|' read -r id when sev st page role img comment; do
    [ -n "$id" ] || continue
    printf '\n\033[1m%s\033[0m  %s · %s · %s\n' "$sev" "$when" "$page" "$role"
    printf '  %s\n' "$comment"
    if [ -n "$img" ] && [ -f "$REPO/$img" ]; then
        printf '  ảnh: %s\n' "$REPO/$img"
    elif [ -n "$img" ]; then
        printf '  ảnh: %s (KHÔNG TÌM THẤY FILE)\n' "$img"
    fi
    printf '  \033[2mid %s · đánh dấu xong: scripts/read-feedback.sh --done %s\033[0m\n' "$id" "$id"
done

n=$(psql -tA "$DB" -c "SELECT count(*) FROM owner_feedback WHERE status='moi'" 2>/dev/null | tr -d ' ')
printf '\n  %s phản hồi chưa xử lý\n' "${n:-?}"
