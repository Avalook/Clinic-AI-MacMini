"""Chạy một lệnh bàn XN trong MỘT giao dịch (router chỉ gọi đây — router mỏng)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn

LenhCoNgay = Callable[
    [asyncpg.Connection, StaffIdentity, dict[str, Any], date], Awaitable[Any]
]
LenhKhongNgay = Callable[
    [asyncpg.Connection, StaffIdentity, dict[str, Any]], Awaitable[Any]
]


async def chay(
    pool: asyncpg.Pool, identity: StaffIdentity, ham: LenhCoNgay, data: dict[str, Any]
) -> Any:
    async with pool.acquire() as conn, conn.transaction():
        return await ham(conn, identity, data, hom_nay_vn())


async def chay_khong_ngay(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    ham: LenhKhongNgay,
    data: dict[str, Any],
) -> Any:
    async with pool.acquire() as conn, conn.transaction():
        return await ham(conn, identity, data)
