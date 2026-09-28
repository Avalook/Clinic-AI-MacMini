"""LƯỢT TREO — MỘT định nghĩa cho cả màn Check-out và bộ canh gác (27/09/2026).

Trước đợt 3 có HAI câu khác nhau cho cùng một chữ "lượt tồn đọng":
  * màn Check-out (`CheckoutService.stale_list`) lấy lượt OPEN/IN_PROGRESS
    check-in trước hôm nay — nhưng KHÔNG loại lượt đã check-out (`closed_at`):
    check-out thường giữ `status = IN_PROGRESS`, nên khách đã về hôm qua vẫn
    nằm trong danh sách "cần đóng";
  * canh gác `LUOT_TREO` (`canh_gac.do_so`) đếm đúng lượt chưa đóng.
Hai con số lệch nhau thì cảnh báo nói "5 lượt treo" mà màn hiện 12 (hay ngược
lại) — người trực không biết tin cái nào. Nay cả hai ghép đúng câu dưới.

Lượt TREO = còn mở (OPEN / IN_PROGRESS), CHƯA check-out (`closed_at` rỗng),
check-in TRƯỚC HÔM NAY theo giờ Việt Nam. INCOMPLETE (khách bỏ về) / FINALIZED
/ AMENDED không tính: đã có người chốt số phận. Lượt không có giờ check-in
không tính (không biết "từ hôm nào").
"""

from __future__ import annotations

import re


def dieu_kien_luot_treo(bi_danh: str = "v") -> str:
    """Mệnh đề SQL (đặt sau WHERE / AND) chọn lượt treo của bảng `visit` mang bí
    danh ``bi_danh``. Bí danh chỉ nhận chữ thường / số / gạch dưới — không ghép
    chuỗi lạ vào SQL."""
    if not isinstance(bi_danh, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*", bi_danh):
        raise ValueError(f"Bí danh bảng không hợp lệ: {bi_danh!r}")
    b = bi_danh
    return (
        f"({b}.status IN ('OPEN', 'IN_PROGRESS') AND {b}.closed_at IS NULL"
        f" AND {b}.checked_in_at IS NOT NULL"
        f" AND ({b}.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
        f" < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)"
    )


__all__ = ["dieu_kien_luot_treo"]
