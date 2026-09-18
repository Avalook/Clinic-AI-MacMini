#!/usr/bin/env bash
# Đẩy bản sao lưu mới nhất lên Viettel Cloud File Storage — bản sao NGOÀI MÁY.
#
#   ./scripts/day-sao-luu-len-viettel-storage.sh
#
# KHÁC GÌ `day-sao-luu-len-viettel.sh`. File kia đẩy vào *database* Viettel
# (DBaaS) dưới dạng dòng `bytea`, và đường tới đó KHÔNG mã hoá được — máy chủ
# của họ từ chối SSL (`server does not support SSL`), nên dump có tên và hồ sơ
# bệnh nhân sẽ đi trần qua Internet. File này đẩy lên *ổ đĩa mạng* (vCFS), mount
# bằng SMB 3.1.1 có `seal` — mã hoá thật. Cùng một nhà cung cấp, hai đường rất
# khác nhau về an toàn; đây là đường nên dùng.
#
# CÁI BẪY LỚN NHẤT CỦA MỌI SCRIPT KIỂU NÀY, và vì sao có bước kiểm ở dưới:
# `/mnt/viettel-cfs` khi KHÔNG mount vẫn là một thư mục bình thường trên chính
# ổ đĩa của VPS. Mạng rớt, mount tuột — `cp` vẫn chạy ngon, script vẫn báo
# "đã đẩy", dung lượng vẫn tăng. Và bản sao "ngoài máy" ấy nằm đúng trên cái ổ
# nó đang bảo vệ. Hỏng kiểu đó không có triệu chứng nào cho tới ngày ổ chết.
# Nên: `mountpoint -q` là câu hỏi đầu tiên, và không có nó thì DỪNG.

set -euo pipefail
umask 077

DICH="${VIETTEL_CFS_DIR:-/mnt/viettel-cfs}/db-backups"
BACKUP_DIR="${CLINIC_BACKUP_DIR:-$HOME/backups/clinicai}"
GIU_LAI="${VIETTEL_CFS_GIU_LAI:-30}"          # số ĐÊM giữ lại

ts() { date "+%Y-%m-%d %H:%M:%S"; }
noi() { printf '[%s] %s\n' "$(ts)" "$*"; }
hong() { printf '[%s] LỖI: %s\n' "$(ts)" "$*" >&2; exit 1; }

# ── 1 · Ổ có THẬT SỰ được mount không ──────────────────────────────────────
mountpoint -q "${VIETTEL_CFS_DIR:-/mnt/viettel-cfs}" \
    || hong "${VIETTEL_CFS_DIR:-/mnt/viettel-cfs} KHÔNG được mount. Ghi vào đó lúc này là
       ghi lên chính ổ đĩa VPS — một bản sao 'ngoài máy' vô dụng. Sửa:
       sudo mount ${VIETTEL_CFS_DIR:-/mnt/viettel-cfs}   (xem /etc/fstab)"

# Mount đúng chỗ nhưng có mã hoá không? `seal` rơi mất là dữ liệu bệnh nhân đi
# trần mà mọi thứ khác trông vẫn bình thường.
findmnt -no OPTIONS "${VIETTEL_CFS_DIR:-/mnt/viettel-cfs}" | tr ',' '\n' | grep -qx seal \
    || hong "ổ đang mount KHÔNG có 'seal' — đường truyền không mã hoá. Mount lại theo /etc/fstab."

mkdir -p "$DICH"

# ── 2 · Tìm cặp mới nhất ───────────────────────────────────────────────────
MOI_NHAT=$(ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | grep -v '_auth\.sql\.gz$' | head -1 || true)
[ -n "$MOI_NHAT" ] || hong "không thấy bản sao lưu nào trong $BACKUP_DIR"

AUTH="${MOI_NHAT%.sql.gz}_auth.sql.gz"
# CẢ HAI HOẶC KHÔNG CẢ HAI. `staff.auth_user_id` có khoá ngoại tới `auth.users`;
# cất mỗi phần public là cất một bản không khôi phục nổi.
[ -f "$AUTH" ] || hong "thiếu tệp auth đi kèm: $(basename "$AUTH")"

