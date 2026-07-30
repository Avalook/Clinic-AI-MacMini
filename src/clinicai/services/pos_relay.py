"""Draining the POS outbox (ADR-0010).

Runs outside the transaction that produced the work, so the till is never
waiting on a third party. Each row is claimed with an advisory lock — the same
technique the notification relay uses — so two relays can run without
double-pushing.

Retries back off exponentially and stop at ``max_attempts``, after which the row
becomes DEAD. Dead-lettering is the honest end state: the money was taken, the
POS was not told, and somebody has to look. Failing silently or retrying for
ever would both hide that.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.adapters.pos.null import NullPosAdapter
from clinicai.ports.pos import (
    PosDeliveryError,
    PosInvoice,
    PosInvoiceLine,
    PosPort,
    PosStockMovement,
)
from clinicai.services import pos_outbox
from clinicai.services.pos_config import build_adapter

logger = structlog.get_logger()

BATCH_SIZE = 50
# 1st retry after a minute, then 5, 25, 125 ... capped by max_attempts.
BACKOFF_BASE_SECONDS = 60
BACKOFF_FACTOR = 5


async def poll_and_push(pool: asyncpg.Pool, adapter: PosPort | None = None) -> int:
    """Deliver everything that is due. Returns how many rows were sent."""
    sent = 0

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT o.id, o.clinic_id, o.kind, o.subject_id, o.payload,
                   o.attempts, o.max_attempts, c.settings
              FROM pos_outbox o
              JOIN clinic c ON c.id = o.clinic_id
             WHERE o.status = 'PENDING'
               AND o.next_attempt_at <= now()
             ORDER BY o.created_at
             LIMIT $1
            """,
            BATCH_SIZE,
        )
        if not rows:
            return 0

        for row in rows:
            claimed = await conn.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1::text, 0))",
                str(row["id"]),
            )
            if not claimed:
                continue
            try:
                cycle_lock = pos_outbox.causal_lock_name(str(row["subject_id"]))
                await conn.execute(
                    "SELECT pg_advisory_lock(hashtextextended($1::text, 0))",
                    cycle_lock,
                )
                try:
                    # Another relay or a payment void may have finished or
                    # cancelled this row between the SELECT and both locks.
                    still_pending = await conn.fetchval(
                        "SELECT status = 'PENDING' FROM pos_outbox WHERE id = $1",
                        row["id"],
                    )
                    if not still_pending:
                        continue

                    port = adapter or build_adapter(_as_dict(row["settings"]))
                    if await _deliver(conn, row, port):
                        sent += 1
                finally:
                    await conn.execute(
                        "SELECT pg_advisory_unlock(hashtextextended($1::text, 0))",
                        cycle_lock,
                    )
            finally:
                await conn.execute(
                    "SELECT pg_advisory_unlock(hashtextextended($1::text, 0))",
                    str(row["id"]),
                )

    logger.info("pos_relay_poll_complete", sent=sent, considered=len(rows))
    return sent


async def _deliver(
    conn: asyncpg.Connection, row: asyncpg.Record, port: PosPort
) -> bool:
    if isinstance(port, NullPosAdapter):
        await _dead_letter(
            conn,
            row,
            "POS adapter đang tắt hoặc cấu hình sai; chưa gửi dữ liệu ra POS",
        )
        return False

    payload = _as_dict(row["payload"])
    kind = row["kind"]

    try:
        if kind == pos_outbox.INVOICE:
            external_ref = await port.push_invoice(_invoice_from(payload))
        elif kind == pos_outbox.INVOICE_VOID:
            await port.void_invoice(str(payload.get("clinic_reference", "")))
            external_ref = None
        elif kind == pos_outbox.STOCK_MOVEMENT:
            external_ref = await port.push_stock_movement(_movement_from(payload))
        else:
            # An unknown kind will never become known by waiting.
            await _dead_letter(conn, row, f"Loại đẩy POS không hỗ trợ: {kind}")
            return False
    except PosDeliveryError as exc:
        if exc.retryable:
            await _schedule_retry(conn, row, str(exc))
        else:
            await _dead_letter(conn, row, str(exc))
        return False
    except Exception as exc:  # noqa: BLE001 — an adapter must not stop the relay
        logger.exception("pos_relay_adapter_crashed", kind=kind, error=str(exc))
        await _schedule_retry(conn, row, str(exc))
        return False

    await conn.execute(
        """
        UPDATE pos_outbox
           SET status = 'SENT', sent_at = now(), external_ref = $2,
               attempts = attempts + 1, last_error = NULL, updated_at = now()
         WHERE id = $1
        """,
        row["id"],
        external_ref,
    )
    logger.info(
        "pos_pushed",
        kind=kind,
        subject_id=str(row["subject_id"]),
        adapter=getattr(port, "name", "?"),
        external_ref=external_ref,
    )
    return True


async def _schedule_retry(
    conn: asyncpg.Connection, row: asyncpg.Record, error: str
) -> None:
    attempts = row["attempts"] + 1
    if attempts >= row["max_attempts"]:
        await _dead_letter(conn, row, error, attempts=attempts)
        return

    delay = BACKOFF_BASE_SECONDS * (BACKOFF_FACTOR ** (attempts - 1))
    await conn.execute(
        """
        UPDATE pos_outbox
           SET attempts = $2,
               last_error = $3,
               next_attempt_at = now() + make_interval(secs => $4),
               updated_at = now()
         WHERE id = $1
        """,
        row["id"],
        attempts,
        error[:1000],
        float(delay),
    )
    logger.warning(
        "pos_push_retry_scheduled",
        subject_id=str(row["subject_id"]),
        attempts=attempts,
        retry_in_s=delay,
    )


async def _dead_letter(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    error: str,
    *,
    attempts: int | None = None,
) -> None:
    await conn.execute(
        """
        UPDATE pos_outbox
           SET status = 'DEAD', attempts = $2, last_error = $3, updated_at = now()
         WHERE id = $1
        """,
        row["id"],
        attempts if attempts is not None else row["attempts"] + 1,
        error[:1000],
    )
    # The money moved and the POS does not know. That is an operations problem,
    # so it is logged at error level and left visible in the table.
    logger.error(
        "pos_push_dead_lettered",
        subject_id=str(row["subject_id"]),
        kind=row["kind"],
        error=error,
    )


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return value or {}


def _invoice_from(payload: dict[str, Any]) -> PosInvoice:
    return PosInvoice(
        clinic_reference=str(payload.get("clinic_reference", "")),
        kind=str(payload.get("kind", "")),
        total_amount=float(payload.get("total_amount") or 0),
        paid_at=_parse_time(payload.get("paid_at")),
        patient_reference=payload.get("patient_reference"),
        lines=[
            PosInvoiceLine(
                code=str(line.get("code", "")),
                name=str(line.get("name", "")),
                quantity=float(line.get("quantity") or 0),
                unit_price=float(line.get("unit_price") or 0),
            )
            for line in payload.get("lines") or []
        ],
        note=payload.get("note"),
    )


def _movement_from(payload: dict[str, Any]) -> PosStockMovement:
    return PosStockMovement(
        clinic_reference=str(payload.get("clinic_reference", "")),
        product_code=str(payload.get("product_code", "")),
        quantity=float(payload.get("quantity") or 0),
        direction=str(payload.get("direction", "out")),
        occurred_at=_parse_time(payload.get("occurred_at")),
        note=payload.get("note"),
    )


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)
    return datetime.now()
