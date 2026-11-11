"""Cửa ĐỌC sổ thu (lịch sử thu dịch vụ / thuốc, phiếu thu) — không bao giờ cho ghi.

Một câu hỏi, một hàm: "ai xem được TOÀN BỘ sổ thu (mọi ngày, mọi ca — của cơ sở
đang chọn ở thanh trên, đổi bằng "Đổi cơ sở", như Quản lý)?" →
`xem_toan_bo_so_thu`. Trả lời: vai Quản lý, hoặc lego Kế toán
(`accounting.finance.full`) — kế toán cần đối chiếu con số mà không đứng quầy
(chị Hoài, Tuyền duyệt 11/11/2026). Người còn lại đi `CashierScopeService.authorize`
như cũ: chỉ ngày / ca / quầy mình được phân công.

BẪY: KHÔNG gắn hàm này vào `CashierScopeService.authorize` — `authorize_active`
(cửa của lệnh thu / huỷ / hoàn) gọi lại `authorize`, nên mở ở đó là cho kế toán
"đang trực quầy" và ghi được tiền. Lối ghi giữ nguyên, test
`test_so_thu_ke_toan_db.py::test_doc_khong_thanh_quyen_ghi` canh.
"""

from __future__ import annotations

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.permissions.can import can
from clinicai.services.cashier_scope_service import CashierScope, CashierScopeService

QUYEN_XEM_SO_THU = "accounting.finance.full"


async def xem_toan_bo_so_thu(pool: asyncpg.Pool, identity: StaffIdentity) -> bool:
    if identity.co_vai([ClinicRole.MANAGEMENT]):
        return True
    async with pool.acquire() as conn:
        return bool(await can(conn, identity, QUYEN_XEM_SO_THU))


async def pham_vi_doc_so_thu(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    *,
    tu: str | None,
    den: str | None,
    kind: str,
    ca: str | None,
    co_so: str | None,
) -> CashierScope:
    """Phạm vi ĐỌC: xem toàn bộ → không giới hạn; còn lại → ca được phân công."""
    if await xem_toan_bo_so_thu(pool, identity):
        return CashierScope(identity, None, None)
    return await CashierScopeService(pool).authorize(
        identity, tu=tu, den=den, kind=kind, ca=ca, co_so=co_so
    )
