"""Các khoảng trống phát hiện khi chạy thử hai kho trên dữ liệu thật của DB test."""

import uuid
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.services.config_service import PriceListService
from clinicai.services.danh_muc_dich_vu_service import doc_vat_tu
from clinicai.services.vat_tu_kho_man_service import doc_phieu
from clinicai.services.vat_tu_kho_service import doc_ton, hoan_phieu, tao_phieu
from tests.services.test_vat_tu_kho_db import _bo, _ghi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_tao_danh_muc_du_metadata_va_tam_ngung_giu_so(pool: asyncpg.Pool) -> None:
    ai, _, rooms = await _bo(pool)
    vt = await PriceListService(pool).add(
        identity=ai,
        service_code="",
        name=f"Vật tư audit {uuid.uuid4().hex}",
        group="vat_tu",
        unit_price="75000",
        vat_tu={
            "loai_vat_tu": "VPP",
            "don_vi": "hộp",
            "gia_nhap": "50000",
            "ma_vach": "AUDIT-01",
            "kinh_doanh": True,
            "can_duyet_nhap": True,
            "can_ql_duyet": True,
        },
    )
    async with pool.acquire() as conn:
        row = next(r for r in await doc_vat_tu(conn, ai.clinic_id) if r["id"] == vt)
    assert row["loai_vat_tu"] == "VPP" and row["don_vi"] == "hộp"
    assert row["gia_nhap"] == 50000 and row["unit_price"] == 75000
    assert row["kinh_doanh"] and row["can_duyet_nhap"] and row["can_ql_duyet"]
    await PriceListService(pool).update(
        price_id=vt, identity=ai, vat_tu={"can_duyet_nhap": False}
    )
    p = await _ghi(pool, ai, vt, "NHAP", den=rooms[0], so=7)
    await PriceListService(pool).update(price_id=vt, identity=ai, active=False)
    assert any(
        t["vat_tu_id"] == vt and t["so_luong"] == 7
        for t in await doc_ton(pool, identity=ai)
    )
    await hoan_phieu(pool, identity=ai, phieu_id=p["id"], khoa_gui=uuid.uuid4().hex)
    assert all(
        t["so_luong"] == 0
        for t in await doc_ton(pool, identity=ai)
        if t["vat_tu_id"] == vt
    )


async def test_gia_tri_uoc_tinh_tu_phieu_khong_tu_gia_danh_muc(
    pool: asyncpg.Pool,
) -> None:
    ai, vt, rooms = await _bo(pool)
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=1000 WHERE id=$1::uuid", vt
    )

    async def nhap(gia: int) -> dict[str, Any]:
        return await tao_phieu(
            pool,
            identity=ai,
            khoa_gui=uuid.uuid4().hex,
            loai="NHAP",
            dong=[{"vat_tu_id": vt, "so_luong": 10, "gia_nhap": gia}],
        )

    await nhap(50000)
    await _ghi(pool, ai, vt, "XUAT_PHONG", den=rooms[0], so=3)

    async def ton() -> dict[str | None, dict[str, Any]]:
        return {
            t["room_id"]: t
            for t in await doc_ton(pool, identity=ai)
            if t["vat_tu_id"] == vt
        }

    t = await ton()
    assert t[None]["gia_tri_ton"] == Decimal(350000)
    assert t[rooms[0]]["gia_tri_ton"] == Decimal(150000)
    p = await nhap(80000)
    assert (await ton())[rooms[0]]["gia_nhap_tham_chieu"] == Decimal(80000)
    await hoan_phieu(pool, identity=ai, phieu_id=p["id"], khoa_gui=uuid.uuid4().hex)
    assert (await ton())[rooms[0]]["gia_tri_ton"] == Decimal(150000)


async def test_lich_su_doc_duoc_phieu_cu_hon_200(pool: asyncpg.Pool) -> None:
    ai, vt, _ = await _bo(pool)
    ids = [(await _ghi(pool, ai, vt, "NHAP", so=1))["id"] for _ in range(205)]
    ds = []
    for offset in range(0, 250, 50):
        ds.extend(await doc_phieu(pool, identity=ai, gioi_han=50, bo_qua=offset))
    assert set(ids) <= {p["id"] for p in ds}
    assert len({p["id"] for p in ds}) == len(ds)
