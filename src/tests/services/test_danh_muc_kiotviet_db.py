"""Danh mục dịch vụ theo KiotViet (Tuyền chốt 25–26/09/2026 — lát 1).

Mã chuẩn = mã phòng khám (`service_price.ma_kiotviet`); `CLS_*` giữ làm khoá ẩn.
Giá: KV > 0 → KV; KV 0đ → giá viết tay; không có → mã cũ giữ giá, mã mới TRỐNG
(không bao giờ nạp 0đ — nạp 0 là thu 0 đồng).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.config_service import PriceListService
from tests.services.test_xac_nhan_tep_ket_qua_db import CLINIC_A, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _ai() -> Any:
    return SimpleNamespace(clinic_id=CLINIC_A)


async def _dong(pool: asyncpg.Pool, code: str) -> asyncpg.Record | None:  # noqa: F811
    return await pool.fetchrow(
        "SELECT ma_kiotviet, unit_price, name, node_code FROM service_price"
        " WHERE clinic_id = $1::uuid AND \"group\" = 'dich_vu'"
        " AND service_code = $2",
        CLINIC_A,
        code,
    )


async def test_chuan_hoa_gan_ma_gia_va_chay_lai_khong_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    await pool.fetch("SELECT * FROM public.chuan_hoa_danh_muc_dich_vu_kiotviet()")
    hpv = await _dong(pool, "CLS_HPV")
    if hpv is None:
        pytest.skip("phòng khám thử chưa có danh mục CLS_*")
    assert hpv["ma_kiotviet"] == "SP000028"
    assert hpv["unit_price"] == 900000, "KV 0đ → giá viết tay 900k"
    thin = await _dong(pool, "CLS_THINPREP")
    assert thin is not None and thin["unit_price"] is not None, "giữ giá cũ"
    nipt = await _dong(pool, "KV_SP000173")
    assert nipt is not None and nipt["unit_price"] is None, "mới + không giá = TRỐNG"
    leep = await _dong(pool, "KV_SP000093")
    assert leep is not None and leep["unit_price"] == 5000000
    assert leep["node_code"] == "DICHVU-THUTHUAT"
    # Phần tách từ mã cũ theo phòng của mã cũ.
    sbtc = await _dong(pool, "KV_SP000056")
    cha = await _dong(pool, "CLS_SOI_BUONG_TU_CUNG")
    assert sbtc is not None and cha is not None
    assert sbtc["node_code"] == cha["node_code"]
    # Không dòng nào có mã KV mà giá 0.
    assert not await pool.fetchval(
        "SELECT count(*) FROM service_price WHERE ma_kiotviet IS NOT NULL"
        " AND unit_price = 0"
    )
    lan2 = await pool.fetchrow(
        "SELECT * FROM public.chuan_hoa_danh_muc_dich_vu_kiotviet()"
    )
    assert lan2 is not None and (lan2["gan_ma"], lan2["them_moi"]) == (0, 0)


async def test_them_sua_ma_phong_kham_va_phong_lam(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    svc = PriceListService(pool)
    ma = f"T{uuid.uuid4().hex[:8].upper()}"
    phong = await pool.fetchval(
        "SELECT code FROM node_definition WHERE clinic_id = $1::uuid"
        " AND code LIKE 'DICHVU-%' LIMIT 1",
        CLINIC_A,
    )
    pid = await svc.add(
        service_code="",
        name="Dịch vụ thử",
        group="dich_vu",
        unit_price=None,
        identity=_ai(),
        ma_kiotviet=f" {ma.lower()} ",
        node_code=phong,
    )
    d = await _dong(pool, f"KV_{ma}")
    assert d is not None and d["ma_kiotviet"] == ma and d["node_code"] == phong
    with pytest.raises(ConflictError):
        await svc.add(
            service_code="",
            name="Trùng",
            group="dich_vu",
            unit_price=None,
            identity=_ai(),
            ma_kiotviet=ma,
        )
    for rac in ("SP 01; drop", "x" * 40):
        with pytest.raises(ValidationError):
            await svc.update(
                price_id=pid,
                identity=_ai(),
                ma_kiotviet=rac,
                ma_kiotviet_provided=True,
            )
    with pytest.raises(ValidationError):
        await svc.update(price_id=pid, identity=_ai(), node_code="KHONG-CO")
    await svc.update(
        price_id=pid, identity=_ai(), ma_kiotviet="", ma_kiotviet_provided=True
    )
    d = await _dong(pool, f"KV_{ma}")
    assert d is not None and d["ma_kiotviet"] is None, "rỗng = gỡ mã"
