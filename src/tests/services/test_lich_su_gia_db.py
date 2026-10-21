"""Đổi giá phải để vết: ai, lúc nào, giá cũ → giá mới (Tuyền duyệt phiếu A, 21/10/2026).

Hoá đơn tính theo giá LÚC THU (bill_service) — sửa giá 500k → 450k lúc 10:00 thì
khách chỉ định lúc 9:00 ra quầy 11:00 trả 450k. Trước đây không ai trả lời được
"sao 450?": service_price / drug_catalog bị ghi đè, không còn giá cũ. Giờ mỗi lần
giá THẬT SỰ đổi phát sự kiện `gia_dich_vu.da_doi` / `gia_thuoc.da_doi`; màn đọc
"sửa lần cuối" + lịch sử từ đó. Đổi tên, xác nhận lại giá tạm = không sinh dòng.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.services.config_service import PriceListService
from clinicai.services.danh_muc_dich_vu_service import DanhMucDichVuService
from clinicai.services.lich_su_gia import LichSuGiaService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_phieu_kham_db import _nguoi, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _gon(ls: list[dict[str, Any]]) -> list[tuple[str, Any, Any]]:
    return [(x["hanh_dong"], x["gia_cu"], x["gia_moi"]) for x in ls]


async def _ten(pool: asyncpg.Pool, staff_id: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval("SELECT full_name FROM staff WHERE id = $1::uuid", staff_id)
    )


async def test_gia_dich_vu_them_sua_xoa_de_vet(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "PHARMACIST")
    svc = PriceListService(pool)
    pid = await svc.add(
        service_code=f"DV-{uuid.uuid4().hex[:6]}",
        name="Siêu âm thử",
        group="dich_vu",
        unit_price=500000,
        identity=ql,
    )
    await svc.update(
        price_id=pid, identity=ql, unit_price="450000", unit_price_provided=True
    )
    # Bấm lưu lại đúng giá cũ (xác nhận giá tạm) và đổi tên: giá không đổi → không ghi.
    await svc.update(
        price_id=pid, identity=ql, unit_price=450000, unit_price_provided=True
    )
    await svc.update(price_id=pid, identity=ql, name="Siêu âm thử (đổi tên)")

    ls = await LichSuGiaService(pool).doc(identity=ql, loai="dich_vu", id=pid)
    assert _gon(ls) == [("SUA", 500000, 450000), ("THEM", None, 500000)]
    assert ls[0]["boi"] == await _ten(pool, ql.staff_id)
    assert ls[0]["luc"]

    dong = {str(r["id"]): r for r in await svc.list(group="dich_vu", identity=ql)}[pid]
    assert (dong["gia_sua_cuoi"]["gia_cu"], dong["gia_sua_cuoi"]["gia_moi"]) == (
        500000,
        450000,
    )
    dm = await DanhMucDichVuService(pool).doc(identity=ql)
    dong_dm = {str(d["id"]): d for d in dm["dich_vu"]}[pid]
    assert dong_dm["gia_sua_cuoi"]["gia_moi"] == 450000

    await svc.remove(price_id=pid, identity=ql)
    ls = await LichSuGiaService(pool).doc(identity=ql, loai="dich_vu", id=pid)
    assert _gon(ls)[0] == ("XOA", 450000, None), "xoá dòng vẫn còn vết giá cuối"


async def test_gia_vat_tu_cung_de_vet(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "PHARMACIST")
    svc = PriceListService(pool)
    pid = await svc.add(
        service_code="",
        name=f"Găng tay thử {uuid.uuid4().hex[:6]}",
        group="vat_tu",
        unit_price=2000,
        identity=ql,
    )
    await svc.update(
        price_id=pid, identity=ql, unit_price=2500, unit_price_provided=True
    )
    dm = await DanhMucDichVuService(pool).doc(identity=ql)
    dong = {str(d["id"]): d for d in dm["vat_tu"]}[pid]
    assert (dong["gia_sua_cuoi"]["gia_cu"], dong["gia_sua_cuoi"]["gia_moi"]) == (
        2000,
        2500,
    )


async def test_gia_thuoc_kho_de_vet(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        ds = await _nguoi(conn, "PHARMACIST")
    svc = PharmacyService(pool)
    ten = f"Thuốc giá thử {uuid.uuid4().hex[:6]}"
    kq = await svc.luu_thuoc(identity=ds, drug_catalog_id=None, ten=ten, gia="50000")
    await svc.luu_thuoc(identity=ds, drug_catalog_id=kq["id"], ten=ten, gia=80000)
    # Sửa hướng dẫn, giá giữ nguyên → không thêm dòng lịch sử giá.
    await svc.luu_thuoc(
        identity=ds, drug_catalog_id=kq["id"], ten=ten, gia=80000, cach_dung="Sáng 1v"
    )
    ls = await LichSuGiaService(pool).doc(identity=ds, loai="thuoc", id=kq["id"])
    assert _gon(ls) == [("SUA", 50000, 80000), ("THEM", None, 50000)]
    dong = {d["id"]: d for d in await svc.danh_muc(identity=ds)}[kq["id"]]
    assert dong["gia_sua_cuoi"]["boi"] == await _ten(pool, ds.staff_id)
    assert dong["gia_sua_cuoi"]["gia_moi"] == 80000


async def test_bang_gia_thuoc_keo_danh_muc_cung_de_vet(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "PHARMACIST")
    ten = f"Thuốc kéo giá {uuid.uuid4().hex[:6]}"
    kq = await PharmacyService(pool).luu_thuoc(
        identity=ql, drug_catalog_id=None, ten=ten, gia=100000
    )
    await PriceListService(pool).add(
        service_code=f"T-{uuid.uuid4().hex[:6]}",
        name=ten,
        group="thuoc",
        unit_price=120000,
        identity=ql,
    )
    ls = await LichSuGiaService(pool).doc(identity=ql, loai="thuoc", id=kq["id"])
    assert _gon(ls)[0] == ("SUA", 100000, 120000), "kho đổi theo bảng giá cũng có vết"
