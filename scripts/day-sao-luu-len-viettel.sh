#!/usr/bin/env bash
# Đẩy bản sao lưu mới nhất sang database Viettel — bản sao NGOÀI MÁY.
#
# VÌ SAO CẦN. Bản sao lưu hằng đêm đang nằm cùng ổ đĩa với chính database nó sao
# lưu. Ổ hỏng là mất cả hai, và lúc đó có bao nhiêu bản cũng bằng không. Một bản
# sao ở máy khác là thứ duy nhất chịu được sự cố phần cứng.
#
# VÌ SAO CHỨA DẠNG TỆP, KHÔNG NẠP THẲNG LƯỢC ĐỒ.
#
# Gói Viettel đang có là Database Service (DBaaS) — database dựng sẵn, không cấp
# CREATEROLE. Mà bản dump của ClinicAI có 61 dòng khai chính sách RLS kiểu
# `CREATE POLICY … TO authenticated`: nạp nó sang một database không có vai
# `authenticated` là hỏng ngay dòng đầu tiên chạm tới chính sách.
#
# Nên ở đây Viettel đóng vai KHO CHỨA: mỗi đêm một dòng, mang nguyên tệp .gz.
# Không phụ thuộc vai, không phụ thuộc extension, không phụ thuộc phiên bản
# Postgres — ta chỉ cất một chuỗi byte và một mã băm để về sau đối chiếu.
#
# Bản sao lưu ~220 KB/đêm; gói 20 GB đủ cho nhiều năm.
#
# ĐÂY KHÔNG PHẢI BẢN CHẠY ĐƯỢC. Muốn khôi phục thì tải tệp về rồi chạy
# scripts/restore-db.sh như bình thường — xem phần cuối file.
#
#   ./scripts/day-sao-luu-len-viettel.sh
#
# Cần một file .env.viettel (KHÔNG theo git) ngay cạnh repo:
#   VIETTEL_DATABASE_URL=postgresql://user:mat_khau@host:5432/tendb?sslmode=require

set -euo pipefail
umask 077

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${VIETTEL_ENV_FILE:-${REPO}/.env.viettel}"
BACKUP_DIR="${CLINIC_BACKUP_DIR:-$HOME/backups/clinicai}"
GIU_LAI="${VIETTEL_GIU_LAI:-30}"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
noi() { printf '[%s] %s\n' "$(ts)" "$*"; }
hong() { printf '[%s] LỖI: %s\n' "$(ts)" "$*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || hong "thiếu $ENV_FILE — xem hướng dẫn ở đầu file này."

URL=$(grep -E '^VIETTEL_DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)
[ -n "$URL" ] || hong "$ENV_FILE không có VIETTEL_DATABASE_URL"

# CHỐT CHỐNG ĐẨY VỀ CHÍNH MÌNH. Một bản sao "ngoài máy" trỏ vào đúng cái máy nó
# sao lưu là bản sao vô dụng — và nó trông y hệt một bản sao thật trong mọi báo
# cáo. Tên container database cục bộ không được xuất hiện trong chuỗi kết nối.
# Cửa thoát CÓ TÊN, chỉ để tự kiểm luồng đẩy trước khi có thật thông tin
# Viettel. Đặt tên dài và xấu để không ai vô tình bật nó trong systemd.
if [ "${VIETTEL_CHO_PHEP_DICH_CUC_BO:-0}" != "1" ]; then
    case "$URL" in
        *clinicai_db*|*127.0.0.1*|*localhost*|*host.docker.internal*)
            hong "VIETTEL_DATABASE_URL trỏ về database cục bộ. Bản sao ngoài máy phải ở MÁY KHÁC."
            ;;
    esac
else
    noi "CẢNH BÁO: đang đẩy về một đích CỤC BỘ (chế độ tự kiểm). Đây KHÔNG phải bản sao ngoài máy."
fi

command -v psql >/dev/null || hong "cần psql: sudo apt install -y postgresql-client"

PSQL=(psql "$URL" -X -v ON_ERROR_STOP=1 -tAq)

noi "Nối tới Viettel…"
PHIEN_BAN=$("${PSQL[@]}" -c "SHOW server_version" 2>&1) \
    || hong "không nối được: $PHIEN_BAN"
noi "Đã nối. PostgreSQL $PHIEN_BAN"

# Bảng kho. Đặt tên có tiền tố rõ ràng: database này về sau có thể còn dùng cho
# việc khác, và một bảng tên `backup` trần thì không ai biết của ai.
"${PSQL[@]}" <<'SQL' >/dev/null
CREATE TABLE IF NOT EXISTS clinicai_sao_luu (
    id          bigserial PRIMARY KEY,
    ten_tep     text        NOT NULL,
    loai        text        NOT NULL CHECK (loai IN ('public', 'auth', 'media')),
    tao_luc     timestamptz NOT NULL DEFAULT now(),
    so_byte     bigint      NOT NULL,
    sha256      text        NOT NULL,
    noi_dung    bytea       NOT NULL,
    UNIQUE (ten_tep)
);

-- NỚI RÀNG BUỘC CHO BẢNG ĐÃ TỒN TẠI.
--
-- `CREATE TABLE IF NOT EXISTS` không đụng tới bảng đã có, nên dòng CHECK ở trên
-- chỉ áp cho lần chạy đầu tiên. Bảng trên Viettel dựng ngày 08/08 với đúng hai
-- giá trị 'public' và 'auth' — đêm đầu tiên có tệp media, `INSERT` sẽ chết vì
-- ràng buộc, và cả bản dump lẫn media đều không lên được.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'clinicai_sao_luu'::regclass
           AND contype = 'c'
           AND pg_get_constraintdef(oid) NOT LIKE '%media%'
           AND pg_get_constraintdef(oid) LIKE '%loai%'
    ) THEN
        ALTER TABLE clinicai_sao_luu DROP CONSTRAINT clinicai_sao_luu_loai_check;
        ALTER TABLE clinicai_sao_luu ADD CONSTRAINT clinicai_sao_luu_loai_check
            CHECK (loai IN ('public', 'auth', 'media'));
    END IF;
