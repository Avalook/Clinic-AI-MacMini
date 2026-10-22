# shellcheck shell=bash
# Chọn BẢN SAO LƯU CHÍNH mới nhất trong một thư mục — dùng chung cho mọi script
# đẩy / kiểm / khôi phục bản sao (nạp bằng `. scripts/lib/chon-ban-sao.sh`).
#
# Mỗi lần backup-db.sh chạy ghi ba tệp cùng mốc giờ: `X.sql.gz` (chính),
# `X_auth.sql.gz`, rồi SAU CÙNG `X_lich_su_notion.sql.gz`. Trước 21/10/2026 năm
# script tự chép cách chọn và chỉ loại `_auth` → "mới nhất" ra tệp notion: đẩy
# Viettel dừng vì "thiếu tệp auth đi kèm" (systemd `ExecStart=-` nuốt lỗi). Thêm
# tệp đi kèm mới ở backup-db.sh thì thêm vào DI_KEM dưới đây — một chỗ.
#
#   chon_ban_chinh_moi_nhat <thư mục> [tiền tố tên, mặc định clinicai_]
#   → in đường dẫn tệp chính mới nhất theo giờ sửa; không có thì in rỗng.

DI_KEM_BAN_SAO='_(auth|lich_su_notion)\.sql\.gz$'

chon_ban_chinh_moi_nhat() {
    local thu_muc="$1" tien_to="${2-clinicai_}"
    # shellcheck disable=SC2012  # tên tệp do backup-db.sh đặt, không có khoảng trắng
    ls -1t "$thu_muc"/"$tien_to"*.sql.gz 2>/dev/null \
        | grep -Ev "$DI_KEM_BAN_SAO" | head -n 1 || true
}
