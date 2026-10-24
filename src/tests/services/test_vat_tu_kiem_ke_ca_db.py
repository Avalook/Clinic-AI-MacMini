"""Bất biến kiểm kê đầu/cuối ca vật tư theo từng phòng."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import vat_tu_kiem_ke_ca_service as kk
from tests.services.test_vat_tu_kho_db import _bo, _ghi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_mo_lap_lai_luu_dem_chot_va_khong_doi_ton(pool: asyncpg.Pool) -> None:
    identity, vat_tu, rooms = await _bo(pool)
    room = rooms[0]
    await _ghi(pool, identity, vat_tu, "NHAP", den=room, so=10)
    args: dict[str, Any] = {
        "pool": pool,
        "identity": identity,
        "room_id": room,
        "ngay": hom_nay_vn().isoformat(),
        "ca": "SANG",
        "loai": "DAU",
    }
    p = await kk.mo_phieu(**args)
    again = await kk.mo_phieu(**args)
    assert p["id"] == again["id"]
    assert p["trang_thai"] == "NHAP" and p["dong"][0]["dem"] is None

    saved = await kk.luu_dem(
        pool,
        identity=identity,
        phieu_id=p["id"],
        dong=[{"vat_tu_id": vat_tu, "dem": "8"}],
    )
    assert saved["dong"][0]["dem"] == Decimal(8)
    before = await pool.fetchval(
        "SELECT so_luong FROM public.vat_tu_ton WHERE vat_tu_id=$1::uuid"
        " AND room_id=$2::uuid",
        vat_tu,
        room,
    )
    result = await kk.chot(pool, identity=identity, phieu_id=p["id"])
    item = result["dong"][0]
    assert result["trang_thai"] == "CHOT"
    assert item["ton_may"] == Decimal(10)
    assert item["lech"] == Decimal(-2)
    assert (
        await pool.fetchval(
            "SELECT so_luong FROM public.vat_tu_ton WHERE vat_tu_id=$1::uuid"
            " AND room_id=$2::uuid",
            vat_tu,
            room,
        )
        == before
        == Decimal(10)
    )
    with pytest.raises(ConflictError):
        await kk.luu_dem(
            pool,
            identity=identity,
            phieu_id=p["id"],
            dong=[{"vat_tu_id": vat_tu, "dem": 10}],
        )


async def test_kiem_ke_chi_gom_vat_tu_cua_phong_da_chon(pool: asyncpg.Pool) -> None:
    identity, vat_tu, rooms = await _bo(pool)
    await _ghi(pool, identity, vat_tu, "NHAP", den=rooms[0], so=4)
    await _ghi(pool, identity, vat_tu, "NHAP", den=rooms[1], so=7)
    p = await kk.mo_phieu(
        pool,
        identity=identity,
        room_id=rooms[0],
        ngay=hom_nay_vn().isoformat(),
        ca="CHIEU",
        loai="CUOI",
    )
    assert [row["vat_tu_id"] for row in p["dong"]] == [vat_tu]
    with pytest.raises(NotFoundError):
        await kk.luu_dem(
            pool,
            identity=identity,
            phieu_id=p["id"],
            dong=[{"vat_tu_id": str(uuid4()), "dem": 1}],
        )
