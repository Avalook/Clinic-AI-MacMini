"""DB guard cho luật tiền–thuốc chưa có test trực tiếp trong suite hiện hữu."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import asyncpg
import pytest
import pytest_asyncio

from clinicai.services.phan_lo_service import can_theo_hoa_don
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (
    Quay,
    _don,
    _nhap_lo,
    _thuoc,
    tao_quay,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def quay(pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch) -> Quay:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    return await tao_quay(pool)


async def test_da_cap_theo_luong_cu_chi_phan_con_lai_moi_can_phan_lo(
    quay: Quay,
) -> None:
    """Luật phan_lo_service.can_theo_hoa_don: trừ số thực đã cấp trước đây."""
    prescription_id = await _don(quay, 10, "Thuốc legacy đã cấp")
    drug_id = await _thuoc(quay)
    await PharmacyService(quay.pool).xac_dinh_thuoc(
        identity=quay.duoc_si,
        prescription_id=prescription_id,
        drug_catalog_id=drug_id,
    )
    batch_id = await _nhap_lo(quay, drug_id, 10, han=date(2099, 12, 31))
    legacy_cycle = str(uuid.uuid4())
    await quay.pool.execute(
        "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
        " amount, status, legacy, paid_at, created_at)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, 'thuoc', 50000, 'PAID', true,"
        " now(), now())",
        legacy_cycle,
        CLINIC,
        quay.visit_id,
    )
    await PharmacyService(quay.pool).cap_phat(
        identity=quay.duoc_si,
        prescription_id=prescription_id,
        drug_batch_id=batch_id,
        so_luong=10,
    )

    async with quay.pool.acquire() as conn:
        can = await can_theo_hoa_don(
            conn,
            clinic_id=CLINIC,
            dong=[(prescription_id, "Thuốc legacy đã cấp", Decimal(10))],
        )

    assert can == {}
    assert await quay.pool.fetchval(
        "SELECT dispensed_qty FROM prescription WHERE id = $1::uuid",
        prescription_id,
    ) == 10
