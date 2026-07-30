"""Writing to the POS outbox (ADR-0010).

Enqueueing is a plain INSERT that runs inside whatever transaction caused it —
that is the entire point of a transactional outbox. If the payment commits, the
push is guaranteed to be queued; if it rolls back, nothing was queued.

This module imports no adapter and knows no vendor. Business services depend on
it; only ``pos_relay`` ever touches the port.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()

INVOICE = "invoice"
INVOICE_VOID = "invoice_void"
STOCK_MOVEMENT = "stock_movement"


async def enqueue(
    conn: asyncpg.Connection,
    *,
    kind: str,
    subject_id: str,
    payload: dict[str, Any],
    clinic_id: str,
) -> None:
    """Queue one push, inside the caller's transaction.

    Enqueueing the same ``(kind, subject_id)`` twice is a no-op: the unique
    constraint makes retries and re-runs safe, so a re-recorded payment cannot
    become two invoices at the till.
    """
    await conn.execute(
        """
        INSERT INTO pos_outbox (kind, subject_id, payload, clinic_id)
        VALUES ($1, $2::uuid, $3, $4::uuid)
        ON CONFLICT ON CONSTRAINT uq_pos_outbox_subject DO NOTHING
        """,
        kind,
        subject_id,
        json.dumps(payload, default=_json_default),
        clinic_id,
    )
    logger.debug("pos_outbox_enqueued", kind=kind, subject_id=subject_id)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
