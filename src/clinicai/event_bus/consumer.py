"""RabbitMQ Consumer worker — MVP skeleton + MockConsumer for unit tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from clinicai.schemas.events import InteractionEvent

logger = structlog.get_logger()

EventHandler = Callable[["InteractionEvent"], Awaitable[None]]


class ConsumerConnectionError(RuntimeError):
    """Raised when the consumer fails to establish a broker connection."""


class RabbitMQConsumer:
    """RabbitMQ consumer that delivers InteractionEvents to a handler.

    MVP scope: simple connect → consume loop → call handler. No retry loop;
    on connection failure we log and raise ConsumerConnectionError so the
    caller (worker entrypoint) can decide restart policy.
    """

    def __init__(
        self,
        connection_url: str,
        queue: str,
        handler: EventHandler,
    ) -> None:
        self.connection_url = connection_url
        self.queue = queue
        self.handler = handler
        self._connection = None
        self._channel = None
        self._stopped = False

    async def start(self) -> None:
        """Connect to RabbitMQ and start consuming messages.

        Real implementation will be wired in T-P5-04 once broker is unblocked.
        MVP: import aio_pika lazily and surface connection failures as
        ConsumerConnectionError; do not enter a retry loop.
        """
        try:
            import aio_pika  # noqa: PLC0415  (lazy import — keeps tests light)

            self._connection = await aio_pika.connect_robust(self.connection_url)
            self._channel = await self._connection.channel()
            queue = await self._channel.declare_queue(self.queue, durable=True)
            logger.info(
                "consumer_started",
                queue=self.queue,
                url=self.connection_url,
            )
            await queue.consume(self._on_message)
        except ConsumerConnectionError:
            raise
        except Exception as e:
            logger.error(
                "consumer_connection_failed",
                queue=self.queue,
                error=str(e),
            )
            raise ConsumerConnectionError(str(e)) from e

    async def _on_message(self, message) -> None:  # type: ignore[no-untyped-def]
        """Decode message into InteractionEvent and dispatch to handler."""
        from clinicai.schemas.events import InteractionEvent  # noqa: PLC0415

        async with message.process():
            event = InteractionEvent.model_validate_json(message.body)
            await self.handler(event)

    async def stop(self) -> None:
        """Gracefully close channel + connection."""
        self._stopped = True
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()
        logger.info("consumer_stopped", queue=self.queue)


class MockConsumer:
    """In-memory consumer for unit tests — replays a pre-supplied event list."""

    def __init__(
        self,
        events: list[InteractionEvent],
        handler: EventHandler,
    ) -> None:
        self.events = events
        self.handler = handler
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        """Replay all queued events through the handler in order."""
        self.started = True
        for event in self.events:
            await self.handler(event)

    async def stop(self) -> None:
        """No resources to release; flip the flag for test assertions."""
        self.stopped = True
