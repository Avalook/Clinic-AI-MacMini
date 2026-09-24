"""Cửa QUYỀN cho router — thay `require_role(...)` (24/09/2026).

`require_role(ClinicRole.X, ...)` ở router là hàng rào theo VAI: quản lý cấp
quyền cho một người khác vai thì người ấy vẫn ăn 403 ở cửa ngoài (bấm thật đã
gặp: điều dưỡng có quyền chỉ định mà router chỉ định chặn). Cửa này hỏi đúng
câu `can(...)` mà lệnh hỏi, nên cấp quyền trên màn Phân quyền là có hiệu lực
ngay ở mọi lớp.

Nhận NHIỀU quyền = có một trong số đó là qua (vd màn đọc nhà thuốc: người giao
thuốc hoặc người chỉ xem). Lệnh ghi bên trong vẫn tự kiểm lại quyền của nó.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import asyncpg
from fastapi import Depends

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import tra_quyen


def cua_quyen(
    *quyen: str, cau: str | None = None
) -> Callable[..., Awaitable[StaffIdentity]]:
    """Dependency FastAPI: đi qua khi người gọi có ÍT NHẤT một quyền trong số."""
    for q in quyen:
        tra_quyen(q)  # tên sai thì hỏng lúc nạp module, không lúc có người bấm

    async def _cua(
        identity: StaffIdentity = Depends(get_current_identity),
        pool: asyncpg.Pool = Depends(get_db_pool),
    ) -> StaffIdentity:
        async with pool.acquire() as conn:
            for q in quyen:
                if await can(conn, identity, q):
                    return identity
        ten = " hoặc ".join(f"“{tra_quyen(q).ten}”" for q in quyen)
        raise SafetyGateError(cau or f"Bạn chưa được cấp quyền {ten}.")

    return _cua


__all__ = ["cua_quyen"]
