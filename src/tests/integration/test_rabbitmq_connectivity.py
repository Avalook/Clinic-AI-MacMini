"""Integration test: RabbitMQ connectivity + topology.

Skipped automatically if RABBITMQ_URL not set or MQ not reachable.
Run: poetry run pytest src/tests/integration/test_rabbitmq_connectivity.py
"""

import os

import aio_pika
import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def rabbitmq_connection():
    url = os.getenv("RABBITMQ_URL")
    if not url:
        pytest.skip("RABBITMQ_URL not set")
    try:
        conn = await aio_pika.connect_robust(url, timeout=3)
    except Exception as exc:
        pytest.skip(f"RabbitMQ not reachable: {exc}")
    yield conn
    await conn.close()


async def test_exchanges_exist(rabbitmq_connection):
    """events.topic và events.dlx phải tồn tại."""
    channel = await rabbitmq_connection.channel()
    for name in ["events.topic", "events.dlx"]:
        ex = await channel.get_exchange(name, ensure=True)
        assert ex is not None


async def test_queues_exist(rabbitmq_connection):
    """events.audit và events.dead_letter phải tồn tại."""
    channel = await rabbitmq_connection.channel()
    for name in ["events.audit", "events.dead_letter"]:
        q = await channel.get_queue(name, ensure=True)
        assert q is not None


async def test_publish_consume_round_trip(rabbitmq_connection):
    """Publish vào events.topic → consume từ events.audit."""
    channel = await rabbitmq_connection.channel()
    exchange = await channel.get_exchange("events.topic")

    test_key = "test.roundtrip"
    test_body = b"hello_t_p5_02"

    await exchange.publish(
        aio_pika.Message(body=test_body),
        routing_key=test_key,
    )

    audit_queue = await channel.get_queue("events.audit")
    async with audit_queue.iterator(timeout=5) as iterator:
        async for message in iterator:
            async with message.process():
                if message.body == test_body:
                    return  # success
    pytest.fail("Did not receive test message within timeout")
