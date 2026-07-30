"""How the POS relay reacts when a till misbehaves (W7, ADR-0010).

The promise being tested is the one that matters to a cashier: the money is
already taken, so nothing the POS does may lose the push or hide the failure.
A connection problem must be retried, a rejection must go to the dead-letter
state where somebody sees it, and an adapter that raises something unexpected
must not take the relay down with it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.ports.pos import PosCatalogItem, PosDeliveryError, PosInvoice
from clinicai.services import pos_outbox, pos_relay


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "id": "11111111-1111-4111-8111-111111111111",
        "clinic_id": "a0000000-0000-4000-8000-000000000001",
        "kind": pos_outbox.INVOICE,
        "subject_id": "22222222-2222-4222-8222-222222222222",
        "payload": json.dumps(
            {
                "clinic_reference": "pay-1",
                "kind": "dich_vu",
                "total_amount": 250000,
                "paid_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        "attempts": 0,
        "max_attempts": 5,
        "settings": {},
    }
    row.update(overrides)
    return row


class _Adapter:
    """A POS that behaves however the test needs it to."""

    name = "fake"

    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.invoices: list[PosInvoice] = []

    async def push_invoice(self, invoice: PosInvoice) -> str | None:
        if self._raises:
            raise self._raises
        self.invoices.append(invoice)
        return "POS-123"

    async def void_invoice(self, clinic_reference: str) -> None:
        if self._raises:
            raise self._raises

    async def push_stock_movement(self, movement: Any) -> str | None:
        if self._raises:
            raise self._raises
        return None

    async def pull_catalog(self) -> list[PosCatalogItem]:
        return []


def _statements(conn: MagicMock) -> str:
    return " ".join(str(call.args[0]) for call in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_success_marks_sent_and_keeps_the_external_reference() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()
    adapter = _Adapter()

    assert await pos_relay._deliver(conn, _row(), adapter) is True

    sql = _statements(conn)
    assert "status = 'SENT'" in sql
    assert conn.execute.await_args_list[0].args[2] == "POS-123"
    assert adapter.invoices[0].total_amount == 250000


@pytest.mark.asyncio
async def test_a_retryable_failure_is_rescheduled_not_lost() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()

    delivered = await pos_relay._deliver(
        conn, _row(), _Adapter(raises=PosDeliveryError("timeout", retryable=True))
    )

    assert delivered is False
    sql = _statements(conn)
    assert "next_attempt_at" in sql and "DEAD" not in sql


@pytest.mark.asyncio
async def test_a_rejection_goes_straight_to_the_dead_letter_state() -> None:
    # Retrying a rejected invoice four more times just delays the moment a human
    # finds out that the till never heard about the money.
    conn = MagicMock()
    conn.execute = AsyncMock()

    delivered = await pos_relay._deliver(
        conn, _row(), _Adapter(raises=PosDeliveryError("rejected", retryable=False))
    )

    assert delivered is False
    assert "status = 'DEAD'" in _statements(conn)


@pytest.mark.asyncio
async def test_the_last_attempt_dead_letters_rather_than_retrying_for_ever() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()

    await pos_relay._deliver(
        conn,
        _row(attempts=4, max_attempts=5),
        _Adapter(raises=PosDeliveryError("still down", retryable=True)),
    )

    assert "status = 'DEAD'" in _statements(conn)


@pytest.mark.asyncio
async def test_an_adapter_that_explodes_does_not_stop_the_relay() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()

    delivered = await pos_relay._deliver(
        conn, _row(), _Adapter(raises=ValueError("vendor SDK blew up"))
    )

    assert delivered is False
    assert "next_attempt_at" in _statements(conn)


@pytest.mark.asyncio
async def test_an_unknown_kind_is_dead_lettered_immediately() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()

    delivered = await pos_relay._deliver(conn, _row(kind="teleport"), _Adapter())

    assert delivered is False
    assert "status = 'DEAD'" in _statements(conn)


class TestBackoff:
    def test_delays_grow(self) -> None:
        # 1 min, 5, 25, 125 — long enough to ride out an outage, short enough
        # that a same-day fix still drains the queue that day.
        delays = [
            pos_relay.BACKOFF_BASE_SECONDS * (pos_relay.BACKOFF_FACTOR ** (n - 1))
            for n in range(1, 5)
        ]
        assert delays == [60, 300, 1500, 7500]
