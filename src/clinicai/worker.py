"""Standalone RabbitMQ worker entrypoint (opt-in — compose profile `workers`).

Runs the :class:`RabbitMQConsumer` as its own process so event handling scales
independently of the API. The broker is not required for the core booking/brief
flow, so this service is gated behind the `workers` compose profile.

Run:  python -m clinicai.worker
Env:  RABBITMQ_URL   (amqp://user:pass@host:5672/vhost)
      WORKER_QUEUE   (default: clinicai.events)

NOTE: the consumer is MVP scaffolding (see event_bus/consumer.py). The default
handler here only logs; wire a real dispatch handler when the broker flow is
activated (T-P5-04).
"""

from __future__ import annotations

import asyncio
import os
import signal

import structlog

from clinicai.event_bus.consumer import ConsumerConnectionError, RabbitMQConsumer
from clinicai.schemas.events import InteractionEvent

logger = structlog.get_logger(__name__)


async def _log_handler(event: InteractionEvent) -> None:
    """Default sink: log the event. Replace with real dispatch when wiring the broker."""
    logger.info("worker_event_received", event_type=getattr(event, "event_type", None))


async def _run() -> None:
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


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
