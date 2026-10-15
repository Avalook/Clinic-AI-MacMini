# shellcheck shell=bash
# GIỜ PHÒNG KHÁM DÙNG HỆ THỐNG — một chỗ duy nhất trả lời "bây giờ có đang giờ
# khám không" cho cả deploy prod (scripts/deploy-backend.sh) và staging chung
# máy (scripts/lib/staging-chung.sh). `source`, không chạy.
#
# Khung (Tuyền chốt 11/11/2026), nửa mở [từ, đến), giờ Việt Nam:
#   thứ 2–6:      16h → 23h
#   thứ 7, CN:     7h → 23h
# Đổi khung = sửa hằng số ở đây bằng một PR. CỐ Ý không có biến môi trường đổi
# khung hay giả giờ: trên VPS, một biến như thế là cửa sau bỏ qua khoá mà không
# để lại lý do. Test giả giờ bằng một `date` giả đứng đầu PATH.
#
# Giờ VN = Asia/Ho_Chi_Minh = UTC+7 cố định (không có giờ mùa hè) → tính từ
# `date -u`, khỏi phụ thuộc tzdata trên VPS (thiếu tzdata thì
# `TZ=Asia/Ho_Chi_Minh date` lặng lẽ in giờ UTC). Đọc thứ và giờ trong MỘT lần
# gọi `date`: hai lần gọi có thể rơi hai bên mốc 17:00 UTC (= 0h VN hôm sau).

GIO_KHAM_TU_NGAY_THUONG=16
GIO_KHAM_TU_CUOI_TUAN=7
GIO_KHAM_DEN=23

# In "thứ giờ" theo giờ VN: thứ 1 = thứ 2 … 7 = Chủ nhật; giờ 0–23.
thu_gio_vn() {
    local utc thu gio
    utc="$(date -u '+%u %H')"
    thu=$(( 10#${utc% *} ))
    gio=$(( 10#${utc#* } + 7 ))
    if [ "$gio" -ge 24 ]; then
        gio=$(( gio - 24 ))
        thu=$(( thu % 7 + 1 ))
    fi
    printf '%s %s\n' "$thu" "$gio"
}

# dang_gio_kham — mã 0 nếu ĐANG giờ khám, 1 nếu không. Luôn đặt biến
# GIO_KHAM_MO_TA (vd "16h thứ 6, khung 16h–23h") để câu thông báo dùng.
dang_gio_kham() {
    local tg thu gio tu ten_thu
    tg="$(thu_gio_vn)"
    thu="${tg% *}"
    gio="${tg#* }"
    if [ "$thu" -ge 6 ]; then tu=$GIO_KHAM_TU_CUOI_TUAN; else tu=$GIO_KHAM_TU_NGAY_THUONG; fi
    if [ "$thu" -eq 7 ]; then ten_thu="Chủ nhật"; else ten_thu="thứ $(( thu + 1 ))"; fi
    GIO_KHAM_MO_TA="${gio}h ${ten_thu} giờ VN, khung ${tu}h–${GIO_KHAM_DEN}h"
    [ "$gio" -ge "$tu" ] && [ "$gio" -lt "$GIO_KHAM_DEN" ]
}
