"""Audit FIN-004: split refunds must not exceed the actual collected amount.

The regression assertion is intentionally RED on the pinned main before a fix.
Uses synthetic data and the repository's ephemeral database runner only.
"""

# ruff: noqa: F811 -- imported pytest fixture follows repository convention.

from __future__ import annotations

from decimal import Decimal

import pytest

from clinicai.services.hoan_tien_service import HoanTienService
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_split_refunds_never_exceed_original_collected_amount(
    q: Quay,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    _, drug = await _dong_da_xac_dinh(q, 1)
    await q.pool.execute(
        "UPDATE drug_catalog SET unit_price=100001 WHERE id=$1::uuid", drug
    )
    cycle = (await _thu(q))["payment_cycle_id"]
    line = await q.pool.fetchval(
        "SELECT id::text FROM payment_bill_line"
        " WHERE payment_cycle_id=$1::uuid AND source_type='prescription'",
        cycle,
    )
    service = HoanTienService(q.pool)
    for _ in range(2):
        await service.tao(
            identity=q.thu_ngan,
            payment_cycle_id=cycle,
            visit_id=q.visit_id,
            kind="thuoc",
            dong=[{"payment_bill_line_id": line, "so_luong": Decimal("0.5")}],
            method="CASH",
            reason="Synthetic audit: refund half of the original item",
        )
    state = await q.pool.fetchrow(
        "SELECT c.amount AS collected,"
        " (SELECT sum(r.amount) FROM payment_refund r"
        "   WHERE r.payment_cycle_id=c.payment_cycle_id"
        "     AND r.status IN ('PENDING','COMPLETED')) AS refunded"
        " FROM payment_cycle c WHERE c.payment_cycle_id=$1::uuid",
        cycle,
    )
    assert state["refunded"] <= state["collected"], (
        f"Refunded {state['refunded']} exceeds collected {state['collected']}"
    )
