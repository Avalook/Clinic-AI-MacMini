"""Lệnh của màn Cài đặt → Đối tác: mỗi lệnh một giao dịch, trả lại danh sách mới.

Router chỉ chuyển tiếp; luật nằm ở `doi_tac.py`. Quyền `config.clinic.manage` gác ở
router (`cua_quyen`) — chỉ Quản lý (câu F, mục 2.I).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.services.xet_nghiem import doi_tac as dt


class CaiDatDoiTac:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def danh_sach(self, identity: StaffIdentity) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            return await dt.danh_sach(conn, identity.clinic_id)

    async def _ghi(
        self,
        identity: StaffIdentity,
        lam: Callable[[asyncpg.Connection], Awaitable[object]],
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await lam(conn)
            return await dt.danh_sach(conn, identity.clinic_id)

    async def luu_doi_tac(
        self, identity: StaffIdentity, data: dict[str, Any], doi_tac_id: str | None
    ) -> dict[str, Any]:
        return await self._ghi(
            identity, lambda c: dt.luu_doi_tac(c, identity, data, doi_tac_id)
        )

    async def ngung(
        self, identity: StaffIdentity, doi_tac_id: str, ngung: bool, ly_do: str | None
    ) -> dict[str, Any]:
        return await self._ghi(
            identity,
            lambda c: dt.ngung_doi_tac(
                c, identity, doi_tac_id, ngung=ngung, ly_do=ly_do
            ),
        )

    async def gan(
        self, identity: StaffIdentity, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._ghi(identity, lambda c: dt.luu_anh_xa(c, identity, data))

    async def bo_gan(self, identity: StaffIdentity, anh_xa_id: str) -> dict[str, Any]:
        return await self._ghi(identity, lambda c: dt.bo_anh_xa(c, identity, anh_xa_id))

    async def nguong(self, identity: StaffIdentity, so_ngay: object) -> dict[str, Any]:
        return await self._ghi(identity, lambda c: dt.luu_nguong(c, identity, so_ngay))
