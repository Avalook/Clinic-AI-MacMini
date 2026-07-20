"""Event Bus Publisher Interface and implementations."""

from abc import ABC, abstractmethod

from clinicai.schemas.events import InteractionEvent


class IEventPublisher(ABC):
    """Abstract interface for publishing events to an external message broker."""

    @abstractmethod
    async def publish(self, topic: str, event: InteractionEvent) -> None:
        """Publish an event to the specified topic/routing key."""

    @abstractmethod
    async def close(self) -> None:
        """Close broker connection resources."""


class MockEventPublisher(IEventPublisher):
    """In-memory event publisher for unit testing and local development."""

    def __init__(self) -> None:
        self.published: list[tuple[str, InteractionEvent]] = []

    async def publish(self, topic: str, event: InteractionEvent) -> None:
        """Simulate publishing by appending to local list."""
        self.published.append((topic, event))

    async def close(self) -> None:
        """No resources to close in mock."""
        pass

    def last(self) -> tuple[str, InteractionEvent]:
        """Return the most recently published event."""
        if not self.published:
            msg = "No events have been published yet."
            raise ValueError(msg)
        return self.published[-1]

    def count(self) -> int:
        """Return the total number of published events."""
        return len(self.published)


class RabbitMQPublisher(IEventPublisher):
    """Production RabbitMQ implementation.

    Currently a stub raising NotImplementedError until RabbitMQ infra is unblocked.
    """

    async def publish(self, topic: str, event: InteractionEvent) -> None:
        """Raise NotImplementedError to signal pending infrastructure."""
        raise NotImplementedError("RabbitMQ infra pending")

    async def close(self) -> None:
        """Raise NotImplementedError."""
        raise NotImplementedError("RabbitMQ infra pending")