bam() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
    else shasum -a 256 "$1" | awk '{print $1}'; fi
}

# ── 3 · Đẩy, rồi ĐỌC LẠI ĐỂ ĐỐI CHIẾU ──────────────────────────────────────
day_len() {
    local tep="$1" ten sha sha_ben_kia dich_tep
    ten=$(basename "$tep")
    dich_tep="$DICH/$ten"
    sha=$(bam "$tep")

    if [ -f "$dich_tep" ]; then
        if [ "$(bam "$dich_tep")" = "$sha" ]; then
            noi "  bỏ qua $ten (đã có, mã băm khớp)"
            return 0
        fi
        hong "  $ten đã có trên Viettel nhưng mã băm KHÁC — dừng, không ghi đè."
    fi

    # Ghi ra tên tạm rồi đổi tên: đứt mạng giữa chừng sẽ để lại `.dang-ghi`
    # thay vì một tệp cụt mang đúng tên thật — thứ mà lần khôi phục sau sẽ tin.
    cp "$tep" "${dich_tep}.dang-ghi" || hong "  ghi $ten thất bại"
    sync
    mv "${dich_tep}.dang-ghi" "$dich_tep"

    # ĐỌC LẠI. "Đã đẩy" mà không kiểm chỉ có nghĩa là lệnh không báo lỗi —
    # chưa phải là byte bên kia giống byte bên này.
    sha_ben_kia=$(bam "$dich_tep")
    [ "$sha_ben_kia" = "$sha" ] \
        || hong "  $ten: mã băm bên Viettel KHÁC bên này — dữ liệu hỏng trên đường."
    noi "  đã đẩy $ten ($(wc -c < "$tep" | tr -d ' ') byte, mã băm khớp)"
}

noi "Đẩy lên $DICH"
day_len "$MOI_NHAT"
day_len "$AUTH"

MANIFEST="${MOI_NHAT}.manifest"
[ -f "$MANIFEST" ] && day_len "$MANIFEST"

# Ảnh/video siêu âm nếu có. Ổ này 1 TB nên không cần trần 512MB như đường DBaaS.
MEDIA="${MOI_NHAT%.sql.gz}_media.tar.gz"
[ -f "$MEDIA" ] && day_len "$MEDIA" || noi "  (không có tệp media đi kèm)"

# ── 4 · Dọn bản cũ, đếm theo NGÀY ──────────────────────────────────────────
# Đếm theo ngày chứ không nhân một hằng số: mỗi đêm sinh 2, 3 hay 4 tệp tuỳ có
# media và manifest hay không, nên nhân lên là xoá nhầm bản của đêm trước.
mapfile -t NGAY_CU < <(
    find "$DICH" -maxdepth 1 -name '*.gz' -printf '%TY-%Tm-%Td\n' 2>/dev/null \
        | sort -u | head -n -"$GIU_LAI"
)
SO_XOA=0
for ngay in "${NGAY_CU[@]:-}"; do
    [ -n "$ngay" ] || continue
    while IFS= read -r f; do
        rm -f "$f"; SO_XOA=$((SO_XOA + 1))
    done < <(find "$DICH" -maxdepth 1 -newermt "$ngay 00:00" ! -newermt "$ngay 23:59:59" -type f)
done
noi "Đã dọn $SO_XOA tệp cũ (giữ $GIU_LAI đêm)."

# ── 5 · Báo cáo ────────────────────────────────────────────────────────────
SO_TEP=$(find "$DICH" -maxdepth 1 -type f | wc -l | tr -d ' ')
DUNG_LUONG=$(du -sh "$DICH" 2>/dev/null | awk '{print $1}')
CON_TRONG=$(df -h "$DICH" | tail -1 | awk '{print $4}')
noi "Trên Viettel Storage: $SO_TEP tệp, $DUNG_LUONG đã dùng, $CON_TRONG còn trống."

cat <<HD

Khôi phục từ bản trên Viettel Storage:
  cp /mnt/viettel-cfs/db-backups/<ten>.sql.gz ~/
  # rồi chạy scripts/restore-db.sh như với một bản sao lưu cục bộ.
HD
