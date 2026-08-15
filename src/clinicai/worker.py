"""Worker entrypoint — two modes of operation.

Mode 1 (default): RabbitMQ consumer (opt-in — compose profile ``workers``).
  Run:  python -m clinicai.worker
  Env:  RABBITMQ_URL, WORKER_QUEUE

Mode 2 (relay): Notification outbox relay — polls ``event_log`` and delivers
  notifications via Telegram/Zalo. Does NOT need RabbitMQ.
  Run:  python -m clinicai.worker --relay
  Env:  DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
        TELEGRAM_CLINIC_ID

Mode 3 (pos-relay): POS outbox relay — polls ``pos_outbox`` and pushes invoices
  and stock movements to whichever POS the clinic configured (ADR-0010). With
  the default null adapter, rows are dead-lettered rather than falsely marked
  delivered. Enable this mode only after configuring a real adapter.
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
import time
from pathlib import Path
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Relay mode (--relay): poll event_log → deliver via Telegram/Zalo
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Liveness heartbeat
# ---------------------------------------------------------------------------
# `restart: unless-stopped` in compose restarts a worker whose PROCESS dies. It
# does nothing about the failure that actually happens to poll loops: the
# process stays up and the loop stops turning — a connection that never times
# out, a task awaiting something that will not arrive, an exception swallowed in
# a nested handler. The container reports healthy, Uptime Kuma is green, and
# nobody learns that patients stopped getting their SMS until one of them says
# so.
#
# None of the three worker services had a healthcheck at all. This is the
# cheapest honest one: each completed pass touches a file, and the compose
# healthcheck fails if that file stops moving. It proves the loop turned, not
# merely that a PID exists.
HEARTBEAT_PATH = Path(os.environ.get("WORKER_HEARTBEAT_FILE", "/tmp/worker-alive"))


def _beat() -> None:
    """Record that the loop completed a pass. Never fatal."""
    try:
        HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_PATH.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        # A worker must not die because it could not write a liveness file; the
        # healthcheck going stale is already the correct signal.
        logger.warning("heartbeat_write_failed", path=str(HEARTBEAT_PATH))


WORKER_HEARTBEAT_INTERVAL = 30  # consumer liveness tick
RELAY_POLL_INTERVAL = 30  # seconds between polls
# The POS is not on the critical path, so it can be told less often.
POS_RELAY_POLL_INTERVAL = 60


async def _run_relay() -> None:
    """Run the notification relay loop."""
    from clinicai.core.database import close_pool, create_pool
    from clinicai.services.notification_relay import poll_and_deliver

    # CHỐT CỨNG TRƯỚC BẢN DÙNG THỬ 15/08 (Quang chốt 09/08/2026: "ngắt cái tele
    # đã"). MVP này là CSKH thao tác tay và tự bấm gửi; không có gì được tự bắn
    # ra ngoài.
    #
    # `profiles` của compose KHÔNG đủ để coi là đã tắt: `--profile workers` bật
    # MỘT LÚC cả worker, pos-relay VÀ notification-relay. Ai bật worker cho việc
    # khác là relay đi theo, và ngay lúc đó nó gặp 208 dòng `event_log` chưa
    # publish còn tồn (docs/DANG-LAM.md §5) — bắn cả 208 tin trong mấy vòng poll
    # đầu, gồm sự kiện từ nhiều ngày trước.
    #
    # Cờ này phải BẬT TƯỜNG MINH mới chạy. Mở lại: đặt NOTIFICATION_RELAY_ENABLED=true
    # trong .env — và xử lý đống tồn đọng trước khi mở.
    if os.environ.get("NOTIFICATION_RELAY_ENABLED", "").strip().lower() != "true":
        raise SystemExit(
            "notification-relay đang TẮT có chủ ý "
            "(NOTIFICATION_RELAY_ENABLED != true). MVP 15/08: mọi tin nhắn do "
            "người bấm gửi, không tự động. "
            "Muốn bật lại thì dọn event_log tồn đọng trước."
        )

    raw_clinic_id = os.environ.get("TELEGRAM_CLINIC_ID", "").strip()
    if not raw_clinic_id:
        raise SystemExit(
            "TELEGRAM_CLINIC_ID is not set — refusing a cross-tenant relay."
        )
    try:
        clinic_id = str(UUID(raw_clinic_id))
    except ValueError as exc:
        raise SystemExit("TELEGRAM_CLINIC_ID must be a UUID.") from exc

    pool = await create_pool()
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # REALTIME (15/08/2026): nghe cùng kênh pg_notify mà màn hình dùng —
    # sự kiện ghi xong là poll chạy NGAY, nhịp 30s chỉ còn là lưới an toàn
    # cho lúc connection LISTEN rớt. Giữ một connection riêng khỏi pool cho
    # tới finally: listener sống bằng connection, trả về pool là điếc.
    from clinicai.services.notification_relay import nen_danh_thuc

    danh_thuc = asyncio.Event()

    def _khi_notify(_conn: object, _pid: int, _channel: str, payload: str) -> None:
        if nen_danh_thuc(payload, clinic_id):
            danh_thuc.set()

    nghe = await pool.acquire()
    await nghe.add_listener("clinicai_changes", _khi_notify)

    logger.info("relay_started", poll_interval=RELAY_POLL_INTERVAL, listen=True)

    try:
        while not stop.is_set():
            try:
                count = await poll_and_deliver(pool, clinic_id=clinic_id)
                if count > 0:
                    logger.info("relay_delivered", count=count)
                _beat()
            except Exception:
                logger.exception("relay_poll_error")

            # Chờ: tin notify ĐÁNH THỨC sớm, hết 30s thì poll cho chắc,
            # stop thì ra về. Gộp một nhịp thở 300ms sau khi thức để một
            # thao tác đụng nhiều sự kiện thành MỘT lượt poll.
            cho_thuc = asyncio.ensure_future(danh_thuc.wait())
            cho_dung = asyncio.ensure_future(stop.wait())
            done, pending = await asyncio.wait(
                {cho_thuc, cho_dung},
                timeout=RELAY_POLL_INTERVAL,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            if cho_dung in done:
                break
            if cho_thuc in done:
                danh_thuc.clear()
                await asyncio.sleep(0.3)
    finally:
        try:
            await nghe.remove_listener("clinicai_changes", _khi_notify)
            await pool.release(nghe)
        except Exception:
            pass
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
                _beat()
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

    async def _heartbeat() -> None:
        """Tick while the consumer is connected.

        A consumer has no poll loop to hang a heartbeat off — it sits in
        ``stop.wait()`` and reacts to deliveries. So liveness is "the broker
        connection is still open", checked on a timer. Without this the worker
        container had no healthcheck at all: a consumer whose channel had died
        silently looked identical to an idle one with nothing to do.
        """
        while not stop.is_set():
            if getattr(consumer, "is_connected", lambda: True)():
                _beat()
            try:
                await asyncio.wait_for(stop.wait(), timeout=WORKER_HEARTBEAT_INTERVAL)
                return
            except asyncio.TimeoutError:
                continue

    try:
        await consumer.start()
        logger.info("worker_started", queue=queue)
        _beat()
        beat_task = asyncio.create_task(_heartbeat())
        try:
            await stop.wait()
        finally:
            beat_task.cancel()
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
