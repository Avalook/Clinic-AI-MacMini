"""Tham số `xem` cho bài kiểm GỌI THẲNG hàm router (không qua FastAPI).

Cửa đọc hồ sơ nhận `xem: GhiXemHoSo = Depends(ghi_xem_ho_so)` (nhật ký xem hồ
sơ, 24/11/2026). Gọi thẳng hàm thì FastAPI không bơm dependency, `xem` sẽ là đối
tượng `Depends` — phải truyền tay một trong hai thứ dưới đây.
"""

from __future__ import annotations

from typing import Any, cast

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.permissions.y_khoa import GhiXemHoSo


def xem_that(
    pool: asyncpg.Pool, identity: StaffIdentity, cua: str = "GET /thu"
) -> GhiXemHoSo:
    """Ghi thật vào `nhat_ky_xem_ho_so` (bài kiểm có DB)."""
    return GhiXemHoSo(pool, identity, cua)


async def _khong_ghi(*_a: Any, **_k: Any) -> None:
    return None


#: Không ghi gì — bài kiểm đơn vị với pool giả.
KHONG_GHI = cast(GhiXemHoSo, _khong_ghi)
