"""Worker entrypoint — two modes of operation.

Mode 1 (default): RabbitMQ consumer (opt-in — compose profile ``workers``).
  Run:  python -m clinicai.worker
  Env:  RABBITMQ_URL, WORKER_QUEUE

Mode 2 (relay): Notification outbox relay — polls ``event_log`` and delivers
  notifications via Telegram/Zalo. Does NOT need RabbitMQ.
  Run:  python -m clinicai.worker --relay
  Env:  DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

Mode 3 (pos-relay): POS outbox relay — polls ``pos_outbox`` and pushes invoices
  and stock movements to whichever POS the clinic configured (ADR-0010). With
  the default null adapter it simply drains the queue, so it is harmless to run
  before any POS is connected.
  Run:  python -m clinicai.worker --pos-relay
  Env:  DATABASE_URL, POS_ADAPTER (default ``none``)

The relay mode is the recommended lightweight path for a single Mac mini
deployment. RabbitMQ mode is kept for future scaling.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Relay mode (--relay): poll event_log → deliver via Telegram/Zalo
# ---------------------------------------------------------------------------

RELAY_POLL_INTERVAL = 30  # seconds between polls
# The POS is not on the critical path, so it can be told less often.
POS_RELAY_POLL_INTERVAL = 60


async def _run_relay() -> None:
    """Run the notification relay loop."""
    from clinicai.core.database import close_pool, create_pool
    from clinicai.services.notification_relay import poll_and_deliver

    pool = await create_pool()
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    logger.info("relay_started", poll_interval=RELAY_POLL_INTERVAL)

    try:
        while not stop.is_set():
            try:
                count = await poll_and_deliver(pool)
                if count > 0:
                    logger.info("relay_delivered", count=count)
            except Exception:
                logger.exception("relay_poll_error")

            # Wait for next poll or stop signal.
            try:
                await asyncio.wait_for(stop.wait(), timeout=RELAY_POLL_INTERVAL)
                break  # stop was set
            except asyncio.TimeoutError:
                continue  # poll again
    finally:
        await close_pool(pool)
        logger.info("relay_stopped")


# ---------------------------------------------------------------------------
# RabbitMQ mode (default): consume from broker
# ---------------------------------------------------------------------------


async def _run_pos_relay() -> None:
    """Run the POS outbox relay loop (ADR-0010)."""
    from clinicai.core.database import close_pool, create_pool
    from clinicai.services.pos_relay import poll_and_push

    pool = await create_pool()
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    logger.info(
        "pos_relay_started",
        poll_interval=POS_RELAY_POLL_INTERVAL,
        adapter=os.environ.get("POS_ADAPTER", "none"),
    )

    try:
        while not stop.is_set():
            try:
                await poll_and_push(pool)
            except Exception:
                # A broken POS must never take the relay down with it.
                logger.exception("pos_relay_poll_error")

            try:
                await asyncio.wait_for(stop.wait(), timeout=POS_RELAY_POLL_INTERVAL)
                break
            except asyncio.TimeoutError:
                continue
    finally:
        await close_pool(pool)
        logger.info("pos_relay_stopped")


async def _run_rabbitmq() -> None:
    """Run the RabbitMQ consumer (legacy mode)."""
    from clinicai.event_bus.consumer import ConsumerConnectionError, RabbitMQConsumer
    from clinicai.schemas.events import InteractionEvent

    async def _log_handler(event: InteractionEvent) -> None:
        logger.info(
            "worker_event_received",
            event_type=getattr(event, "event_type", None),
        )

    url = os.environ.get("RABBITMQ_URL")
    if not url:
        raise SystemExit("RABBITMQ_URL is not set — cannot start worker.")
    queue = os.environ.get("WORKER_QUEUE", "clinicai.events")

    consumer = RabbitMQConsumer(connection_url=url, queue=queue, handler=_log_handler)
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    try:
        await consumer.start()
        logger.info("worker_started", queue=queue)
        await stop.wait()
    except ConsumerConnectionError as exc:
        logger.error("worker_broker_unavailable", error=str(exc))
        raise SystemExit(1) from exc
    finally:
        await consumer.stop()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    if "--pos-relay" in sys.argv:
        asyncio.run(_run_pos_relay())
    elif "--relay" in sys.argv:
        asyncio.run(_run_relay())
    else:
        asyncio.run(_run_rabbitmq())


if __name__ == "__main__":
    main()
