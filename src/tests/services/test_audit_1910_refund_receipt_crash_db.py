"""Read-only audit probe: a lost refund receipt can repeat a partial refund."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import asyncpg
import pytest

from clinicai.api.idempotency import IdempotencyGuard
from clinicai.api.v1.routers.payment import HoanTienRequest, hoan_tien
from tests.services.test_thu_dich_vu_nhieu_lan_db import _quan_ly, _thu, q

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_partial_refund_repeats_after_receipt_write_failure_and_lease_expiry(
    q,  # noqa: F811 -- fixture imported from the payment lifecycle module
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cycle_id = str((await _thu(q))["payment_cycle_id"])
    line_id = str(
        await q.pool.fetchval(
            "SELECT id::text FROM payment_bill_line"
            " WHERE payment_cycle_id=$1::uuid ORDER BY created_at LIMIT 1",
            cycle_id,
        )
    )
    body = HoanTienRequest(
        payment_cycle_id=uuid.UUID(cycle_id),
        visit_id=uuid.UUID(q.visit_id),
        kind="dich_vu",
        method="CASH",
        reason="Khách đổi quyết định một phần",
        dong=[{"payment_bill_line_id": uuid.UUID(line_id), "so_luong": 0.5}],
    )
    key = "audit-refund-" + uuid.uuid4().hex
    endpoint = "POST /api/v1/payments/hoan-tien"
    guard = IdempotencyGuard(key=key, endpoint=endpoint, request_hash="b" * 64)
    manager = await _quan_ly(q)

    with monkeypatch.context() as patch:
        patch.setattr(
            IdempotencyGuard,
            "save",
            AsyncMock(side_effect=RuntimeError("synthetic receipt persistence failure")),
        )
        with pytest.raises(RuntimeError, match="receipt persistence"):
            await hoan_tien(body=body, identity=manager, pool=q.pool, idem=guard)

    first = await q.pool.fetchval(
        "SELECT count(*) FROM payment_refund"
        " WHERE payment_cycle_id=$1::uuid AND status='COMPLETED'",
        cycle_id,
    )
    assert first == 1, "the refund committed before its cached response was saved"
    await q.pool.execute(
        "UPDATE idempotency_key SET updated_at=now()-interval '6 minutes'"
        " WHERE key=$1 AND endpoint=$2 AND actor_id=$3",
        key,
        endpoint,
        manager.auth_user_id,
    )

    result = await hoan_tien(body=body, identity=manager, pool=q.pool, idem=guard)
    assert result["ok"] is True
    refunds = await q.pool.fetch(
        "SELECT refund_id::text, amount FROM payment_refund"
        " WHERE payment_cycle_id=$1::uuid AND status='COMPLETED' ORDER BY created_at",
        cycle_id,
    )
    assert len(refunds) == 2, "the same key and body should have returned one receipt"
    assert len({r["refund_id"] for r in refunds}) == 2
    assert refunds[0]["amount"] == refunds[1]["amount"]

