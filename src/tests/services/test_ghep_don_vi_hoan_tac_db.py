"""Ghép nhiều đơn vị bán với hoàn tác giao và kiểm ca (31/10/2026).

Sổ kho tính theo đơn vị lô, dòng đơn theo đơn vị đã bán. Hai phần làm riêng đều
xanh; lỗi chỉ lộ khi ghép: hoàn tác 30 gói trừ thẳng vào `dispensed_qty` 1 hộp.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

from decimal import Decimal

import pytest

from clinicai.services.kiem_ke_ca_service import giao_chua_gan_lo_theo_don_vi
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_nhieu_don_vi_ban_db import (
    _ban,
    _dong_rx,
    _giao,
    _lo,
    _thu,
    _thu_khong_cho_kho,  # noqa: F401
    _thuoc_goi,
    _ton,
    _xuat,
)
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _huy_phieu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_hoan_tac_giao_hop_doi_dung_ve_don_vi_da_ban(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    lo = await _lo(q, drug, 60)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 1)
    assert await _ton(q, lo) == 30

    (lan,) = await _xuat(q, rx)
    await PharmacyService(q.pool).hoan_tac_giao(
        identity=q.duoc_si, dispense_txn_id=lan["id"], ly_do="Giao nhầm dòng"
    )

    assert await _ton(q, lo) == 60
    assert (await _dong_rx(q, rx))["dispensed_qty"] == 0, "không trừ 30 vào 1 hộp"
    await _giao(q, rx, 1)
    assert await _ton(q, lo) == 30


async def test_hoan_tac_lan_thu_hop_dua_du_thuoc_ve_quay(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    lo = await _lo(q, drug, 60)
    rx = await _ban(q, drug, "1 hộp")
    lan = await _thu(q)
    await _giao(q, rx, 1)

    await _huy_phieu(q, lan["payment_cycle_id"])

    assert await _ton(q, lo) == 60
    assert (await _dong_rx(q, rx))["dispensed_qty"] == 0


async def test_cho_gan_lo_ban_hop_quy_ve_don_vi_dem(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 1)

    async with q.pool.acquire() as conn:
        cho = await giao_chua_gan_lo_theo_don_vi(
            conn, clinic_id=q.duoc_si.clinic_id, location_id=q.duoc_si.location_id
        )
    assert cho[(drug, "gói")] == Decimal(30), "kiểm đếm theo gói, không theo hộp"
