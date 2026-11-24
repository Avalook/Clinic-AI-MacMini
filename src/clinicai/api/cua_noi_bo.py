"""Dependency CHUNG của mọi router nội bộ (nhân viên) — `_GUARDED` trong `main.py`.

1. `runaway_guard`: trần số lượt gọi mỗi phút của MỘT nhân viên (xem
   `api/runaway_guard.py`).
2. `ghi_xem_sau_khi_doc` (24/11/2026): cửa đọc hồ sơ khách khai trong
   `api/xem_ho_so.CUA_XEM` trả thành công → một dòng nhật ký xem hồ sơ.

Tách khỏi `main.py` để thêm một cửa chung không làm tệp đó (đã chạm trần kích
thước) dài thêm. Router KHÔNG gắn danh sách này (đăng nhập, đối tác, tivi) xem
chú thích ở `main.py`.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends

from clinicai.api.runaway_guard import runaway_guard
from clinicai.api.xem_ho_so import ghi_xem_sau_khi_doc

CUA_NOI_BO: list[Any] = [Depends(runaway_guard), Depends(ghi_xem_sau_khi_doc)]

__all__ = ["CUA_NOI_BO"]
