"""G3a: mọi đường gắn/giao trả ConflictError tiếng Việt khi lô hết hạn."""

from __future__ import annotations

# ruff: noqa: F811
import asyncio
from datetime import timedelta

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.core.clock import hom_nay_vn
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _dong_da_xac_dinh,
    _huy_phieu,
    _san_sang,
    _thu,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_het_han_409_giao_va_gan_sau(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, drug = await _dong_da_xac_dinh(q, 3)
    lo = await _nhap_lo(q, drug, 20, han=hom_nay_vn() - timedelta(days=1))
    svc = PharmacyService(q.pool)
    await _thu(q)
    with pytest.raises(ConflictError, match="hết hạn"):
        await svc.cap_phat(
            identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=1
        )
    await svc.cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=1
    )
    dong = await q.pool.fetchval(
        "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE prescription_id=$1::uuid", rx
    )
    with pytest.raises(ConflictError, match="hết hạn"):
        await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong, drug_batch_id=lo)
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id=$1::uuid", lo
        )
        == 20
    )


async def test_han_hom_nay_van_giao_duoc(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, drug = await _dong_da_xac_dinh(q, 3)
    lo = await _nhap_lo(q, drug, 20, han=hom_nay_vn())
    await _thu(q)
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=1
    )
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id=$1::uuid", lo
        )
        == 19
    )


async def test_db_chan_ghi_so_lo_het_han(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, drug = await _dong_da_xac_dinh(q, 3)
    lo = await _nhap_lo(q, drug, 20, han=hom_nay_vn())
    await _thu(q)
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=1
    )
    await q.pool.execute(
        "UPDATE drug_batch SET expiry_date=$2 WHERE id=$1::uuid",
        lo,
        hom_nay_vn() - timedelta(days=1),
    )
    with pytest.raises(asyncpg.ExclusionViolationError, match="hết hạn"):
        await q.pool.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity, "
            "ref_type, ref_id, performed_by_staff_id, payment_cycle_id, allocation_id) "
            "SELECT clinic_id, drug_batch_id, txn_type, quantity, ref_type, ref_id, "
            "performed_by_staff_id, payment_cycle_id, allocation_id FROM inventory_txn "
            "WHERE drug_batch_id=$1::uuid AND txn_type='DISPENSE' LIMIT 1",
            lo,
        )
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id=$1::uuid", lo
        )
        == 19
    )


async def test_sua_han_cung_luc_giao_khoa_cung_lo(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, drug = await _dong_da_xac_dinh(q, 3)
    lo = await _nhap_lo(q, drug, 20, han=hom_nay_vn())
    await _thu(q)
    async with q.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE drug_batch SET expiry_date=$2 WHERE id=$1::uuid",
                lo,
                hom_nay_vn() - timedelta(days=1),
            )
            giao = asyncio.create_task(
                PharmacyService(q.pool).cap_phat(
                    identity=q.duoc_si,
                    prescription_id=rx,
                    drug_batch_id=lo,
                    so_luong=1,
                )
            )
            await asyncio.sleep(0.05)
            assert not giao.done()
    with pytest.raises(ConflictError, match="hết hạn"):
        await asyncio.wait_for(giao, timeout=5)
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id=$1::uuid", lo
        )
        == 20
    )


async def test_huy_phieu_lo_da_het_han_van_dao_ban_duoc(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    _, _, lo = await _san_sang(q)
    lan = await _thu(q)
    await q.pool.execute(
        "UPDATE drug_batch SET expiry_date=$2 WHERE id=$1::uuid",
        lo,
        hom_nay_vn() - timedelta(days=1),
    )
    await _huy_phieu(q, lan["payment_cycle_id"])
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE drug_batch_id=$1::uuid "
            "AND txn_type='SALE_REVERSAL'",
            lo,
        )
        == 1
    )
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id=$1::uuid",
            lo,
        )
        == 100
    )
