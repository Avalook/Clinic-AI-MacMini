"""G3a: lô chưa biết hạn được nhập/giao, chip xám và FEFO cuối."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

# ruff: noqa: F811
from clinicai.core.clock import hom_nay_vn
from clinicai.services.ban_thuoc_service import man_nha_thuoc
from clinicai.services.pharmacy_service import PharmacyService, kiem_dong_nhap
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_nhap_va_giao_lo_chua_co_han(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, drug = await _dong_da_xac_dinh(q, 3)
    svc = PharmacyService(q.pool)
    nhap = await svc.nhap_lo(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        so_luong=20,
        batch_code=f"KH-{q.duoi}",
        expiry_date=None,
        unit="viên",
    )
    lo = nhap["drug_batch_id"]
    rows = await svc.ton_kho(identity=q.duoc_si)
    batch = next(r for r in rows if r["id"] == lo)
    assert batch["expiry_date"] is None
    assert batch["trang_thai_han"] == "chua_co_han"
    assert batch["canh_bao_han"] is False
    await _thu(q)
    await svc.cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=3
    )
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id=$1::uuid", lo
        )
        == 17
    )


@pytest.mark.parametrize("han", [None, "", "rác", "2026-99-99", object()])
async def test_ngay_rac_tra_rong(han: Any) -> None:
    assert (
        kiem_dong_nhap(so_luong=1, batch_code="A", expiry_date=han, unit="viên")[3]
        is None
    )


async def test_goi_y_fefo_lo_thieu_han_o_cuoi(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, drug = await _dong_da_xac_dinh(q, 3)
    svc = PharmacyService(q.pool)
    nhap = await svc.nhap_lo(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        so_luong=20,
        batch_code=f"KH-{q.duoi}",
        expiry_date=None,
        unit="viên",
    )
    co_han = await _nhap_lo(q, drug, 20, han=hom_nay_vn() + timedelta(days=10))
    het_han = await _nhap_lo(q, drug, 20, han=hom_nay_vn() - timedelta(days=1))
    await _thu(q)
    man = await man_nha_thuoc(q.pool, identity=q.duoc_si)
    dong = next(d for v in man["luot"] for d in v["dong"] if d["id"] == rx)
    ids = [lo["drug_batch_id"] for lo in dong["lo_goi_y"]]
    assert ids == [co_han, nhap["drug_batch_id"]]
    assert het_han not in ids
