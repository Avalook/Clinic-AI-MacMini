"""CLIN-007: dispensing without allocations must still use the ordered drug.

Synthetic fixture and actual main services/triggers, disposable database only.
"""

# ruff: noqa: F811 -- imported pytest fixture follows repository convention.

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import get_current_identity
from clinicai.api.v1.routers import pharmacy as rt
from clinicai.core.database import get_db_pool
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import (
    Quay,
    _nhap_lo,
    _thuoc,
    q,  # noqa: F401
)
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_dispense_rejects_batch_of_another_catalogue_drug(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Turning off stock reservation cannot allow a different medicine."""
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, ordered = await _dong_da_xac_dinh(q, 2)
    other = await _thuoc(q, ten="AUDIT other medicine " + q.duoi)
    assert ordered != other
    batch = await _nhap_lo(q, other, 10)
    await _thu(q)
    with pytest.raises((ValidationError, ConflictError)):
        result = await PharmacyService(q.pool).cap_phat(
            identity=q.duoc_si,
            prescription_id=rx,
            drug_batch_id=batch,
            so_luong=1,
        )
        state = await q.pool.fetchrow(
            "SELECT r.drug_catalog_id::text AS ordered_drug,"
            " b.drug_catalog_id::text AS dispensed_drug,"
            " r.dispensed_qty,b.quantity_on_hand"
            " FROM prescription r JOIN drug_batch b ON b.id=$2::uuid"
            " WHERE r.id=$1::uuid",
            rx,
            batch,
        )
        print(
            json.dumps(
                {"finding": "CLIN-007", "result": result, "state": dict(state)},
                default=str,
            )
        )


async def test_http_dispense_rejects_other_drug_with_real_permission_guard(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep router permissions/validation/idempotency; replace login identity."""
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    rx, ordered = await _dong_da_xac_dinh(q, 2)
    other = await _thuoc(q, ten="AUDIT HTTP other medicine " + q.duoi)
    assert ordered != other
    batch = await _nhap_lo(q, other, 10)
    await _thu(q)
    app = FastAPI()
    app.include_router(rt.router, prefix="/api/v1")

    async def test_pool() -> AsyncIterator[asyncpg.Pool]:
        yield q.pool

    app.dependency_overrides[get_db_pool] = test_pool
    app.dependency_overrides[get_current_identity] = lambda: q.duoc_si
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://audit.local"
    ) as client:
        response = await client.post(
            "/api/v1/pharmacy/dispense",
            json={"prescription_id": rx, "drug_batch_id": batch, "so_luong": 1},
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    print(
        json.dumps(
            {
                "finding": "CLIN-007",
                "http_status": response.status_code,
                "body": response.json(),
            },
            default=str,
        )
    )
    assert response.status_code in {400, 409, 422}
