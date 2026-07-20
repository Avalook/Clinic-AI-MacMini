"""
Health check script for RabbitMQ.
Run: poetry run python scripts/check_rabbitmq.py
Exit code 0 = healthy, 1 = unhealthy.
"""

import asyncio
import os
import sys

import aio_pika
from dotenv import load_dotenv


async def main() -> int:
    load_dotenv()
    url = os.getenv("RABBITMQ_URL")
    if not url:
        print("ERROR: RABBITMQ_URL not set in .env")
        return 1

    print(f"Connecting to {url}...")
    try:
        connection = await aio_pika.connect_robust(url, timeout=5)
    except Exception as exc:
        print(f"ERROR: Connection failed: {exc}")
        return 1

    async with connection:
        channel = await connection.channel()

        # Verify exchanges exist
        for exchange_name in ["events.topic", "events.dlx"]:
            try:
                await channel.get_exchange(exchange_name, ensure=True)
                print(f"  ✅ Exchange '{exchange_name}' exists")
            except Exception as exc:
                print(f"  ❌ Exchange '{exchange_name}' missing: {exc}")
                return 1

        # Verify queues exist
        for queue_name in ["events.audit", "events.dead_letter"]:
            try:
                await channel.get_queue(queue_name, ensure=True)
                print(f"  ✅ Queue '{queue_name}' exists")
            except Exception as exc:
                print(f"  ❌ Queue '{queue_name}' missing: {exc}")
                return 1

        # Round-trip publish + consume test
        test_routing_key = "test.healthcheck"
        test_payload = b"healthcheck_ping"

        exchange = await channel.get_exchange("events.topic")
        await exchange.publish(
            aio_pika.Message(body=test_payload),
            routing_key=test_routing_key,
        )
        print(f"  ✅ Published test message to '{test_routing_key}'")

        # Consume from events.audit (binding # catches all)
        audit_queue = await channel.get_queue("events.audit")
        async with audit_queue.iterator(timeout=3) as iterator:
            async for message in iterator:
                async with message.process():
                    if message.body == test_payload:
                        print("  ✅ Received test message on events.audit")
                        break

    print("\n🎉 RabbitMQ healthy!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
