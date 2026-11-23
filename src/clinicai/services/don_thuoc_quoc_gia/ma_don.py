"""Mã đơn thuốc quốc gia — TT 26/2025/TT-BYT Phụ lục I chú thích 1 + QĐ 808 mục VII.1.

14 ký tự ``xxxxxyyyyyyy-z``: 5 ký tự mã cơ sở khám chữa bệnh, 7 ký tự ngẫu nhiên
0-9 / a-z (duy nhất trong cơ sở — Postgres ép bằng `uq_dtqg_gui_ma_don`), dấu
``-``, loại đơn. Viết THƯỜNG theo QĐ 808 và các phần mềm đang chạy (TT 26 viết
hoa — hỏi lại hotrokythuat@donthuocquocgia.vn trước khi bật thật).
"""

from __future__ import annotations

import re
import secrets
import string

_KY_TU = string.digits + string.ascii_lowercase
#: c = đơn thường. n / h (gây nghiện, hướng thần) và y (cổ truyền) cần phân loại
#: thuốc mà danh mục ClinicAI chưa có — mọi đơn hiện gửi loại c (xem docs).
LOAI_THUONG = "c"
MA_DON = re.compile(r"^[0-9A-Za-z]{5}[0-9a-z]{7}-[cnhy]$")


def sinh_ma_don(ma_co_so: str, loai: str = LOAI_THUONG) -> str:
    """Mã đơn mới. ``ma_co_so`` phải đúng 5 ký tự chữ/số (cấu hình đã kiểm)."""
    duoi = "".join(secrets.choice(_KY_TU) for _ in range(7))
    ma = f"{ma_co_so}{duoi}-{loai}"
    if not MA_DON.match(ma):
        raise ValueError("mã cơ sở / loại đơn sai dạng")
    return ma


__all__ = ["LOAI_THUONG", "MA_DON", "sinh_ma_don"]
