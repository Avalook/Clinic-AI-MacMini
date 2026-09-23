"""Sửa giá thuốc ở màn Bảng giá thuốc → danh mục thuốc cùng tên đi theo (24/09).

Hoá đơn lấy giá thuốc ở CẢ `drug_catalog` lẫn `service_price` nhóm thuốc (HOLD
J5); lệch nhau là dòng "mâu thuẫn giá", quầy không thu được. Màn chỉ sửa được
`service_price`, nên sửa ở đó phải kéo danh mục theo — không thì tự khoá quầy.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import asyncpg
import pytest

from clinicai.services.config_service import PriceListService
from tests.services.test_xac_nhan_tep_ket_qua_db import CLINIC_A, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _ai() -> Any:
    return SimpleNamespace(clinic_id=CLINIC_A)


async def _thuoc(pool: asyncpg.Pool, ten: str, gia: int | None) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price)"
            " VALUES ($1::uuid, $2, $2, $3) RETURNING id",
            CLINIC_A,
            ten,
            gia,
        )
    )


async def _gia_danh_muc(pool: asyncpg.Pool, dc: str) -> Any:  # noqa: F811
    return await pool.fetchval("SELECT unit_price FROM drug_catalog WHERE id = $1", dc)


async def test_sua_gia_thuoc_tren_man_keo_danh_muc_theo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ten = f"Thuốc thử {uuid.uuid4().hex[:6]}"
    dc = await _thuoc(pool, ten, 100000)
    svc = PriceListService(pool)
    pid = await svc.add(
        service_code=f"T-{uuid.uuid4().hex[:6]}",
        name=ten,
        group="thuoc",
        unit_price=120000,
        identity=_ai(),
    )
    assert await _gia_danh_muc(pool, dc) == 120000
    await svc.update(
        price_id=pid, identity=_ai(), unit_price=135000, unit_price_provided=True
    )
    assert await _gia_danh_muc(pool, dc) == 135000


async def test_gia_dich_vu_khong_dung_danh_muc_thuoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ten = f"Trùng tên {uuid.uuid4().hex[:6]}"
    dc = await _thuoc(pool, ten, 50000)
    await PriceListService(pool).add(
        service_code=f"D-{uuid.uuid4().hex[:6]}",
        name=ten,
        group="dich_vu",
        unit_price=90000,
        identity=_ai(),
    )
    assert await _gia_danh_muc(pool, dc) == 50000
