"""Quyền NỘI BỘ `giamsat.view` của đội vận hành ClinicAI (09/10/2026).

Quản lý phòng khám (kể cả có `permission.manage`) không được tự cấp: khối nằm
ngoài mọi preset, màn Phân quyền không bày, service từ chối, và Postgres bỏ mọi
dòng cấp không mang cờ phiên `clinicai.cap_noi_bo`.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.permissions.catalogue import (
    KHOI_AN,
    KHOI_MO_FULL,
    KHOI_NOI_BO,
    PRESET,
    QUYEN,
)
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_khoi_noi_bo_khong_nam_trong_preset_nao() -> None:
    assert QUYEN["giamsat.view"].khoi in KHOI_NOI_BO
    for vai, khoi in PRESET.items():
        assert not (KHOI_NOI_BO & set(khoi)), f"preset {vai} chứa khối nội bộ"
    assert not (KHOI_NOI_BO & set(KHOI_MO_FULL))
    assert KHOI_NOI_BO <= KHOI_AN, "màn Phân quyền phải ẩn khối nội bộ"


class _HuyGiaoDichError(Exception):
    """Huỷ giao dịch cuối bài — DB thử dùng chung, không để lại quyền."""


async def test_postgres_bo_dong_cap_khong_co_co(pool: asyncpg.Pool) -> None:  # noqa: F811
    dem = (
        "SELECT count(*) FROM capability_grant WHERE staff_id = $1::uuid"
        " AND capability = 'giamsat.view' AND revoked_at IS NULL"
    )
    them = (
        "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
        " scope_type, tu_khoi, ly_do) VALUES ($1::uuid, $2::uuid,"
        " 'giamsat.view', 'CLINIC', 'noi_bo_giam_sat', 'thử') ON CONFLICT DO NOTHING"
    )
    with pytest.raises(_HuyGiaoDichError):
        async with pool.acquire() as conn, conn.transaction():
            loc = await conn.fetchval(
                "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
                " ORDER BY id LIMIT 1",
                CLINIC,
            )
            sid = await conn.fetchval(
                "INSERT INTO staff (full_name, primary_department,"
                " primary_location_id, is_active)"
                " VALUES ('Thử quyền nội bộ', 'MANAGEMENT', $1::uuid, true)"
                " RETURNING id::text",
                loc,
            )
            await conn.execute(them, CLINIC, sid)
            assert await conn.fetchval(dem, sid) == 0, "không cờ → Postgres bỏ dòng"
            await conn.execute("SET LOCAL clinicai.cap_noi_bo = 'on'")
            await conn.execute(them, CLINIC, sid)
            assert await conn.fetchval(dem, sid) == 1, "có cờ → cấp được"
            raise _HuyGiaoDichError