END $$;

COMMENT ON TABLE clinicai_sao_luu IS
    'Bản sao lưu ClinicAI đẩy từ máy chủ sang. Mỗi đêm: public + auth, '
    'và media nếu phòng khám có ảnh siêu âm.';
SQL

bam() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
    else shasum -a 256 "$1" | awk '{print $1}'; fi
}

day_len() {
    local tep="$1" loai="$2" ten b64 sha byte da_co
    ten=$(basename "$tep")
    sha=$(bam "$tep")
    byte=$(wc -c < "$tep" | tr -d ' ')

    da_co=$("${PSQL[@]}" -c \
        "SELECT sha256 FROM clinicai_sao_luu WHERE ten_tep = '${ten}'")
    if [ "$da_co" = "$sha" ]; then
        noi "  bỏ qua $ten (đã có, mã băm khớp)"
        return 0
    fi
    [ -z "$da_co" ] || hong "  $ten đã có trên Viettel nhưng mã băm KHÁC — dừng."

    # `\copy` chứ không phải tham số dòng lệnh: nó truyền theo luồng nên không
    # đụng giới hạn độ dài tham số, và bản sao lưu sẽ còn lớn lên.
    b64=$(mktemp "${TMPDIR:-/tmp}/clinicai-b64.XXXXXX")
    trap 'rm -f "$b64"' RETURN
    base64 -w0 < "$tep" > "$b64" 2>/dev/null || base64 < "$tep" | tr -d '\n' > "$b64"

    psql "$URL" -X -v ON_ERROR_STOP=1 -q <<SQL
CREATE TEMP TABLE _nap (b64 text);
\\copy _nap (b64) FROM '${b64}'
INSERT INTO clinicai_sao_luu (ten_tep, loai, so_byte, sha256, noi_dung)
SELECT '${ten}', '${loai}', ${byte}, '${sha}',
       decode(string_agg(b64, '' ORDER BY ctid), 'base64')
  FROM _nap;
SQL

    # ĐỌC LẠI ĐỂ ĐỐI CHIẾU. Ghi xong mà không kiểm thì "đã đẩy" chỉ có nghĩa là
    # lệnh không báo lỗi — chưa phải là byte bên kia giống byte bên này.
    local sha_ben_kia
    sha_ben_kia=$("${PSQL[@]}" -c \
        "SELECT encode(sha256(noi_dung), 'hex') FROM clinicai_sao_luu WHERE ten_tep = '${ten}'")
    [ "$sha_ben_kia" = "$sha" ] \
        || hong "  $ten: mã băm bên Viettel KHÁC bên này ($sha_ben_kia ≠ $sha)"
    noi "  đã đẩy $ten ($byte byte, mã băm khớp)"
}

