"""Ghép nhiều đơn vị bán với hoàn tác giao và kiểm ca (31/10/2026).

Sổ kho tính theo đơn vị lô, dòng đơn theo đơn vị đã bán. Hai phần làm riêng đều
xanh; lỗi chỉ lộ khi ghép: hoàn tác 30 gói trừ thẳng vào `dispensed_qty` 1 hộp.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.services import theo_doi_thuoc_service as theo_doi
from clinicai.services.kiem_ke_ca_service import giao_chua_gan_lo_theo_don_vi
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_quay_db import (  # noqa: F401
    Co,
    _bat,
    _chuyen,
    _ton_noi,
    co,
)
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


async def test_ban_hop_quay_thieu_gan_lo_tu_kho_va_cau_bao_de_doc(co: Co) -> None:
    """Bấm thật bản gộp: gán từ KHO bị chốt Postgres từ chối vì so sai đơn vị, câu báo
    hiện "0.033333 hộp", Theo dõi thuốc tính sai số trên kệ."""
    await _bat(co)
    drug = await _thuoc_goi(co.q)
    svc = PharmacyService(co.q.pool)
    nhap = await svc.nhap_lo(
        identity=co.ds,
        drug_catalog_id=drug,
        so_luong=59,
        batch_code=f"LO-{uuid.uuid4().hex[:8]}",
        expiry_date=hom_nay_vn() + timedelta(days=400),
        unit="gói",
    )
    lo_kho = str(nhap["drug_batch_id"])
    await _chuyen(co, lo_kho, 29, ly_do=None)
    rx = await _ban(co.q, drug, "1 hộp")
    await _thu(co.q)

    kq = await svc.cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=None, so_luong=1
    )
    assert "1 gói quầy không đủ" in kq["tom_tat"]

    td = await theo_doi.theo_doi_thuoc(co.q.pool, identity=co.ds, thuoc=drug)
    goi = next(x for x in td["dang_o_dau"]["tong"] if x["don_vi"] == "gói")
    assert goi["cho_gan_lo"] == 1 and goi["tren_ke"] == 29, "kho 30 − 1 đã giao"

    async def cho_cua_dong() -> list[dict[str, Any]]:
        ds = (await svc.cho_gan_lo(identity=co.ds))["dong"]
        return [d for d in ds if d["prescription_id"] == rx]

    cho = await cho_cua_dong()
    assert cho[0]["hien"] == "1 gói"
    await svc.gan_lo_da_giao(identity=co.ds, dong_id=cho[0]["id"], drug_batch_id=lo_kho)

    assert await _ton_noi(co, drug) == {"KHO": 29, "QUAY": 0}
    assert not await cho_cua_dong()
