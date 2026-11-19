#!/usr/bin/env bash
# Đẩy log máy chủ (journald: mọi container + timer hệ thống) lên Viettel CFS mỗi giờ.
#
#   ./scripts/day-log-len-viettel.sh      (timer clinicai-log-viettel chạy mỗi giờ)
#
# VÌ SAO (19/11/2026). Journal trên VPS có trần 2G (journald.conf.d/clinicai.conf)
# và đã chạm trần: log chỉ còn ~4 ngày. Truy vụ "chuyển kho → quầy không được" thì
# log trước 15/11 14:41 đã bị xoá. Bản ở đây giữ GIU_NGAY ngày trên ổ Viettel.
#
# CÁCH LÀM — không hở, không trùng:
#   `journalctl --cursor-file` xuất đúng các dòng SAU mốc lần trước. Xuất vào thư
#   mục tạm trên VPS với một BẢN SAO của mốc; chép lên Viettel và đọc lại mã băm
#   xong mới ghi mốc mới. Viettel rớt mạng / bị khoá (như đêm 15/11) thì mốc đứng
#   yên, lần sau xuất bù — journal trên VPS (~4 ngày) là vùng đệm.
#
# Log đã sạch dữ liệu khách ở nguồn: Caddy cắt query (Caddyfile), không ghi thân
# request. Script này không lọc thêm.
#
# Đọc lại một khoảng: xem docs/VAN-HANH-MAY-CHU.md mục "Log cũ trên Viettel".

set -euo pipefail
umask 027

GOC_CFS="${VIETTEL_CFS_DIR:-/mnt/viettel-cfs}"
DICH="$GOC_CFS/logs"
TRANG_THAI="${LOG_VIETTEL_STATE_DIR:-$HOME/.local/state/clinicai-log-viettel}"
MOC="$TRANG_THAI/cursor"
GIU_NGAY="${LOG_VIETTEL_GIU_NGAY:-180}"
JOURNALCTL="${JOURNALCTL_BIN:-journalctl}"
MOUNTPOINT="${MOUNTPOINT_BIN:-mountpoint}"
FINDMNT="${FINDMNT_BIN:-findmnt}"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
noi() { printf '[%s] %s\n' "$(ts)" "$*"; }
hong() { printf '[%s] LỖI: %s\n' "$(ts)" "$*" >&2; exit 1; }
bam() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
    else shasum -a 256 "$1" | awk '{print $1}'; fi
}
# Ngày cách đây N ngày, dạng YYYYMMDD — GNU date trên VPS, BSD date trên Mac (test).
ngay_cach() { date -d "-$1 days" +%Y%m%d 2>/dev/null || date -v-"$1"d +%Y%m%d; }

# ── 1 · Ổ có THẬT SỰ được mount, có mã hoá không ──────────────────────────
# Không mount thì /mnt/viettel-cfs là thư mục thường trên chính đĩa VPS: ghi vào
# đó là lấp đầy cái đĩa đang 89% mà vẫn tưởng đã lưu ngoài máy.
"$MOUNTPOINT" -q "$GOC_CFS" || hong "$GOC_CFS KHÔNG được mount — dừng, mốc giữ nguyên.
       Sửa: sudo mount $GOC_CFS   (xem /etc/fstab)"
"$FINDMNT" -no OPTIONS "$GOC_CFS" | tr ',' '\n' | grep -qx seal \
    || hong "ổ đang mount KHÔNG có 'seal' — đường truyền không mã hoá. Mount lại theo /etc/fstab."

mkdir -p "$TRANG_THAI"

# Hai lần chạy chồng nhau (lần trước xuất bù lâu) sẽ cùng đọc một mốc → trùng.
if command -v flock >/dev/null 2>&1; then
    exec 9>"$TRANG_THAI/khoa"
    flock -n 9 || { noi "Lần trước chưa xong — bỏ lượt này."; exit 0; }
fi

TAM=$(mktemp -d "$TRANG_THAI/tam.XXXXXX")
trap 'rm -rf "$TAM"' EXIT

# ── 2 · Xuất phần mới kể từ mốc ────────────────────────────────────────────
# Chưa có mốc (lần đầu) thì journalctl xuất TOÀN BỘ journal còn giữ — đúng ý:
# cứu luôn ~4 ngày đang có.
[ -f "$MOC" ] && cp "$MOC" "$TAM/cursor"
# Tắt -e quanh ống để tự đọc mã lỗi từng vế, báo đúng vế nào hỏng.
set +e
"$JOURNALCTL" --cursor-file="$TAM/cursor" -o json --no-pager \
    2>"$TAM/loi" | zstd -q -3 -c >"$TAM/log.json.zst"