MOI_NHAT=$(ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | grep -v '_auth\.sql\.gz$' | head -1 || true)
[ -n "$MOI_NHAT" ] || hong "không thấy bản sao lưu nào trong $BACKUP_DIR"
AUTH="${MOI_NHAT%.sql.gz}_auth.sql.gz"
# CẢ HAI HOẶC KHÔNG CẢ HAI. Đẩy mỗi phần public sang là cất một bản không khôi
# phục được: staff.auth_user_id có khoá ngoại tới auth.users, thiếu nó thì
# khôi phục chết giữa chừng.
[ -f "$AUTH" ] || hong "thiếu tệp auth đi kèm: $AUTH"

noi "Đẩy cặp mới nhất:"
day_len "$MOI_NHAT" public
day_len "$AUTH" auth

# ── Tệp media ──────────────────────────────────────────────────────────────
#
# Ảnh và video siêu âm không nằm trong pg_dump; từ 08/08/2026 backup-db.sh đóng
# gói chúng thành `..._media.tar.gz` bên cạnh. Nếu chỗ này không đẩy nó đi thì
# ảnh bệnh nhân chỉ tồn tại trên đúng một cái ổ đĩa.
#
# CÓ TRẦN, VÀ NÓI RA KHI VƯỢT. Gói Viettel là 20GB, còn base64 làm mọi thứ phồng
# thêm một phần ba. Video 50MB × 30 ca/ngày sẽ lấp nó trong vài tuần, và cách hỏng
# tệ nhất là đẩy im lặng cho tới đêm database bên kia đầy — lúc đó cả bản dump
# lẫn media đều không lên được, và không ai biết.
#
# Vượt trần thì BỎ QUA MEDIA nhưng VẪN đẩy dump, và hét lên. Bỏ qua im lặng là
# đúng cái bệnh đang đi chữa.
MEDIA="${MOI_NHAT%.sql.gz}_media.tar.gz"
MEDIA_TRAN="${VIETTEL_MEDIA_TOI_DA_BYTE:-536870912}"   # 512MB
if [ -f "$MEDIA" ]; then
    MEDIA_BYTE=$(wc -c < "$MEDIA" | tr -d ' ')
    if [ "$MEDIA_BYTE" -le "$MEDIA_TRAN" ]; then
        day_len "$MEDIA" media
    else
        noi "  ⚠️  BỎ QUA $(basename "$MEDIA"): ${MEDIA_BYTE} byte > trần ${MEDIA_TRAN}."
        noi "     ẢNH BỆNH NHÂN HIỆN CHỈ CÓ MỘT BẢN, trên chính máy chủ này."
        noi "     Cần một đường khác cho tệp lớn (R2/rclone), hoặc nâng"
        noi "     VIETTEL_MEDIA_TOI_DA_BYTE nếu dung lượng Viettel còn đủ."
    fi
else
    noi "  (không có tệp media đi kèm — bản sao lưu này không có ảnh nào)"
fi

# Dọn bản cũ. Mỗi đêm sinh 2 hoặc 3 dòng (public + auth, và media nếu có), nên
# đếm theo NGÀY chứ không nhân một hằng số — nhân 2 như trước sẽ xoá nhầm bản
# public của đêm trước ngay đêm đầu tiên có media.
XOA=$("${PSQL[@]}" <<SQL
WITH giu AS (
    SELECT DISTINCT tao_luc::date AS ngay
      FROM clinicai_sao_luu
     ORDER BY ngay DESC
     LIMIT ${GIU_LAI}
)
DELETE FROM clinicai_sao_luu
 WHERE tao_luc::date NOT IN (SELECT ngay FROM giu)
RETURNING 1
SQL
)
noi "Đã dọn $(printf '%s' "$XOA" | grep -c 1 || true) dòng cũ (giữ ${GIU_LAI} đêm)."

TONG=$("${PSQL[@]}" -c \
    "SELECT count(*) || ' dòng, ' || pg_size_pretty(sum(so_byte)) FROM clinicai_sao_luu")
noi "Trên Viettel hiện có: $TONG"

cat <<'HD'

Khôi phục từ bản trên Viettel:
  psql "$VIETTEL_DATABASE_URL" -tAq -c \
    "SELECT encode(noi_dung,'base64') FROM clinicai_sao_luu
      WHERE loai='public' ORDER BY tao_luc DESC LIMIT 1" \
    | base64 -d > ban.sql.gz
  # rồi chạy scripts/restore-db.sh như với một bản sao lưu cục bộ.
HD