trang=("${PIPESTATUS[@]}")
set -e
[ "${trang[0]}" = 0 ] || hong "journalctl thất bại: $(head -c 300 "$TAM/loi")"
[ "${trang[1]}" = 0 ] || hong "nén zstd thất bại"
# Không thuộc nhóm systemd-journal thì journalctl KHÔNG báo lỗi — nó im lặng chỉ
# trả log của chính tài khoản này, kèm một dòng gợi ý. Bản lưu như thế là thiếu.
if grep -qi "not seeing messages" "$TAM/loi"; then
    hong "tài khoản $(id -un) không đọc được toàn bộ journal. Sửa:
       sudo usermod -aG systemd-journal $(id -un)   (rồi khởi động lại timer)"
fi
zstd -q -t "$TAM/log.json.zst" || hong "tệp nén vừa tạo đọc không được"

SO_DONG=$(zstd -q -dc "$TAM/log.json.zst" | wc -l | tr -d ' ')
if [ "$SO_DONG" = 0 ]; then
    noi "Không có dòng log mới."
    exit 0
fi

# ── 3 · Chép lên Viettel, đọc lại, rồi mới ghi mốc ────────────────────────
# Tên theo giờ CHẠY: một tệp chứa mọi dòng từ tệp trước tới lúc này (bình thường
# ~1 giờ; sau khi Viettel rớt thì dài hơn).
THU_MUC="$DICH/$(date +%Y/%m/%d)"
mkdir -p "$THU_MUC" || hong "không tạo được $THU_MUC trên Viettel"
# Không bao giờ ghi đè: tệp cũ chứa những dòng mà mốc đã đi qua, mất là mất hẳn.
# Số thứ tự 2 chữ số luôn có mặt để xếp theo tên = xếp theo thời gian
# (`X-2` mà không có ở `X` thì `X-2.json` lại đứng trước `X.json`).
GOC_TEN="$(date +%Y%m%d-%H%M%S)"
n=1
TEN="$GOC_TEN-01.json.zst"
while [ -e "$THU_MUC/$TEN" ] || [ -e "$THU_MUC/$TEN.dang-ghi" ]; do
    n=$((n + 1)); TEN="$GOC_TEN-$(printf %02d "$n").json.zst"
done
SHA=$(bam "$TAM/log.json.zst")
cp "$TAM/log.json.zst" "$THU_MUC/$TEN.dang-ghi" || hong "chép lên Viettel thất bại — mốc giữ nguyên, lần sau xuất bù"
sync
mv "$THU_MUC/$TEN.dang-ghi" "$THU_MUC/$TEN"
[ "$(bam "$THU_MUC/$TEN")" = "$SHA" ] \
    || hong "$TEN: mã băm bên Viettel KHÁC bên này — mốc giữ nguyên, lần sau xuất bù"

mv "$TAM/cursor" "$MOC"
noi "Đã đẩy $SO_DONG dòng → $THU_MUC/$TEN ($(wc -c <"$THU_MUC/$TEN" | tr -d ' ') byte, mã băm khớp)."

# ── 4 · Dọn ngày cũ ────────────────────────────────────────────────────────
# Đi theo cây NĂM/THÁNG/NGÀY (vài trăm thư mục), không `find` từng tệp trên ổ
# mạng — `du`/`find` nghìn tệp qua SMB từng mất nhiều phút.
HAN=$(ngay_cach "$GIU_NGAY")
SO_XOA=0
for d in "$DICH"/[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]; do
    [ -d "$d" ] || continue
    ngay=$(echo "${d#"$DICH"/}" | tr -d /)
    if [[ "$ngay" < "$HAN" ]]; then rm -rf "$d"; SO_XOA=$((SO_XOA + 1)); fi
done
rmdir "$DICH"/[0-9][0-9][0-9][0-9]/[0-9][0-9] "$DICH"/[0-9][0-9][0-9][0-9] 2>/dev/null || true
[ "$SO_XOA" = 0 ] || noi "Đã dọn $SO_XOA ngày cũ hơn $GIU_NGAY ngày."
